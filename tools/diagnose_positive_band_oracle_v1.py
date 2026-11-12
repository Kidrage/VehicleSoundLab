"""Diagnostic convex amplitude feasibility at the exact known phase; never an estimator."""
import argparse
from contextlib import nullcontext
import json
from pathlib import Path
import shutil
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--diagnosis',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
from scipy.optimize import minimize,LinearConstraint,Bounds
from drive_evidence_v1.sources import sha
from aperture_model_v1.forward import real_rows
from observed_topology_v1.fixtures import make
from positive_band_envelope_v1.model import BandModel
from positive_band_envelope_v1.basis import basis
try:
    from threadpoolctl import threadpool_limits
    limit=lambda:threadpool_limits(limits=2)
except ImportError:
    limit=nullcontext


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.positive-band-oracle-diagnosis/1',result='running',sources={},real_audio_read=False,
    real_source_permitted=False,qualification_changed=False,uses_analytic_phase_amplitude=True,
    may_initialize_estimator=False)
try:
    parent=load(args.diagnosis/'report.json')
    assert parent['result']=='dense_diagnostic_rejected'
    report['diagnosis_report_sha256']=sha(args.diagnosis/'report.json')
    sources={Path(__file__)}|{repo/name for name in parent['sources']}
    for name,digest in parent['sources'].items():
        assert sha(repo/name)==sha(args.diagnosis/'exact_sources'/name)==digest
    for source in sources:
        relative=source.relative_to(repo)
        target=args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target)
        report['sources'][relative.as_posix()]=sha(source)
    settings=load(repo/'research/positive_band_envelope_v1_plan.json')
    guard=load(repo/settings['parent_plan'])
    resolution=load(repo/guard['parent_plan'])
    topology=load(repo/resolution['parent_plan'])
    base=load(repo/topology['base_plan'])
    variant=load(repo/topology['minority_plan'])
    case=next(row for row in topology['added_cases'] if row['id']==settings['diagnostic_case'])
    time,audio,truth,_=make(case,base)
    plan=load(args.diagnosis/'effective_plan.json')
    model=BandModel(time,plan,variant,[])
    model.time=time+truth
    reduced,_=basis(time,plan['cycles'],model.orders)
    full=np.column_stack((1-reduced.sum(axis=1),reduced))
    gram=full.T@full/len(time)
    count=full.shape[1]
    bound=plan['amplitude_control_bound']
    inequality=np.zeros((2*(count-1),count))
    for j in range(1,count):
        inequality[2*(j-1),0]=-(1-bound)
        inequality[2*(j-1),j]=1
        inequality[2*(j-1)+1,0]=1+bound
        inequality[2*(j-1)+1,j]=-1
    parameters=np.zeros(model.parameter_count)
    controls=[]
    targets=[]
    report['partials']=[]
    with limit():
        for index,order in enumerate(plan['source_orders']):
            amplitude=(.045 if order in (2,3,5,7) else .022*(1+.15*np.cos(index*.31)))*case['gain']
            desired=amplitude*(1+.09*np.sin(2*np.pi*(.018+.0004*index)*time+.19*index))
            linear=full.T@desired/len(time)
            fitted=minimize(lambda x:float(x@gram@x-2*linear@x),np.full(count,amplitude),
                jac=lambda x:2*(gram@x-linear),method='SLSQP',
                constraints=[LinearConstraint(inequality,0,np.inf)],bounds=Bounds(1e-8,1),
                options=dict(ftol=1e-14,maxiter=300))
            assert np.min(inequality@fitted.x)>-1e-10
            c0=fitted.x[0]
            beta=fitted.x[1:]/c0-1
            assert abs(beta).max()<=bound+1e-8
            phi=.37*order+.013*order*order
            parameters[index]=c0*np.cos(phi)
            parameters[index+model.parts]=-c0*np.sin(phi)
            first=2*model.parts+model.phase_count+index*model.envelope_count
            parameters[first:first+model.envelope_count]=beta
            error=full@fitted.x-desired
            report['partials'].append(dict(order=order,success=bool(fitted.success),message=fitted.message,
                iterations=int(fitted.nit),amplitude_rms_error=float(np.sqrt(np.mean(error**2))),
                amplitude_maximum_error=float(abs(error).max())))
            controls.append(fitted.x)
            targets.append(desired)
        target=real_rows(model.aperture.apply(audio[:,0]))
        residual=model.prediction(parameters)-target
        normalized=float(np.linalg.norm(residual)/np.linalg.norm(target))
    np.savez_compressed(args.out/'oracle_amplitudes.npz',time=time,parameters=parameters,
        true_phase_correction=truth,absolute_controls=np.asarray(controls),true_amplitudes=np.asarray(targets))
    report.update(result='diagnosed_amplitude_feasibility_no_qualification_change',
        normalized_projection_residual_at_exact_phase=normalized,
        actual_estimator_projection_residual=parent['fit']['normalized_projection_residual'],
        all_qp_success=all(row['success'] for row in report['partials']),
        worst_amplitude_rms_error=max(row['amplitude_rms_error'] for row in report['partials']),
        limits=['Convex absolute amplitude QPs use known true curves and phase for diagnosis only',
            'They do not initialize or qualify the actual estimator, prove its optimum, or solve real idle/acceleration timbre'])
    print(json.dumps({key:report[key] for key in ('result','normalized_projection_residual_at_exact_phase',
        'actual_estimator_projection_residual','all_qp_success','worst_amplitude_rms_error')}),flush=True)
except Exception as exc:
    report.update(result='failed',error=repr(exc))
    raise
finally:
    (args.out/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
