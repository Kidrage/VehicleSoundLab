"""One measured-gap envelope refinement of the frozen dense failure."""
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
from drive_evidence_v1.sources import sha
from aperture_model_v1.checks import assess,controls
from observed_topology_v1.fixtures import make
from envelope_resolution_v1.refine import geometry,transfer,estimate
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
report=dict(schema='vsl.envelope-resolution-diagnosis/1',result='running',sources={},real_audio_read=False,
    real_source_permitted=False,qualification_changed=False,runtime_changed=False)
try:
    validation=load(args.validation/'report.json')
    assert validation['result']=='rejected'
    settings_path=repo/'research/envelope_resolution_v1_plan.json'
    settings=load(settings_path)
    topology=load(repo/settings['parent_plan'])
    base=load(repo/topology['base_plan'])
    variant=load(repo/topology['minority_plan'])
    sources={Path(__file__),settings_path,repo/'tools/envelope_resolution_v1/refine.py',
        repo/'tools/envelope_resolution_v1/__init__.py'}|{repo/name for name in validation['sources']}
    for name,digest in validation['sources'].items():
        assert sha(repo/name)==sha(args.validation/'exact_sources'/name)==digest
    for source in sources:
        relative=source.relative_to(repo)
        target=args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target)
        report['sources'][relative.as_posix()]=sha(source)
    report['validation_report_sha256']=sha(args.validation/'report.json')
    item=next(row for row in validation['cases'] if row['case']['id']==settings['diagnostic_case'])
    assert not item['passed']
    previous=load(args.validation/item['case']['id']/'effective_plan.json')
    current,report['geometry']=geometry(previous)
    save(args.out/'effective_plan.json',current)
    report['effective_plan_sha256']=sha(args.out/'effective_plan.json')
    time,audio,truth,_=make(item['case'],base)
    saved=np.load(args.validation/item['case']['id']/'fit.npz')
    assert np.array_equal(time,saved['time']) and np.array_equal(truth,saved['true_phase_correction'])
    selected=item['fit']['selected_indices']
    with limit():
        report['controls']=controls(current)
        assert report['controls']['passed']
        initial,report['transfer']=transfer(time,previous,current,variant,selected,saved['parameters'],
            settings['minimum_envelope_transfer_accuracy'])
        print(json.dumps(dict(status='refining',geometry=report['geometry'],transfer=report['transfer'])),flush=True)
        started=timer.perf_counter()
        parameters,phase,report['fit']=estimate(audio,time,current,variant,selected,initial,settings['maximum_evaluations'])
        np.savez_compressed(args.out/'fit.npz',time=time,parameters=parameters,initial_parameters=initial,
            phase_correction=phase,true_phase_correction=truth)
        report['fit']['seconds']=timer.perf_counter()-started
        if report['fit']['observation_supported']:
            assessment,positions,oracle_positions=assess(audio,time,truth,phase,parameters,
                {**current,'heldout_orders':base['heldout_orders']})
            report['assessment']=assessment
            np.savez_compressed(args.out/'coordinates.npz',positions=positions,oracle_positions=oracle_positions)
    report['original_assessment']=item['assessment']
    report['result']='dense_diagnostic_passed_not_full_qualification' if report.get('assessment',{}).get('qualified') else 'dense_diagnostic_rejected'
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from minority_phase_v1.model import MinorityModel
    before=MinorityModel(time,previous,variant,selected).samples(saved['parameters'])[1]
    interior=(time>=5)&(time<35)
    fig,axis=plt.subplots(figsize=(10,4))
    for epsilon,label in ((before,'Original envelope spacing10'),(phase,'Observed-gap envelope spacing5')):
        error=epsilon-truth
        error-=np.median(error[interior])
        axis.plot(time[interior],error[interior],label=label)
    threshold=current['rules']['maximum_point_phase_p95_cycles']
    for sign in (-1,1):
        axis.axhline(sign*threshold,color='black',linestyle='--',linewidth=.6)
    axis.set(xlabel='Coarse-cycle coordinate',ylabel='Phase error (cycles)',title='Dense observed topology: real-envelope resolution')
    axis.legend()
    fig.tight_layout()
    fig.savefig(args.out/'phase_comparison.png',dpi=150)
    plt.close(fig)
    report['plot_sha256']=sha(args.out/'phase_comparison.png')
    print(json.dumps(dict(result=report['result'],fit=report['fit'],assessment=report.get('assessment'))),flush=True)
except Exception as exc:
    report.update(result='failed',error=repr(exc))
    raise
finally:
    save(args.out/'report.json',report)
