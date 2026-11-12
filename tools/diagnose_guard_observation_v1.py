"""Fit one declared dense case after exposing measured boundary sidebands."""
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
from aperture_model_v1.checks import assess
from observed_topology_v1.fixtures import make
from envelope_resolution_v1.refine import geometry,transfer,estimate
from guard_observation_v1.geometry import extend
from guard_observation_v1.checks import controls
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
report=dict(schema='vsl.guard-observation-diagnosis/1',result='running',sources={},real_audio_read=False,
    real_source_permitted=False,qualification_changed=False,runtime_changed=False)
try:
    parent=load(args.validation/'report.json')
    assert parent['result']=='rejected'
    report['parent_report_sha256']=sha(args.validation/'report.json')
    settings_path=repo/'research/guard_observation_v1_plan.json'
    settings=load(settings_path)
    resolution=load(repo/settings['parent_plan'])
    topology=load(repo/resolution['parent_plan'])
    base=load(repo/topology['base_plan'])
    variant=load(repo/topology['minority_plan'])
    sources={Path(__file__),settings_path,repo/settings['parent_plan']}|set((repo/'tools/guard_observation_v1').glob('*.py'))|{repo/name for name in parent['sources']}|{
        repo/'tools/envelope_resolution_v1/refine.py',repo/'tools/envelope_resolution_v1/__init__.py'}
    for name,digest in parent['sources'].items():
        assert sha(repo/name)==sha(args.validation/'exact_sources'/name)==digest
    for source in sources:
        relative=source.relative_to(repo)
        target=args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target)
        report['sources'][relative.as_posix()]=sha(source)
    item=next(row for row in parent['cases'] if row['case']['id']==settings['diagnostic_case'])
    case=item['case']
    time,audio,truth,_=make(case,base)
    previous=load(args.validation/case['id']/'effective_plan.json')
    refined,report['amplitude_geometry']=geometry(previous)
    effective,report['guard_geometry']=extend(refined)
    save(args.out/'effective_plan.json',effective)
    saved=np.load(args.validation/case['id']/'fit.npz')
    assert np.array_equal(time,saved['time']) and np.array_equal(truth,saved['true_phase_correction'])
    with limit():
        report['controls']=controls(effective)
        initial,report['transfer']=transfer(time,previous,effective,variant,item['fit']['selected_indices'],saved['parameters'],
            resolution['minimum_envelope_transfer_accuracy'])
        print(json.dumps(dict(status='fitting_measured_boundary_guards',guard=report['guard_geometry'],controls=report['controls'])),flush=True)
        started=timer.perf_counter()
        parameters,phase,report['fit']=estimate(audio,time,effective,variant,item['fit']['selected_indices'],initial,settings['maximum_evaluations'])
        np.savez_compressed(args.out/'fit.npz',time=time,parameters=parameters,initial_parameters=initial,
            phase_correction=phase,true_phase_correction=truth)
        report['fit']['seconds']=timer.perf_counter()-started
        if report['fit']['observation_supported']:
            assessment,positions,oracle_positions=assess(audio,time,truth,phase,parameters,
                {**effective,'heldout_orders':base['heldout_orders']})
            report['assessment']=assessment
            np.savez_compressed(args.out/'coordinates.npz',positions=positions,oracle_positions=oracle_positions)
    report['original_assessment']=item['assessment']
    report['result']='dense_diagnostic_passed_not_full_qualification' if report.get('assessment',{}).get('qualified') else 'dense_diagnostic_rejected'
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from minority_phase_v1.model import MinorityModel
    original=MinorityModel(time,previous,variant,item['fit']['selected_indices']).samples(saved['parameters'])[1]
    fig,axis=plt.subplots(figsize=(10,4))
    interior=(time>=5)&(time<35)
    for correction,label in ((original,'Original candidate-complete observations'),(phase,'Measured boundary guards')):
        error=correction-truth
        error-=np.median(error[interior])
        axis.plot(time[interior],error[interior],label=label)
    for sign in (-1,1):
        axis.axhline(sign*effective['rules']['maximum_point_phase_p95_cycles'],color='black',linestyle='--',linewidth=.6)
    axis.set(xlabel='Coarse-cycle coordinate',ylabel='Phase error (cycles)',title='Dense topology: observe boundary phase sidebands')
    axis.legend()
    fig.tight_layout()
    fig.savefig(args.out/'guard_phase_comparison.png',dpi=150)
    plt.close(fig)
    report['plot_sha256']=sha(args.out/'guard_phase_comparison.png')
    print(json.dumps(dict(result=report['result'],fit=report['fit'],assessment=report.get('assessment'))),flush=True)
except Exception as exc:
    report.update(result='failed',error=repr(exc))
    raise
finally:
    save(args.out/'report.json',report)
