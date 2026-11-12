"""Truth-only dense phase sensitivity, without nonlinear estimator refitting."""
import argparse
from contextlib import nullcontext
from copy import deepcopy
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
from scipy.optimize import lsq_linear
from drive_evidence_v1.sources import sha
from aperture_model_v1.fit import Model
from aperture_model_v1.forward import real_rows
from observed_topology_v1.fixtures import make
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
report=dict(schema='vsl.envelope-tangent-diagnosis/1',result='running',sources={},real_audio_read=False,
    qualification_changed=False,real_source_permitted=False,nonlinear_estimator_run=False,
    linear_projection_solves=True,oracle_diagnostic_only=True)
try:
    parent=load(args.diagnosis/'report.json')
    assert parent['result']=='dense_diagnostic_rejected'
    report['parent_report_sha256']=sha(args.diagnosis/'report.json')
    sources={Path(__file__)}|{repo/name for name in parent['sources']}
    for name,digest in parent['sources'].items():
        assert sha(repo/name)==sha(args.diagnosis/'exact_sources'/name)==digest
    for source in sources:
        relative=source.relative_to(repo)
        target=args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target)
        report['sources'][relative.as_posix()]=sha(source)
    settings=load(repo/'research/envelope_resolution_v1_plan.json')
    topology=load(repo/settings['parent_plan'])
    base=load(repo/topology['base_plan'])
    case=next(row for row in topology['added_cases'] if row['id']==settings['diagnostic_case'])
    plan=load(args.diagnosis/'effective_plan.json')
    time,observed,truth,_=make(case,base)
    silent_noise={**case,'noise':0}
    _,no_noise,_,_=make(silent_noise,base)
    no_holdout=deepcopy(base)
    no_holdout['heldout_orders']=[]
    _,source,_,_=make(silent_noise,no_holdout)
    omitted=no_noise-source
    noise=observed-no_noise
    assert abs(observed-source-omitted-noise).max()<1e-14
    model=Model(time,plan)
    model.time=time+truth
    parameters=np.zeros(model.parameter_count)
    with limit():
        for index,order in enumerate(plan['source_orders']):
            amplitude=(.045 if order in (2,3,5,7) else .022*(1+.15*np.cos(index*.31)))*case['gain']
            envelope=1+.09*np.sin(2*np.pi*(.018+.0004*index)*time+.19*index)
            phi=.37*order+.013*order*order
            parameters[index]=amplitude*envelope[0]*np.cos(phi)
            parameters[index+model.parts]=-amplitude*envelope[0]*np.sin(phi)
            beta=lsq_linear(model.envelope_basis,envelope/envelope[0]-1,
                bounds=(-plan['amplitude_control_bound'],plan['amplitude_control_bound']),tol=1e-12).x
            first=2*model.parts+model.phase_count+index*model.envelope_count
            parameters[first:first+model.envelope_count]=beta
        prediction,jacobian=model.prediction(parameters,True)
        source_target=real_rows(model.aperture.apply(source[:,0]))
        observed_target=real_rows(model.aperture.apply(observed[:,0]))
        components=np.column_stack((prediction-source_target,
            -real_rows(model.aperture.apply(omitted[:,0])),-real_rows(model.aperture.apply(noise[:,0]))))
        residual=prediction-observed_target
        closure=float(abs(components.sum(axis=1)-residual).max())
        assert closure<1e-12
        first=2*model.parts
        stop=first+model.phase_count
        free=np.r_[np.arange(first),np.arange(stop,model.parameter_count)]
        common=jacobian[:,first:stop]
        nuisance=jacobian[:,free]
        combined=np.column_stack((common,components))
        coefficients,_,nuisance_rank,_=np.linalg.lstsq(nuisance,combined,rcond=1e-10)
        profiled=combined-nuisance@coefficients
        phase_columns=profiled[:,:model.phase_count]
        # Minimum-norm UNWEIGHTED linear sensitivity at the known source.
        # This is not the bounded robust solver, a corrected phase or a
        # calibrated uncertainty bound. It cannot authorize an estimator.
        changes,_,phase_rank,singular=np.linalg.lstsq(phase_columns,-profiled[:,model.phase_count:],rcond=1e-10)
        phase_changes=model.phase_basis@changes
    interior=(time>=5)&(time<35)
    labels=['real_envelope_approximation','omitted_heldout_line_projection','fixture_noise']
    rows=[]
    for i,label in enumerate(labels):
        centered=phase_changes[:,i]-np.median(phase_changes[interior,i])
        rows.append(dict(component=label,projection_norm=float(np.linalg.norm(components[:,i])),
            profiled_projection_norm=float(np.linalg.norm(profiled[:,model.phase_count+i])),
            linearized_phase_p95_cycles=float(np.percentile(abs(centered[interior]),95)),
            maximum_absolute_linear_phase_control=float(abs(changes[:,i]).max())))
    total=phase_changes.sum(axis=1)
    total-=np.median(total[interior])
    actual=np.load(args.diagnosis/'fit.npz')['phase_correction']-truth
    actual-=np.median(actual[interior])
    np.savez_compressed(args.out/'decomposition.npz',time=time,parameters=parameters,component_residuals=components,
        phase_changes=phase_changes,linear_phase_controls=changes,actual_phase_error=actual,
        phase_profile_singular_values=singular)
    report.update(result='diagnosed_linear_sensitivity_no_qualification_change',components=rows,
        projected_decomposition_maximum_error=closure,nuisance_rank=int(nuisance_rank),phase_rank=int(phase_rank),
        profiled_phase_condition=float(singular[0]/max(singular[-1],1e-30)),
        total_linear_phase_p95_cycles=float(np.percentile(abs(total[interior]),95)),
        actual_phase_p95_cycles=float(np.percentile(abs(actual[interior]),95)),
        actual_vs_linear_correlation=float(np.corrcoef(actual[interior],total[interior])[0,1]),
        limits=['Known analytic decomposition is diagnostic only and is never used by the estimator',
            'Linear minimum-norm unweighted sensitivity ignores robust loss and active bounds; not a replacement fit or uncertainty certificate',
            'Dense positive and all original gates remain unchanged'])
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,1,figsize=(10,7),sharex=True)
    for i,label in enumerate(labels):
        centered=phase_changes[:,i]-np.median(phase_changes[interior,i])
        axes[0].plot(time[interior],centered[interior],label=label)
    axes[0].set_ylabel('Linear phase sensitivity (cycles)')
    axes[0].legend()
    axes[1].plot(time[interior],actual[interior],label='Actual bounded robust fit error')
    axes[1].plot(time[interior],total[interior],label='Total local unweighted prediction')
    axes[1].set(xlabel='Coarse-cycle coordinate',ylabel='Phase error (cycles)')
    axes[1].legend()
    fig.tight_layout()
    fig.savefig(args.out/'tangent_decomposition.png',dpi=150)
    plt.close(fig)
    report['plot_sha256']=sha(args.out/'tangent_decomposition.png')
    print(json.dumps(dict(result=report['result'],components=rows,condition=report['profiled_phase_condition'],
        phase_p95=report['total_linear_phase_p95_cycles'],correlation=report['actual_vs_linear_correlation'])),flush=True)
except Exception as exc:
    report.update(result='failed',error=repr(exc))
    raise
finally:
    save(args.out/'report.json',report)
