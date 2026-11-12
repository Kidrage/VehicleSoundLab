"""One observed constrained joint direction after the alternating solver."""
import argparse
import json
from pathlib import Path
import shutil
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--parent',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
from drive_evidence_v1.sources import sha
from absolute_amplitude_v1.model import AbsoluteModel
from absolute_amplitude_v1.direction import step
from aperture_model_v1.forward import real_rows
from aperture_model_v1.checks import assess
from observed_topology_v1.fixtures import make


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.absolute-amplitude-joint-direction/1',result='running',sources={},
    real_audio_read=False,real_source_permitted=False,qualification_changed=False)
try:
    parent=load(args.parent/'report.json')
    assert parent['result']=='dense_diagnostic_rejected'
    report['parent_report_sha256']=sha(args.parent/'report.json')
    sources={Path(__file__),repo/'tools/absolute_amplitude_v1/direction.py'}|{repo/name for name in parent['sources']}
    for name,digest in parent['sources'].items():
        assert sha(repo/name)==sha(args.parent/'exact_sources'/name)==digest
    for source in sources:
        relative=source.relative_to(repo)
        target=args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target)
        report['sources'][relative.as_posix()]=sha(source)
    topology=load(repo/'research/observed_topology_v1_plan.json')
    base=load(repo/topology['base_plan'])
    variant=load(repo/topology['minority_plan'])
    case=next(row for row in topology['added_cases'] if row['id']=='unknown_thirty_six')
    time,audio,truth,_=make(case,base)
    saved=np.load(args.parent/'fit.npz')
    assert np.array_equal(time,saved['time']) and np.array_equal(truth,saved['true_phase_correction'])
    plan=load(args.parent/'effective_plan.json')
    model=AbsoluteModel(time,plan,variant,parent['fit']['selected_indices'])
    outer,controls=model.unpack(saved['parameters'])
    target=real_rows(model.original.aperture.apply(audio[:,0]))
    (new_outer,new_controls),report['direction'],direction=step(model,target,outer,controls,plan['soft_l1_scale'])
    parameters=model.pack(new_outer,new_controls)
    _,phase,_=model.original.samples(parameters)
    np.savez_compressed(args.out/'step.npz',time=time,parameters=parameters,phase_correction=phase,
        true_phase_correction=truth,outer_direction=direction[:len(outer)],absolute_direction=direction[len(outer):])
    report['assessment'],_,_=assess(audio,time,truth,phase,parameters,{**plan,'heldout_orders':base['heldout_orders']})
    report.update(result='joint_direction_diagnostic_no_qualification',original_assessment=parent['assessment'])
    print(json.dumps(dict(result=report['result'],direction=report['direction'],assessment=report['assessment'])),flush=True)
except Exception as exc:
    report.update(result='failed',error=repr(exc))
    raise
finally:
    (args.out/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
