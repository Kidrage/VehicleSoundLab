"""Refine all original measured-topology cases with unchanged acceptance gates."""
import argparse
from contextlib import nullcontext
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time as timer

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--validation',type=Path,required=True)
parser.add_argument('--reuse-dense',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
from drive_evidence_v1.sources import sha
from aperture_model_v1.checks import assess
from minority_phase_v1.model import MinorityModel
from observed_topology_v1.fixtures import make
from envelope_resolution_v1.refine import geometry,transfer,estimate
from envelope_resolution_v1.checks import controls
try:
    from threadpoolctl import threadpool_limits
    limit=lambda:threadpool_limits(limits=2)
except ImportError:
    limit=nullcontext


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path,value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.envelope-resolution-validation/1',result='running',sources={},cases=[],
    real_audio_read=False,real_source_permitted=False,runtime_changed=False)
try:
    previous=load(args.validation/'report.json')
    dense=load(args.reuse_dense/'report.json')
    assert previous['result']=='rejected' and dense['result']=='dense_diagnostic_passed_not_full_qualification'
    report['parent_report_sha256']=sha(args.validation/'report.json')
    assert dense['validation_report_sha256']==report['parent_report_sha256']
    report['dense_report_sha256']=sha(args.reuse_dense/'report.json')
    settings=load(repo/'research/envelope_resolution_v1_plan.json')
    topology=load(repo/settings['parent_plan'])
    base=load(repo/topology['base_plan'])
    variant=load(repo/topology['minority_plan'])
    sources={Path(__file__),repo/'tools/envelope_resolution_v1/checks.py'}|{repo/name for name in dense['sources']}
    for parent,folder in ((previous,args.validation),(dense,args.reuse_dense)):
        for name,digest in parent['sources'].items():
            assert sha(repo/name)==sha(folder/'exact_sources'/name)==digest
    for source in sources:
        relative=source.relative_to(repo)
        target=args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target)
        report['sources'][relative.as_posix()]=sha(source)
    assert [row['case'] for row in previous['cases']]==base['cases']+variant['added_cases']+topology['added_cases']
    with limit():
        time=np.arange(base['cycles']*base['samples_per_cycle'])/base['samples_per_cycle']
        check_plan=load(args.validation/'unknown_thirty_six/effective_plan.json')
        report['controls']=controls(time,check_plan,variant,settings['minimum_envelope_transfer_accuracy'])
        for old in previous['cases']:
            started=timer.perf_counter()
            case=old['case']
            directory=args.out/case['id']
            directory.mkdir()
            item=dict(case=case,fit_reused=False,parent_status=old['status'])
            if old['status']=='topology_rejected':
                assert len(old['topology']['selected_orders'])<variant['minimum_remaining_carriers']
                item.update(status='topology_rejected',observation_supported=False,qualified=False,passed=bool(case.get('negative')))
            else:
                time,audio,truth,_=make(case,base)
                audio_hash=hashlib.sha256(audio.tobytes()).hexdigest()
                assert audio_hash==old['fixture_audio_sha256']
                previous_plan=load(args.validation/case['id']/'effective_plan.json')
                effective,item['geometry']=geometry(previous_plan)
                save(directory/'effective_plan.json',effective)
                saved=np.load(args.validation/case['id']/'fit.npz')
                assert np.array_equal(time,saved['time']) and np.array_equal(truth,saved['true_phase_correction'])
                selected=old['fit']['selected_indices']
                initial,item['transfer']=transfer(time,previous_plan,effective,variant,selected,saved['parameters'],
                    settings['minimum_envelope_transfer_accuracy'])
                if case['id']==settings['diagnostic_case']:
                    assert effective==load(args.reuse_dense/'effective_plan.json')
                    stored=np.load(args.reuse_dense/'fit.npz')
                    assert np.array_equal(initial,stored['initial_parameters'])
                    parameters=stored['parameters']
                    phase=MinorityModel(time,effective,variant,selected).samples(parameters)[1]
                    assert np.array_equal(phase,stored['phase_correction'])
                    fit=dense['fit'].copy()
                    item['fit_reused']=dict(report_sha256=report['dense_report_sha256'],arrays_sha256=sha(args.reuse_dense/'fit.npz'),
                        effective_input_and_source_exact=True)
                else:
                    print(json.dumps(dict(id=case['id'],status='refining_real_amplitude',spacing=effective['amplitude_knot_cycles'])),flush=True)
                    parameters,phase,fit=estimate(audio,time,effective,variant,selected,initial,settings['maximum_evaluations'])
                np.savez_compressed(directory/'fit.npz',time=time,parameters=parameters,initial_parameters=initial,
                    phase_correction=phase,true_phase_correction=truth)
                item.update(fit=fit,observation_supported=fit['observation_supported'],fixture_audio_sha256=audio_hash,
                    effective_plan_sha256=sha(directory/'effective_plan.json'))
                if not fit['observation_supported']:
                    item.update(status='observation_rejected',qualified=False,passed=bool(case.get('negative')))
                else:
                    assessment,positions,oracle_positions=assess(audio,time,truth,phase,parameters,
                        {**effective,'heldout_orders':base['heldout_orders']})
                    np.savez_compressed(directory/'coordinates.npz',positions=positions,oracle_positions=oracle_positions)
                    if item['fit_reused']:
                        assert assessment==dense['assessment']
                    item.update(status='measured',assessment=assessment,qualified=assessment['qualified'],
                        passed=bool(assessment['qualified'] and not case.get('negative')))
            item['seconds']=timer.perf_counter()-started
            report['cases'].append(item)
            save(directory/'report.json',item)
            print(json.dumps(dict(id=case['id'],status=item['status'],passed=item['passed'],
                phase=item.get('assessment',{}).get('point_phase_p95_cycles'),seconds=item['seconds'])),flush=True)
    report['result']='passed' if all(row['passed'] for row in report['cases']) else 'rejected'
    report['limits']=['All17 is a low-bandwidth principle check, not full33 or individual14kHz qualification',
        'Nested refinement retains the prior observation-selected minority phase departures; no physical order/RPM inference',
        'No real source read, profile, C, audio or listening change; moving35 held']
except Exception as exc:
    report.update(result='failed',error=repr(exc))
    raise
finally:
    save(args.out/'report.json',report)
