"""Test finite-aperture phase inversion without reading any real recording."""
import argparse
from contextlib import nullcontext
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
from drive_evidence_v1.sources import sha
from aperture_model_v1.checks import controls,assess
from aperture_model_v1.fixtures import make
from aperture_model_v1.fit import estimate
try:
    from threadpoolctl import threadpool_limits,threadpool_info
    limit=lambda:threadpool_limits(limits=2)
except ImportError:
    threadpool_info=lambda:[]
    limit=nullcontext


def save(path,value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.aperture-model-validation/1',result='running',sources={},cases=[],
    real_audio_read=False,real_source_permitted=False,runtime_changed=False,
    environment=dict(python=sys.version,numpy=np.__version__,scipy=scipy.__version__,threadpools=threadpool_info()))
try:
    plan_path=repo/'research/aperture_model_v1_plan.json'
    plan=json.loads(plan_path.read_text(encoding='utf-8'))
    report['plan_sha256']=sha(plan_path)
    sources=[Path(__file__),plan_path,repo/'tools/drive_evidence_v1/sources.py']+list((repo/'tools/aperture_model_v1').glob('*.py'))
    for source in sources:
        relative=source.relative_to(repo)
        target=args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target)
        report['sources'][relative.as_posix()]=sha(source)
    with limit():
        report['controls']=controls(plan)
        assert report['controls']['passed']
        save(args.out/'controls.json',report['controls'])
        print(json.dumps(dict(controls=report['controls'])),flush=True)
        for case in plan['cases']:
            start=timer.perf_counter()
            directory=args.out/case['id']
            directory.mkdir()
            time,audio,truth=make(case,plan)
            estimated,fit,parameters=estimate(audio,time,plan)
            result,positions,oracle_positions=assess(audio,time,truth,estimated,parameters,plan)
            item=dict(case=case,fit=fit,assessment=result,seconds=timer.perf_counter()-start,
                passed=not result['qualified'] if case.get('negative') else result['qualified'])
            np.savez_compressed(directory/'fit.npz',time=time,true_phase_correction=truth,
                fitted_phase_correction=estimated,parameters=parameters,positions=positions,oracle_positions=oracle_positions)
            save(directory/'report.json',item)
            report['cases'].append(item)
            print(json.dumps(dict(id=case['id'],passed=item['passed'],evaluations=fit['evaluations'],
                residual=fit['normalized_projection_residual'],phase=result['point_phase_p95_cycles'],
                power=result['maximum_heldout_power_error_db'],correlation=result['maximum_heldout_complex_correlation_error'],
                seconds=item['seconds'])),flush=True)
    report['result']='passed' if all(row['passed'] for row in report['cases']) else 'rejected'
    report['limits']=['Known sparse low-band topology only; no real-source identifiability proof',
        'These controls do not replace the original33 or individual14kHz retention gates',
        'No physical RPM, source export, C model, listening or driving acceptance']
except Exception as exc:
    report.update(result='failed',error=repr(exc))
    raise
finally:
    save(args.out/'report.json',report)
