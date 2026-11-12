"""Separate approximation bias from warm-start bias at the declared resolution."""
import argparse
from contextlib import nullcontext
import json
from pathlib import Path
import shutil
import sys
import time as timer

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--diagnosis',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
from scipy.optimize import least_squares,lsq_linear
from drive_evidence_v1.sources import sha
from aperture_model_v1.fit import Model,estimate
from aperture_model_v1.checks import assess
from aperture_model_v1.forward import real_rows
from minority_phase_v1.model import MinorityModel
from observed_topology_v1.fixtures import make
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


def cost(residual,scale):
    return float(scale**2*np.sum(np.sqrt(1+(residual/scale)**2)-1))


args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.envelope-bias-diagnosis/1',result='running',sources={},real_audio_read=False,
    real_source_permitted=False,qualification_changed=False)
try:
    parent=load(args.diagnosis/'report.json')
    assert parent['result']=='dense_diagnostic_rejected'
    report['parent_report_sha256']=sha(args.diagnosis/'report.json')
    sources={Path(__file__),repo/'tools/envelope_resolution_v1/checks.py'}|{repo/name for name in parent['sources']}
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
    variant=load(repo/topology['minority_plan'])
    case=next(row for row in topology['added_cases'] if row['id']==settings['diagnostic_case'])
    time,audio,truth,_=make(case,base)
    plan=load(args.diagnosis/'effective_plan.json')
    previous={**plan,'amplitude_knot_cycles':parent['geometry']['previous_spacing']}
    model=Model(time,plan)
    target=real_rows(model.aperture.apply(audio[:,0]))
    scale=plan['soft_l1_scale']
    with limit():
        report['controls']=controls(time,previous,variant,settings['minimum_envelope_transfer_accuracy'])
        # This branch is a diagnostic oracle only; it is not imported by the
        # estimator and its parameters are never used to initialize it.
        oracle=Model(time,plan)
        oracle.time=time+truth
        parameters=np.zeros(model.parameter_count)
        for index,order in enumerate(plan['source_orders']):
            amplitude=(.045 if order in (2,3,5,7) else .022*(1+.15*np.cos(index*.31)))*case['gain']
            envelope=1+.09*np.sin(2*np.pi*(.018+.0004*index)*time+.19*index)
            phi=.37*order+.013*order*order
            parameters[index]=amplitude*envelope[0]*np.cos(phi)
            parameters[index+model.parts]=-amplitude*envelope[0]*np.sin(phi)
            beta=lsq_linear(model.envelope_basis,envelope/envelope[0]-1,
                bounds=(-plan['amplitude_control_bound'],plan['amplitude_control_bound']),tol=1e-12).x
            start=2*model.parts+model.phase_count+index*model.envelope_count
            parameters[start:start+model.envelope_count]=beta
        free=np.r_[np.arange(2*model.parts),np.arange(2*model.parts+model.phase_count,model.parameter_count)]
        lower,upper=MinorityModel(time,plan,variant,[]).bounds(plan,variant)
        cache={}
        def calculate(x):
            if 'x' not in cache or not np.array_equal(cache['x'],x):
                full=parameters.copy()
                full[free]=x
                value,jacobian=oracle.prediction(full,True)
                cache.update(x=x.copy(),residual=value-target,jacobian=jacobian[:,free])
            return cache
        fixed=least_squares(lambda x:calculate(x)['residual'].copy(),parameters[free],
            jac=lambda x:calculate(x)['jacobian'].copy(),bounds=(lower[free],upper[free]),
            loss='soft_l1',f_scale=scale,x_scale='jac',max_nfev=80,ftol=1e-10,xtol=1e-10,gtol=1e-10)
        parameters[free]=fixed.x
        np.savez_compressed(args.out/'fixed_true_phase.npz',parameters=parameters,time=time,true_phase_correction=truth)
        report['fixed_true_phase']=dict(cost=cost(oracle.prediction(parameters)-target,scale),evaluations=int(fixed.nfev),
            success=bool(fixed.success),message=fixed.message,uses_oracle=True,may_initialize_estimator=False)
        save(args.out/'checkpoint.json',report)
        print(json.dumps(dict(fixed_true_phase=report['fixed_true_phase'])),flush=True)
        started=timer.perf_counter()
        # The same actual estimator is now started from its standard observed
        # constant-line LS solution, not from saved biased phase or oracle.
        fresh_phase,fresh_report,fresh_parameters=estimate(audio,time,plan)
        np.savez_compressed(args.out/'fresh_fit.npz',parameters=fresh_parameters,time=time,
            phase_correction=fresh_phase,true_phase_correction=truth)
        report['fresh']=dict(fit=fresh_report,seconds=timer.perf_counter()-started,
            cost=cost(model.prediction(fresh_parameters)-target,scale),uses_oracle=False)
        save(args.out/'checkpoint.json',report)
        if np.min(np.diff(time+fresh_phase))>0:
            assessment,positions,oracle_positions=assess(audio,time,truth,fresh_phase,fresh_parameters,
                {**plan,'heldout_orders':base['heldout_orders']})
            report['fresh']['assessment']=assessment
            np.savez_compressed(args.out/'coordinates.npz',positions=positions,oracle_positions=oracle_positions)
    saved=np.load(args.diagnosis/'fit.npz')
    warm_cost=cost(model.prediction(saved['parameters'])-target,scale)
    report['comparison']=dict(warm_phase_p95=parent['assessment']['point_phase_p95_cycles'],warm_cost=warm_cost,
        fresh_phase_p95=report['fresh'].get('assessment',{}).get('point_phase_p95_cycles'),
        fresh_cost=report['fresh']['cost'],fixed_true_phase_cost=report['fixed_true_phase']['cost'],
        global_optimality_or_nonidentifiability_proven=False)
    report['result']='diagnosed_no_qualification_change'
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axis=plt.subplots(figsize=(10,4))
    interior=(time>=5)&(time<35)
    for phase,label in ((saved['phase_correction'],'Nested warm start120'),(fresh_phase,'Fresh observed LS start80')):
        error=phase-truth
        error-=np.median(error[interior])
        axis.plot(time[interior],error[interior],label=label)
    for sign in (-1,1):
        axis.axhline(sign*plan['rules']['maximum_point_phase_p95_cycles'],color='black',linestyle='--',linewidth=.6)
    axis.set(xlabel='Coarse-cycle coordinate',ylabel='Phase error (cycles)',title='Same real-envelope model: initialization diagnostic')
    axis.legend()
    fig.tight_layout()
    fig.savefig(args.out/'initialization_comparison.png',dpi=150)
    plt.close(fig)
    report['plot_sha256']=sha(args.out/'initialization_comparison.png')
    print(json.dumps(dict(result=report['result'],comparison=report['comparison'])),flush=True)
except Exception as exc:
    report.update(result='failed',error=repr(exc))
    raise
finally:
    save(args.out/'report.json',report)
