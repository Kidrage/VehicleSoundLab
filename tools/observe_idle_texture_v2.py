"""Observe F2 training before choosing an idle texture recipe."""
import argparse,json,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
from drive_evidence_v1.sources import read,sha
from idle_texture_v2.observation import inventory,stereo,controls
a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',exact_sources={})
try:
    plan=json.loads((repo/'research/idle_texture_v2_plan.json').read_text(encoding='utf-8'))
    for path in [Path(__file__),repo/'research/idle_texture_v2_plan.json',
        repo/'tools/idle_texture_v2/observation.py',repo/'tools/idle_modal_v1/modal.py',
        repo/'tools/drive_evidence_v1/sources.py']:
        dest=a.out/'exact_sources'/path.relative_to(repo);dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,dest);r['exact_sources'][path.relative_to(repo).as_posix()]=sha(path)
    r['controls']=controls(plan)
    audio,provenance=read(a.workspace,plan['source'],'recording_power')
    train=audio[:3*48000]
    r.update(result='training_upper_structure_observed',provenance=provenance,
        stereo=stereo(train,plan),inventory=inventory(train,plan),holdout_used=False)
finally:
    (a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
print(json.dumps(r,ensure_ascii=False))
