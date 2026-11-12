"""One declared finite-band amplitude candidate, using measured boundary guards."""
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
from observed_topology_v1.fixtures import make
from positive_band_envelope_v1.fit import initialize,estimate
from positive_band_envelope_v1.checks import controls
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
report=dict(schema='vsl.positive-band-envelope-diagnosis/1',result='running',sources={},real_audio_read=False,
    real_source_permitted=False,qualification_changed=False,runtime_changed=False)
try:
    parent=load(args.parent/'report.json')
    assert parent['result']=='dense_diagnostic_rejected'
    report['parent_report_sha256']=sha(args.parent/'report.json')
    settings_path=repo/'research/positive_band_envelope_v1_plan.json'
    settings=load(settings_path)
    guard=load(repo/settings['parent_plan'])
    resolution=load(repo/guard['parent_plan'])
    topology=load(repo/resolution['parent_plan'])
    base=load(repo/topology['base_plan'])
    variant=load(repo/topology['minority_plan'])
    sources={Path(__file__),settings_path}|set((repo/'tools/positive_band_envelope_v1').glob('*.py'))|{repo/name for name in parent['sources']}
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
        report['controls']=controls(time,plan,variant)
        initial,report['initialization']=initialize(time,plan,variant,selected,saved['parameters'])
        save(args.out/'initialization.json',report['initialization'])
        print(json.dumps(dict(status='fitting_positive_finite_band_amplitudes',initialization=report['initialization'],controls=report['controls'])),flush=True)
        started=timer.perf_counter()
        parameters,phase,report['fit']=estimate(audio,time,plan,variant,settings,selected,initial)
        np.savez_compressed(args.out/'fit.npz',time=time,parameters=parameters,initial_parameters=initial,
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
    fig,axis=plt.subplots(figsize=(10,4))
    interior=(time>=5)&(time<35)
    for correction,label in ((saved['phase_correction'],'Guard observations, cubic amplitudes'),(phase,'Guard observations, positive finite-band amplitudes')):
        error=correction-truth
        error-=np.median(error[interior])
        axis.plot(time[interior],error[interior],label=label)
    for sign in (-1,1):
        axis.axhline(sign*plan['rules']['maximum_point_phase_p95_cycles'],color='black',linestyle='--',linewidth=.6)
    axis.set(xlabel='Coarse-cycle coordinate',ylabel='Phase error (cycles)',title='Positive finite-band amplitudes, original phase freedom')
    axis.legend()
    fig.tight_layout()
    fig.savefig(args.out/'positive_band_phase_comparison.png',dpi=150)
    plt.close(fig)
    report['plot_sha256']=sha(args.out/'positive_band_phase_comparison.png')
    print(json.dumps(dict(result=report['result'],fit=report['fit'],assessment=report.get('assessment'))),flush=True)
except Exception as exc:
    report.update(result='failed',error=repr(exc))
    raise
finally:
    save(args.out/'report.json',report)
