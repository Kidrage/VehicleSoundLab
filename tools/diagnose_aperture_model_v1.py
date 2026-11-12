"""Separate an iteration cap from common-phase bias on the declared outlier case."""
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
parser.add_argument('--continued-from',type=Path,help='Reuse the verified terminal continuation; only rerun the oracle diagnostic')
args=parser.parse_args()
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
# Use the actual executed estimator, not a subsequently modified working copy.
sys.path.insert(0,str(args.validation/'exact_sources/tools'))
import numpy as np
import scipy
from scipy.optimize import least_squares
try:
    from threadpoolctl import threadpool_limits
    limit=lambda:threadpool_limits(limits=2)
except ImportError:
    limit=nullcontext
from drive_evidence_v1.sources import sha
from aperture_model_v1.fit import Model
from aperture_model_v1.fixtures import make
from aperture_model_v1.forward import real_rows
from aperture_model_v1.checks import assess


def save(path,value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


def robust_cost(residual,scale):
    return float(scale**2*np.sum(np.sqrt(1+(residual/scale)**2)-1))


args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.aperture-model-diagnosis/1',result='running',sources={},real_audio_read=False,
    qualification_changed=False,real_source_permitted=False,
    environment=dict(python=sys.version,numpy=np.__version__,scipy=scipy.__version__))
