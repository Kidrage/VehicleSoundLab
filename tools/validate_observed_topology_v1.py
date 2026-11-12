"""Fit measured topology and preserve all original phase and stereo gates."""
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
parser.add_argument('--observations',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
parser.add_argument('--reuse-completed',type=Path,help='Reuse exactly verified completed cases from an earlier terminal run')
args=parser.parse_args()
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
import scipy
from drive_evidence_v1.sources import sha
from aperture_model_v1.fit import estimate as baseline_estimate
from aperture_model_v1.checks import assess
from aperture_model_v1.forward import real_rows
from minority_phase_v1.model import MinorityModel
from minority_phase_v1.fit import estimate
from observed_topology_v1.discover import discover
from observed_topology_v1.fixtures import make
from observed_topology_v1.inputs import numerical_inputs
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
report=dict(schema='vsl.observed-topology-validation/1',result='running',cases=[],sources={},
    real_audio_read=False,real_source_permitted=False,runtime_changed=False,
    environment=dict(python=sys.version,numpy=np.__version__,scipy=scipy.__version__))
try:
    observed=load(args.observations/'report.json')
    assert observed['result']=='observed' and observed['controls']['passed']
    for name,digest in observed['sources'].items():
        assert sha(repo/name)==sha(args.observations/'exact_sources'/name)==digest
    report['observation_report_sha256']=sha(args.observations/'report.json')
    settings_path=repo/'research/observed_topology_v1_plan.json'
    settings=load(settings_path)
    base=load(repo/settings['base_plan'])
    variant=load(repo/settings['minority_plan'])
    geometry,discovery_settings=numerical_inputs(base,settings)
    prior_path=args.workspace/'references/analysis/minority_phase_v1/validate2'
    prior=load(prior_path/'report.json')
    assert prior['result']=='passed'
    for name,digest in prior['sources'].items():
        assert sha(repo/name)==sha(prior_path/'exact_sources'/name)==digest
    assert all(prior['environment'][key]==report['environment'][key] for key in ('numpy','scipy','python'))
    report['minority_report_sha256']=sha(prior_path/'report.json')
    completed=None
    if args.reuse_completed:
        completed=load(args.reuse_completed/'report.json')
        assert completed['result'] in ('failed','passed','rejected')
        unchanged_exceptions={'tools/observe_topology_v1.py','tools/validate_observed_topology_v1.py',
            'tools/observed_topology_v1/discover.py'}
        for name,digest in completed['sources'].items():
            assert sha(args.reuse_completed/'exact_sources'/name)==digest
            if name not in unchanged_exceptions:
                assert sha(repo/name)==digest
        report['completed_run_sha256']=sha(args.reuse_completed/'report.json')
    sources={Path(__file__)}|{repo/name for name in observed['sources']}|{repo/name for name in prior['sources']}
    for source in sources:
        relative=source.relative_to(repo)
        target=args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target)
        report['sources'][relative.as_posix()]=sha(source)
    with limit():
        for case in base['cases']+variant['added_cases']+settings['added_cases']:
            started=timer.perf_counter()
            directory=args.out/case['id']
            directory.mkdir()
            time,audio,truth,fixture_plan=make(case,base)
            orders,evidence=discover(audio,time,geometry,discovery_settings)
            observation=next(row for row in observed['cases'] if row['case']==case)
            assert evidence==observation['evidence']
            audio_hash=hashlib.sha256(audio.tobytes()).hexdigest()
            assert audio_hash==observation['fixture_audio_sha256']
            effective={**geometry,'source_orders':orders}
            save(directory/'effective_plan.json',effective)
            item=dict(case=case,topology=evidence,fixture_audio_sha256=audio_hash,
                effective_plan_sha256=sha(directory/'effective_plan.json'),fit_reused=False)
            if len(orders)<variant['minimum_remaining_carriers']:
                item.update(status='topology_rejected',reason='Fewer measured candidates than required remaining coherent carriers',
                    qualified=False,observation_supported=False,passed=bool(case.get('negative')))
            else:
                completed_item=next((row for row in completed['cases'] if row['case']==case and row['passed']
                    and row['status']=='measured'),None) if completed else None
                old=completed_item or next((row for row in prior['cases'] if row['case']==case),None)
                if completed_item is not None or (old is not None and orders==base['source_orders']):
                    # Unused truth/case metadata is stripped from the estimator
                    # interface. Every effective plan field is unchanged.
                    previous_directory=args.reuse_completed/case['id'] if completed_item else prior_path/case['id']
                    if completed_item:
                        assert effective==load(previous_directory/'effective_plan.json')
                        assert evidence==completed_item['topology']
                    else:
                        assert effective=={key:value for key,value in base.items() if key in effective}
                    assert old['fixture_audio_sha256']==audio_hash
                    saved_path=previous_directory/'fit.npz'
                    saved=np.load(saved_path)
                    assert np.array_equal(time,saved['time']) and np.array_equal(truth,saved['true_phase_correction'])
                    parameters=saved['parameters']
                    baseline=saved['baseline_parameters']
                    fitted=old['fit']
                    model=MinorityModel(time,effective,variant,fitted['selected_indices'])
                    phase=model.samples(parameters)[1]
                    assert np.array_equal(phase,saved['fitted_phase_correction'])
                    target=real_rows(model.aperture.apply(audio[:,0]))
                    normalized=float(np.linalg.norm(model.prediction(parameters)-target)/max(np.linalg.norm(target),1e-30))
                    assert normalized==fitted['normalized_projection_residual']
                    item['fit_reused']=dict(report_sha256=sha(previous_directory/'report.json'),
                        arrays_sha256=sha(saved_path),effective_input_and_sources_exact=True,
                        actual_signal_phase_and_residual_exact=True,completed_run=bool(completed_item))
                    baseline_report=old['baseline']
                else:
                    print(json.dumps(dict(id=case['id'],status='fitting_new_measured_topology',lines=len(orders))),flush=True)
                    _,baseline_report,baseline=baseline_estimate(audio,time,effective)
                    phase,parameters,fitted=estimate(audio,time,effective,variant,baseline)
                # Always retain the actual fitted coordinate before attempting
                # any oracle remapping. Unsupported candidates never authorize
                # remapping; a nonmonotonic negative is a valid rejection.
                np.savez_compressed(directory/'fit.npz',time=time,true_phase_correction=truth,baseline_parameters=baseline,
                    fitted_phase_correction=phase,parameters=parameters)
                item.update(baseline=baseline_report,fit=fitted,observation_supported=fitted['observation_supported'],
                    minimum_coordinate_step=float(np.min(np.diff(time+phase))))
                if not fitted['observation_supported']:
                    item.update(status='observation_rejected',qualified=False,passed=bool(case.get('negative')),
                        reason='Measured model lacks residual/carrier/positive/monotonic support; no remapping attempted')
                else:
                    assessment_plan={**effective,'heldout_orders':base['heldout_orders']}
                    assessment,positions,oracle_positions=assess(audio,time,truth,phase,parameters,assessment_plan)
                    if item['fit_reused']:
                        assert assessment==old['assessment']
                    qualified=bool(assessment['qualified'])
                    passed=False if case.get('negative') else qualified
                    item.update(status='measured',assessment=assessment,qualified=qualified,passed=passed)
                    np.savez_compressed(directory/'coordinates.npz',positions=positions,oracle_positions=oracle_positions)
            item['seconds']=timer.perf_counter()-started
            save(directory/'report.json',item)
            report['cases'].append(item)
            print(json.dumps(dict(id=case['id'],status=item['status'],passed=item['passed'],lines=len(orders),
                selected=item.get('fit',{}).get('selected_orders'),phase=item.get('assessment',{}).get('point_phase_p95_cycles'),
                residual=item.get('fit',{}).get('normalized_projection_residual'),seconds=item['seconds'])),flush=True)
    report['result']='passed' if all(row['passed'] for row in report['cases']) else 'rejected'
    report['limits']=['The fifth grid is still declared; inferred candidates are not physical source identities',
        'All33 plus individual14kHz qualification and the original real-source case remain required',
        'No optimizer convergence, real idle timbre, C/runtime, listening or multiengine acceptance is established']
except Exception as exc:
    report.update(result='failed',error=repr(exc))
    raise
finally:
    save(args.out/'report.json',report)
