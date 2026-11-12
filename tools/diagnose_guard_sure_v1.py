"""One fixed composition of measured guards and automatic amplitude roughness."""
import argparse
from contextlib import nullcontext
import json
from pathlib import Path
import shutil
import sys
import time as timer

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--parent',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
from drive_evidence_v1.sources import sha
from aperture_model_v1.checks import assess
from aperture_model_v1.forward import real_rows
from minority_phase_v1.model import MinorityModel
from observed_topology_v1.fixtures import make
from smooth_envelope_v1.penalty import build
from smooth_envelope_v1.select_sure import select
from smooth_envelope_v1.fit_selected import estimate
from smooth_envelope_v1.sure_checks import controls as risk_controls
from smooth_envelope_v1.covariance_checks import controls as covariance_controls
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
report=dict(schema='vsl.guard-sure-diagnosis/1',result='running',sources={},real_audio_read=False,
    real_source_permitted=False,qualification_changed=False,runtime_changed=False)
try:
    parent=load(args.parent/'report.json')
    assert parent['result']=='dense_diagnostic_rejected'
    report['parent_report_sha256']=sha(args.parent/'report.json')
    settings_path=repo/'research/guard_sure_v1_plan.json'
    settings=load(settings_path)
    guard=load(repo/settings['guard_plan'])
    smoothing=load(repo/settings['smooth_plan'])
    roughness=load(repo/smoothing['parent_plan'])
    resolution=load(repo/guard['parent_plan'])
    topology=load(repo/resolution['parent_plan'])
    base=load(repo/topology['base_plan'])
    variant=load(repo/topology['minority_plan'])
    sources={Path(__file__),settings_path,repo/settings['guard_plan'],repo/settings['smooth_plan'],
        repo/smoothing['parent_plan']}|set((repo/'tools/smooth_envelope_v1').glob('*.py'))|{repo/name for name in parent['sources']}
    for name,digest in parent['sources'].items():
        assert sha(repo/name)==sha(args.parent/'exact_sources'/name)==digest
    for source in sources:
        relative=source.relative_to(repo)
        target=args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target)
        report['sources'][relative.as_posix()]=sha(source)
    case=next(row for row in topology['added_cases'] if row['id']==settings['diagnostic_case'])
    time,audio,truth,_=make(case,base)
    plan=load(args.parent/'effective_plan.json')
    save(args.out/'effective_plan.json',plan)
    saved=np.load(args.parent/'fit.npz')
    assert np.array_equal(time,saved['time']) and np.array_equal(truth,saved['true_phase_correction'])
    selected=parent['fit']['selected_indices']
    with limit():
        report['risk_controls']=risk_controls(plan)
        report['covariance_controls']=covariance_controls(plan)
        model=MinorityModel(time,plan,variant,selected)
        target=real_rows(model.aperture.apply(audio[:,0]))
        old_prior,evidence=build(model,saved['parameters'],target,plan,roughness)
        proxy=evidence['projection_residual_scale_proxy']
        assert proxy>0
        prior,report['selection']=select(model,saved['parameters'],target,old_prior/proxy)
        save(args.out/'selection.json',report['selection'])
        np.savez_compressed(args.out/'prior.npz',matrix=prior)
        print(json.dumps(dict(status='fitting_guard_and_selected_amplitude_prior',weight=report['selection']['weight'],
            white_noise_proxy=report['selection']['source_white_noise_standard_deviation_proxy'],
            orthogonal_noise_trace=report['selection']['orthogonal_noise_trace'])),flush=True)
        started=timer.perf_counter()
        parameters,phase,report['fit']=estimate(audio,time,plan,variant,settings,selected,saved['parameters'],prior,report['selection'])
        np.savez_compressed(args.out/'fit.npz',time=time,parameters=parameters,initial_parameters=saved['parameters'],
            phase_correction=phase,true_phase_correction=truth)
        report['fit']['seconds']=timer.perf_counter()-started
        if report['fit']['observation_supported']:
            assessment,positions,oracle_positions=assess(audio,time,truth,phase,parameters,
                {**plan,'heldout_orders':base['heldout_orders']})
            report['assessment']=assessment
            np.savez_compressed(args.out/'coordinates.npz',positions=positions,oracle_positions=oracle_positions)
    report['original_assessment']=parent['assessment']
    report['result']='dense_diagnostic_passed_not_full_qualification' if report.get('assessment',{}).get('qualified') else 'dense_diagnostic_rejected'
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,1,figsize=(10,7))
    interior=(time>=5)&(time<35)
    for correction,label in ((saved['phase_correction'],'Boundary guards only'),(phase,'Guards plus selected amplitude prior')):
        error=correction-truth
        error-=np.median(error[interior])
        axes[0].plot(time[interior],error[interior],label=label)
    for sign in (-1,1):
        axes[0].axhline(sign*plan['rules']['maximum_point_phase_p95_cycles'],color='black',linestyle='--',linewidth=.6)
    axes[0].set(xlabel='Coarse-cycle coordinate',ylabel='Phase error (cycles)')
    axes[0].legend()
    chosen=report['selection']['log_weight']
    curve=[row for row in report['selection']['risk_curve'] if abs(row['log_weight']-chosen)<=6]
    axes[1].plot([row['log_weight'] for row in curve],[row['risk'] for row in curve])
    axes[1].axvline(chosen,color='black',linestyle='--')
    axes[1].set(xlabel='Log amplitude-prior weight (near selected value)',ylabel='Local predictive risk')
    fig.tight_layout()
    fig.savefig(args.out/'guard_sure_phase_comparison.png',dpi=150)
    plt.close(fig)
    report['plot_sha256']=sha(args.out/'guard_sure_phase_comparison.png')
    print(json.dumps(dict(result=report['result'],fit=report['fit'],assessment=report.get('assessment'))),flush=True)
except Exception as exc:
    report.update(result='failed',error=repr(exc))
    raise
finally:
    save(args.out/'report.json',report)
