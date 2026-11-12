"""Diagnose the declared dense-topology failure without changing qualification."""
import argparse
from contextlib import nullcontext
import json
from pathlib import Path
import shutil
import sys
import time as timer

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--validation',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
from scipy.optimize import least_squares,lsq_linear
from drive_evidence_v1.sources import sha
from aperture_model_v1.fit import Model
from aperture_model_v1.forward import real_rows
from aperture_model_v1.checks import assess
from observed_topology_v1.fixtures import make
from minority_phase_v1.model import MinorityModel
try:
    from threadpoolctl import threadpool_limits
    limit=lambda:threadpool_limits(limits=2)
except ImportError:
    limit=nullcontext


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path,value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


def cost(residual,scale):
    return float(scale**2*np.sum(np.sqrt(1+(residual/scale)**2)-1))


args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.observed-dense-diagnosis/1',result='running',sources={},
    real_audio_read=False,qualification_changed=False,real_source_permitted=False)
try:
    validation=load(args.validation/'report.json')
    assert validation['result']=='rejected'
    report['validation_report_sha256']=sha(args.validation/'report.json')
    sources={Path(__file__)}|{repo/name for name in validation['sources']}
    for name,digest in validation['sources'].items():
        assert sha(repo/name)==sha(args.validation/'exact_sources'/name)==digest
    for source in sources:
        relative=source.relative_to(repo)
        target=args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target)
        report['sources'][relative.as_posix()]=sha(source)
    settings=load(repo/'research/observed_topology_v1_plan.json')
    base=load(repo/settings['base_plan'])
    variant=load(repo/settings['minority_plan'])
    item=next(row for row in validation['cases'] if row['case']['id']=='unknown_thirty_six')
    assert not item['passed'] and not item['fit']['selected_indices']
    case=item['case']
    time,audio,truth,_=make(case,base)
    plan=load(args.validation/case['id']/'effective_plan.json')
    original=np.load(args.validation/case['id']/'fit.npz')['parameters']
    model=Model(time,plan)
    target=real_rows(model.aperture.apply(audio[:,0]))
    lower,upper=MinorityModel(time,plan,variant,[]).bounds(plan,variant)
    scale=plan['soft_l1_scale']
    cache={}
    def calculate(x):
        if 'x' not in cache or not np.array_equal(cache['x'],x):
            value,jacobian=model.prediction(x,True)
            cache.update(x=x.copy(),residual=value-target,jacobian=jacobian)
        return cache
    started=timer.perf_counter()
    with limit():
        continued=least_squares(lambda x:calculate(x)['residual'].copy(),original,
            jac=lambda x:calculate(x)['jacobian'].copy(),bounds=(lower,upper),loss='soft_l1',f_scale=scale,
            x_scale='jac',max_nfev=300,ftol=1e-10,xtol=1e-10,gtol=1e-10)
        phase=model.samples(continued.x)[1]
        assessment_plan={**plan,'heldout_orders':base['heldout_orders']}
        assessment,positions,oracle_positions=assess(audio,time,truth,phase,continued.x,assessment_plan)
        report['continued']=dict(evaluations=int(continued.nfev),success=bool(continued.success),message=continued.message,
            optimality=float(continued.optimality),cost=cost(model.prediction(continued.x)-target,scale),
            original_cost=cost(model.prediction(original)-target,scale),assessment=assessment,seconds=timer.perf_counter()-started)
        print(json.dumps(dict(continued=report['continued'])),flush=True)
        # Known analytic phase/amplitude initialize a diagnostic oracle only.
        # The actual estimator has never received these fixture parameters.
        oracle_model=Model(time,plan)
        oracle_model.time=time+truth
        oracle_parameters=np.zeros(model.parameter_count)
        envelope_truth=[]
        for index,order in enumerate(plan['source_orders']):
            amplitude=(.045 if order in (2,3,5,7) else .022*(1+.15*np.cos(index*.31)))*case['gain']
            envelope=1+.09*np.sin(2*np.pi*(.018+.0004*index)*time+.19*index)
            phi=.37*order+.013*order*order
            oracle_parameters[index]=amplitude*envelope[0]*np.cos(phi)
            oracle_parameters[index+model.parts]=-amplitude*envelope[0]*np.sin(phi)
            beta=lsq_linear(model.envelope_basis,envelope/envelope[0]-1,
                bounds=(-plan['amplitude_control_bound'],plan['amplitude_control_bound']),tol=1e-12).x
            start=2*model.parts+model.phase_count+index*model.envelope_count
            oracle_parameters[start:start+model.envelope_count]=beta
            envelope_truth.append(amplitude*envelope)
        phase_start=2*model.parts
        phase_stop=phase_start+model.phase_count
        free=np.r_[np.arange(phase_start),np.arange(phase_stop,model.parameter_count)]
        oracle_cache={}
        initial_oracle_cost=cost(oracle_model.prediction(oracle_parameters)-target,scale)
        def oracle_calculate(x):
            if 'x' not in oracle_cache or not np.array_equal(oracle_cache['x'],x):
                parameters=oracle_parameters.copy()
                parameters[free]=x
                value,jacobian=oracle_model.prediction(parameters,True)
                oracle_cache.update(x=x.copy(),residual=value-target,jacobian=jacobian[:,free])
            return oracle_cache
        fixed=least_squares(lambda x:oracle_calculate(x)['residual'].copy(),oracle_parameters[free],
            jac=lambda x:oracle_calculate(x)['jacobian'].copy(),bounds=(lower[free],upper[free]),
            loss='soft_l1',f_scale=scale,x_scale='jac',max_nfev=80,ftol=1e-10,xtol=1e-10,gtol=1e-10)
        oracle_parameters[free]=fixed.x
    report['fixed_true_phase']=dict(evaluations=int(fixed.nfev),success=bool(fixed.success),message=fixed.message,
        initial_known_envelope_cost=initial_oracle_cost,cost=cost(oracle_model.prediction(oracle_parameters)-target,scale),
        uses_exact_analytic_phase=True,uses_known_amplitude_for_initialization=True,may_authorize_estimator=False)
    np.savez_compressed(args.out/'diagnosis.npz',time=time,true_phase_correction=truth,
        original_parameters=original,continued_parameters=continued.x,continued_phase_correction=phase,
        oracle_parameters=oracle_parameters,true_partial_amplitude=np.asarray(envelope_truth),
        positions=positions,oracle_positions=oracle_positions)
    report['result']='diagnosed_dense_failure_no_qualification_change'
    report['comparison']=dict(continued_phase_gate_passed=assessment['point_phase_p95_cycles']<=plan['rules']['maximum_point_phase_p95_cycles'],
        continued_cost_lower_than_fixed_true=report['continued']['cost']<report['fixed_true_phase']['cost'],
        global_optimum_or_identifiability_proven=False)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,1,figsize=(10,7),sharex=True)
    interior=(time>=5)&(time<35)
    for parameters,label in ((original,'Original80 evaluations'),(continued.x,'300 additional evaluations')):
        correction=model.samples(parameters)[1]
        error=correction-truth
        error-=np.median(error[interior])
        axes[0].plot(time[interior],error[interior]*1e3,label=label)
    threshold=plan['rules']['maximum_point_phase_p95_cycles']*1e3
    for sign in (-1,1):
        axes[0].axhline(sign*threshold,color='black',linestyle='--',linewidth=.6)
    axes[0].set_ylabel('Phase error (1e-3 coarse cycles)')
    axes[0].set_title('Dense36-line case: continuation and amplitude coupling')
    axes[0].legend()
    index=model.parts-1
    axes[1].plot(time,np.asarray(envelope_truth)[index],label='Known partial amplitude',color='black')
    for parameters,label in ((original,'Original estimate'),(continued.x,'Continued estimate')):
        envelope=model.samples(parameters)[2][:,index]
        amplitude=np.hypot(parameters[index],parameters[index+model.parts])*envelope
        axes[1].plot(time,amplitude,label=label)
    oracle_envelope=oracle_model.samples(oracle_parameters)[2][:,index]
    axes[1].plot(time,np.hypot(oracle_parameters[index],oracle_parameters[index+model.parts])*oracle_envelope,
        label='Fixed exact phase diagnostic',linestyle='--')
    axes[1].set(xlabel='Coarse-cycle coordinate',ylabel='Amplitude',xlim=(5,35))
    axes[1].legend()
    fig.tight_layout()
    fig.savefig(args.out/'dense_phase_diagnosis.png',dpi=150)
    plt.close(fig)
    report['plot_sha256']=sha(args.out/'dense_phase_diagnosis.png')
    print(json.dumps(dict(result=report['result'],comparison=report['comparison'],fixed_true_phase=report['fixed_true_phase'])),flush=True)
except Exception as exc:
    report.update(result='failed',error=repr(exc))
    raise
finally:
    save(args.out/'report.json',report)
