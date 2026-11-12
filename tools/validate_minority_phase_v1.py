"""Qualify observation-selected minority phase departures on declared controls."""
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
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
import scipy
from aperture_model_v1.fixtures import make as original_fixture
from aperture_model_v1.fit import Model,estimate as baseline_estimate
from aperture_model_v1.forward import real_rows
from aperture_model_v1.checks import assess
from drive_evidence_v1.sources import sha
from minority_phase_v1.checks import controls
from minority_phase_v1.fixtures import make
from minority_phase_v1.fit import estimate
try:
    from threadpoolctl import threadpool_limits
    limit=lambda:threadpool_limits(limits=2)
except ImportError:
    limit=nullcontext


def save(path,value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.minority-phase-validation/1',result='running',sources={},cases=[],
    real_audio_read=False,real_source_permitted=False,runtime_changed=False,
    environment=dict(python=sys.version,numpy=np.__version__,scipy=scipy.__version__))
try:
    variant_path=repo/'research/minority_phase_v1_plan.json'
    variant=json.loads(variant_path.read_text(encoding='utf-8'))
    plan_path=repo/variant['base_plan']
    assert sha(plan_path)==variant['base_plan_sha256']
    plan=json.loads(plan_path.read_text(encoding='utf-8'))
    report.update(plan_sha256=sha(variant_path),base_plan_sha256=sha(plan_path))
    prior_path=args.workspace/'references/analysis/aperture_model_v1/validate1'
    prior=json.loads((prior_path/'report.json').read_text(encoding='utf-8'))
    assert prior['result']=='rejected' and prior['plan_sha256']==sha(plan_path)
    for name,digest in prior['sources'].items():
        assert sha(repo/name)==sha(prior_path/'exact_sources'/name)==digest
    assert prior['environment']['numpy']==np.__version__ and prior['environment']['scipy']==scipy.__version__
    report['baseline_report_sha256']=sha(prior_path/'report.json')
    sources=[Path(__file__),variant_path,plan_path,repo/'tools/drive_evidence_v1/sources.py']
    sources+=list((repo/'tools/aperture_model_v1').glob('*.py'))+list((repo/'tools/minority_phase_v1').glob('*.py'))
    for source in sources:
        relative=source.relative_to(repo)
        target=args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target)
        report['sources'][relative.as_posix()]=sha(source)
    with limit():
        report['controls']=controls(plan,variant)
        assert report['controls']['passed']
        save(args.out/'controls.json',report['controls'])
        print(json.dumps(dict(controls=report['controls'])),flush=True)
        for case in plan['cases']+variant['added_cases']:
            started=timer.perf_counter()
            directory=args.out/case['id']
            directory.mkdir()
            time,audio,truth=make(case,plan)
            if case in plan['cases']:
                original=original_fixture(case,plan)
                assert all(np.array_equal(left,right) for left,right in zip((time,audio,truth),original))
                saved=np.load(prior_path/case['id']/'fit.npz')
                assert np.array_equal(time,saved['time']) and np.array_equal(truth,saved['true_phase_correction'])
                baseline=saved['parameters']
                model=Model(time,plan)
                assert np.array_equal(model.samples(baseline)[1],saved['fitted_phase_correction'])
                old=next(row for row in prior['cases'] if row['case']==case)
                baseline_report=old['fit']
                target=real_rows(model.aperture.apply(audio[:,0]))
                normalized=float(np.linalg.norm(model.prediction(baseline)-target)/max(np.linalg.norm(target),1e-30))
                assert normalized==baseline_report['normalized_projection_residual']
                reused=dict(actual_parameters_sha256=sha(prior_path/case['id']/'fit.npz'),
                    executed_sources_exact=True,fixtures_exact=True,actual_phase_and_residual_exact=True)
            else:
                _,baseline_report,baseline=baseline_estimate(audio,time,plan)
                reused=False
            phase,parameters,fitted=estimate(audio,time,plan,variant,baseline)
            assessment,positions,oracle_positions=assess(audio,time,truth,phase,parameters,plan)
            qualified=bool(assessment['qualified'] and fitted['observation_supported'])
            passed=not fitted['observation_supported'] if case.get('negative') else qualified
            item=dict(case=case,baseline=baseline_report,baseline_reused=reused,fit=fitted,assessment=assessment,
                qualified=qualified,passed=passed,seconds=timer.perf_counter()-started,
                fixture_audio_sha256=hashlib.sha256(audio.tobytes()).hexdigest())
            np.savez_compressed(directory/'fit.npz',time=time,true_phase_correction=truth,baseline_parameters=baseline,
                fitted_phase_correction=phase,parameters=parameters,positions=positions,oracle_positions=oracle_positions)
            save(directory/'report.json',item)
            report['cases'].append(item)
            print(json.dumps(dict(id=case['id'],passed=passed,selected=fitted['selected_orders'],
                observed_support=fitted['observation_supported'],residual=fitted['normalized_projection_residual'],
                point_phase=assessment['point_phase_p95_cycles'],power=assessment['maximum_heldout_power_error_db'],
                seconds=item['seconds'])),flush=True)
    report['result']='passed' if all(row['passed'] for row in report['cases']) else 'rejected'
    report['limits']=['Known sparse low-band topology; all33 and individual14kHz audits remain required',
        'Error gates and observed residual support are separate from optimizer convergence',
        'No physical RPM, real-source export, C model, listening or driving acceptance']
except Exception as exc:
    report.update(result='failed',error=repr(exc))
    raise
finally:
    save(args.out/'report.json',report)
