"""One original-budget dense36 run with invariant complex radial robust residuals."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import time as timer

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
args=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(args.workspace/'tools/ipm_deps'),str(args.workspace/'tools/qp_deps'),str(args.workspace/'tools/python_deps')]
import numpy as np
import scipy
import clarabel
from drive_evidence_v1.sources import sha
from quintic_phase_v1.model import QuinticAbsoluteModel
from correlated_observation_v1.marginal import MarginalAperture
from aperture_model_v1.checks import assess
from complex_radial_v1.fit import estimate


def load(path):return json.loads(path.read_text(encoding='utf-8'))
def save(path,value):path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.complex-radial-fit/1',result='running',sources={},real_audio_read=False,
    model_exported=False,runtime_changed=False,full_qualification=False)
try:
    parent=args.workspace/'references/analysis/correlated_observation_v1/fit1';old=load(parent/'report.json')
    checks=args.workspace/'references/analysis/complex_radial_v1/controls1';checked=load(checks/'report.json')
    assert checked['result']=='radial_loss_QP_and_observed_derivative_controls_passed' and checked['parent_input_sha256']==sha(parent/'input.npz')
    sources={Path(__file__)}
    for name,digest in checked['sources'].items():assert sha(repo/name)==sha(checks/'exact_sources'/name)==digest;sources.add(repo/name)
    for path in sources:
        relative=path.relative_to(repo);dest=args.out/'exact_sources'/relative
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest);report['sources'][relative.as_posix()]=sha(path)
    plan=load(parent/'effective_plan.json');settings=load(parent/'effective_settings.json');variant=load(repo/'research/minority_phase_v1_plan.json')
    assert settings['maximum_iterations']==20
    inputs=np.load(parent/'input.npz');time,audio,initial=(inputs[k] for k in ('time','audio','initial_parameters'))
    model=QuinticAbsoluteModel(time,plan,variant,[]);old_wave=model.original.samples(initial)[0]
    model.original.aperture=MarginalAperture(model.original.aperture)
    assert np.array_equal(old_wave,model.original.samples(initial)[0])
    save(args.out/'effective_plan.json',plan);save(args.out/'effective_settings.json',settings)
    np.savez_compressed(args.out/'input.npz',time=time,audio=audio,initial_parameters=initial)
    report.update(parent_report_sha256=sha(parent/'report.json'),parent_input_sha256=sha(parent/'input.npz'),controls_report_sha256=sha(checks/'report.json'),
        sample_model_bounds_initial_unchanged=True,numeric_libraries=dict(numpy=np.__version__,scipy=scipy.__version__,clarabel=clarabel.__version__))
    assert report['numeric_libraries']==old['numeric_libraries']
    def progress(row):
        save(args.out/'progress.json',row)
        print(json.dumps(dict(iteration=row['iteration'],accepted=row['accepted'],qp_certified=row['qp']['success'],cost=row['candidate_cost'])),flush=True)
    started=timer.perf_counter();parameters,phase,fit=estimate(model,audio,time,plan,variant,settings,initial,progress)
    fit['seconds']=timer.perf_counter()-started;report['fit']=fit
    np.savez_compressed(args.out/'fit.npz',parameters=parameters,phase_correction=phase)
    # Original known phase and heldout orders become visible only after fitting is complete.
    topology=load(repo/'research/observed_topology_v1_plan.json');base=load(repo/topology['base_plan'])
    from observed_topology_v1.fixtures import make
    case=next(x for x in topology['added_cases'] if x['id']=='unknown_thirty_six')
    independent_time,independent_audio,truth,_=make(case,base)
    assert np.array_equal(independent_time,time) and np.array_equal(independent_audio,audio)
    assessment,positions,oracle=assess(audio,time,truth,phase,parameters,{**plan,'heldout_orders':base['heldout_orders']})
    np.savez_compressed(args.out/'coordinates.npz',positions=positions,oracle_positions=oracle)
    report.update(result='dense_radial_passed_not_full_qualification' if assessment['qualified'] and fit['observation_supported'] else 'dense_radial_rejected',
        assessment=assessment,qp_certified=sum(x['qp']['success'] for x in fit['history']),original_gates_unchanged=True,
        limits=['This changes complex robust geometry, not the marginal aperture or out-of-band leakage/noise model',
            'No nonlinear/global convergence claim; original dense/all17/full33/individual14k/originalE remain required',
            'No real recording, new sound DNA, high-frequency recovery or listening acceptance'])
    print(json.dumps(dict(result=report['result'],qp_certified=report['qp_certified'],phase_p95=assessment['point_phase_p95_cycles'])),flush=True)
except Exception as exc:report.update(result='failed',error=repr(exc));raise
finally:save(args.out/'report.json',report)