try:
    prior=json.loads((args.validation/'report.json').read_text(encoding='utf-8'))
    assert prior['result']=='rejected'
    report['validation_report_sha256']=sha(args.validation/'report.json')
    sources=[Path(__file__)]
    for name,digest in prior['sources'].items():
        source=args.validation/'exact_sources'/name
        assert sha(source)==digest
        target=args.out/'exact_sources'/name
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target)
        report['sources'][name]=digest
    target=args.out/'exact_sources/tools/diagnose_aperture_model_v1.py'
    shutil.copy2(Path(__file__),target)
    report['sources']['tools/diagnose_aperture_model_v1.py']=sha(Path(__file__))
    plan=json.loads((args.validation/'exact_sources/research/aperture_model_v1_plan.json').read_text(encoding='utf-8'))
    case=next(row for row in plan['cases'] if row['id']=='independent_phase_5')
    time,audio,truth=make(case,plan)
    original=np.load(args.validation/case['id']/'fit.npz')['parameters']
    model=Model(time,plan)
    target=real_rows(model.aperture.apply(audio[:,0]))
    start_phase=2*model.parts
    stop_phase=start_phase+model.phase_count
    lower=np.full(model.parameter_count,-plan['amplitude_control_bound'])
    upper=-lower
    lower[:start_phase]=-1
    upper[:start_phase]=1
    lower[start_phase:stop_phase]=-plan['phase_control_bound_cycles']
    upper[start_phase:stop_phase]=plan['phase_control_bound_cycles']
    scale=plan['soft_l1_scale']
    cache={}
    def calculate(x):
        if 'x' not in cache or not np.array_equal(cache['x'],x):
            value,jacobian=model.prediction(x,True)
            cache.update(x=x.copy(),residual=value-target,jacobian=jacobian)
        return cache
    started=timer.perf_counter()
    with limit():
        if args.continued_from:
            previous=json.loads((args.continued_from/'report.json').read_text(encoding='utf-8'))
            assert previous['result']=='diagnosed_no_qualification_change'
            assert previous['validation_report_sha256']==report['validation_report_sha256']
            for name,digest in prior['sources'].items():
                assert previous['sources'][name]==digest
            saved=np.load(args.continued_from/'diagnosis.npz')
            assert np.array_equal(saved['time'],time) and np.array_equal(saved['true_phase_correction'],truth)
            assert np.array_equal(saved['original_parameters'],original)
            continued_parameters=saved['continued_parameters']
            estimated=model.samples(continued_parameters)[1]
            assert np.array_equal(estimated,saved['continued_phase_correction'])
            assessment,positions,oracle_positions=assess(audio,time,truth,estimated,continued_parameters,plan)
            report['continued']=previous['continued']
            assert assessment==report['continued']['assessment']
            assert robust_cost(model.prediction(continued_parameters)-target,scale)==report['continued']['cost']
            report['continued_from']=dict(report_sha256=sha(args.continued_from/'report.json'),
                arrays_sha256=sha(args.continued_from/'diagnosis.npz'),exact_parameters_and_assessment=True)
        else:
            continued=least_squares(lambda x:calculate(x)['residual'].copy(),original,
                jac=lambda x:calculate(x)['jacobian'].copy(),bounds=(lower,upper),loss='soft_l1',f_scale=scale,
                x_scale='jac',max_nfev=300,ftol=1e-10,xtol=1e-10,gtol=1e-10)
            continued_parameters=continued.x
            _,estimated,_=model.samples(continued_parameters)
            assessment,positions,oracle_positions=assess(audio,time,truth,estimated,continued_parameters,plan)
            report['continued']=dict(evaluations=int(continued.nfev),success=bool(continued.success),
                message=continued.message,optimality=float(continued.optimality),assessment=assessment,
                cost=robust_cost(model.prediction(continued_parameters)-target,scale),
                original_cost=robust_cost(model.prediction(original)-target,scale),seconds=timer.perf_counter()-started)
        print(json.dumps(dict(continued=report['continued'])),flush=True)
        # An oracle is used ONLY for diagnosis, never to estimate or qualify phase.
        oracle_parameters=continued_parameters.copy()
        spline_truth=model.phase_basis@np.linalg.lstsq(model.phase_basis,truth,rcond=None)[0]
        # Freeze the exact analytic phase, independent of the inverse spline's
        # approximation error. Bases and projection remain on original time.
        oracle_model=Model(time,plan)
        oracle_model.time=time+truth
        oracle_parameters[start_phase:stop_phase]=0
        oracle_phase=truth.copy()
        free=np.r_[np.arange(start_phase),np.arange(stop_phase,model.parameter_count)]
        oracle_cache={}
        def oracle_calculate(x):
            if 'x' not in oracle_cache or not np.array_equal(oracle_cache['x'],x):
                parameters=oracle_parameters.copy()
                parameters[free]=x
                value,jacobian=oracle_model.prediction(parameters,True)
                oracle_cache.update(x=x.copy(),residual=value-target,jacobian=jacobian[:,free])
            return oracle_cache
        fixed=least_squares(lambda x:oracle_calculate(x)['residual'].copy(),oracle_parameters[free],
            jac=lambda x:oracle_calculate(x)['jacobian'].copy(),bounds=(lower[free],upper[free]),
            loss='soft_l1',f_scale=scale,x_scale='jac',max_nfev=150,ftol=1e-10,xtol=1e-10,gtol=1e-10)
        oracle_parameters[free]=fixed.x
    report['fixed_true_phase']=dict(evaluations=int(fixed.nfev),success=bool(fixed.success),message=fixed.message,
        maximum_phase_representation_error=float(abs(oracle_phase-truth).max()),
        unused_spline_maximum_error=float(abs(spline_truth-truth).max()),
        cost=robust_cost(oracle_model.prediction(oracle_parameters)-target,scale),
        uses_exact_analytic_phase=True,uses_known_truth=True,may_authorize_estimator=False)
    report['result']='diagnosed_no_qualification_change'
    report['conclusion']=dict(continued_phase_gate_passed=assessment['point_phase_p95_cycles']<=plan['rules']['maximum_point_phase_p95_cycles'],
        biased_solution_has_lower_objective=report['continued']['cost']<report['fixed_true_phase']['cost'],
        model_assumption_violated='One partial has independent phase motion, while the model permits only real positive envelope motion')
    np.savez_compressed(args.out/'diagnosis.npz',time=time,true_phase_correction=truth,
        original_parameters=original,continued_parameters=continued_parameters,continued_phase_correction=estimated,
        oracle_parameters=oracle_parameters,oracle_phase_correction=oracle_phase,positions=positions,oracle_positions=oracle_positions)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    original_phase=model.samples(original)[1]
    interior=(time>=5)&(time<35)
    fig,axes=plt.subplots(3,1,figsize=(10,8),sharex=True)
    axes[0].plot(time,truth,label='Known common phase',color='black',linewidth=1.4)
    axes[0].plot(time,original_phase-np.median((original_phase-truth)[interior]),label='80 evaluations (origin aligned)',alpha=.7)
    axes[0].plot(time,estimated-np.median((estimated-truth)[interior]),label='Continued (origin aligned)',alpha=.7)
    axes[0].set_ylabel('Correction (cycles)')
    axes[0].legend()
    for phase,label in ((original_phase,'80 evaluations'),(estimated,'Continued')):
        error=phase-truth
        error-=np.median(error[interior])
        axes[1].plot(time,error*1e3,label=label)
    threshold=plan['rules']['maximum_point_phase_p95_cycles']*1e3
    axes[1].axhline(threshold,color='black',linestyle='--',linewidth=.7)
    axes[1].axhline(-threshold,color='black',linestyle='--',linewidth=.7)
    axes[1].set_ylabel('Phase error (1e-3 cycles)')
    errors=[(phase-truth-np.median((phase-truth)[interior]))[interior]*1e3 for phase in (original_phase,estimated)]
    extent=max(threshold,max(float(abs(error).max()) for error in errors))*1.15
    axes[1].set_ylim(-extent,extent)
    axes[1].legend()
    coefficients=model.aperture.apply(audio[:,0]).reshape(len(model.aperture.starts),-1)
    prediction=model.aperture.apply(model.samples(continued_parameters)[0]).reshape(coefficients.shape)
    center=(model.aperture.starts+model.aperture.size/2)/plan['samples_per_cycle']
    image=axes[2].pcolormesh(center,model.aperture.orders,abs(coefficients-prediction).T,shading='nearest')
    axes[2].set_ylabel('Observed order')
    axes[2].set_xlabel('Coarse-cycle coordinate')
    fig.colorbar(image,ax=axes[2],label='Absolute complex residual')
    axes[0].set_title('One independently moving partial: common phase and model mismatch')
    for ax in axes:
        ax.set_xlim(5,35)
    fig.tight_layout()
    fig.savefig(args.out/'common_phase_bias.png',dpi=150)
    plt.close(fig)
    report['plot_sha256']=sha(args.out/'common_phase_bias.png')
    print(json.dumps(dict(result=report['result'],conclusion=report['conclusion'],fixed_true_phase=report['fixed_true_phase'])),flush=True)
except Exception as exc:
    report.update(result='failed',error=repr(exc))
    raise
finally:
    save(args.out/'report.json',report)
