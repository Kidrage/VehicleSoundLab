"""Separate stereo covariance axes with unchanged aggregate and new component gates."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
from drive_evidence_v1.sources import sha
from stereo_delay_v1.spectrum import measure,scalar_check
from stereo_field_v1.controls import cases
from stereo_field_v1.components import evaluate

args.out.mkdir(parents=True,exist_ok=False)
plan_path=repo/'research/stereo_components_v1_plan.json';extension=json.loads(plan_path.read_text(encoding='utf-8'))
parent=repo/extension['extends'];plan={**json.loads(parent.read_text(encoding='utf-8')),**extension}
root=args.workspace/'references/analysis/stereo_field_v1';previous_path=root/'analysis1/report.json'
previous=json.loads(previous_path.read_text(encoding='utf-8'));assert previous['result']=='diagnostics_completed'
paths=[Path(__file__),plan_path,parent,repo/'tools/drive_evidence_v1/sources.py',repo/'tools/stereo_delay_v1/spectrum.py',
    *sorted((repo/'tools/stereo_field_v1').glob('*.py'))]
for path in paths:
    target=args.out/'exact_sources'/path.relative_to(repo);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
r=dict(schema='vsl.stereo-component-analysis/1',result='running',controls=[],observations=[],
    source_sha256={p.relative_to(repo).as_posix():sha(p) for p in paths},
    input_sha256={str(previous_path):sha(previous_path)},
    base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip())
(args.out/'metadata.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8',newline='\n')
try:
    for seed in plan['known_seeds']:
        for name,audio in cases(plan,seed):
            data=measure(audio,48000,plan['size'],plan['hop'],plan['bands'])
            dft=scalar_check(audio,data,48000,plan['size'],plan['hop']);assert dft<plan['tolerances']['scalar_DFT_relative']
            rows=evaluate(data,plan);qualified=sum(row['bidirectional_gate_passed'] for row in rows)
            r['controls'].append(dict(seed=seed,name=name,bidirectional_bands=qualified,scalar_DFT_relative=dft,bands=rows))
            if name=='coloured_delay':assert qualified>=plan['known_coloured_minimum_bidirectional_bands'],(seed,name,qualified)
            else:assert qualified==0,(seed,name,qualified)
            print(json.dumps(dict(kind='known',seed=seed,name=name,qualified=qualified)),flush=True)
    for observation in previous['observations']:
        path=args.workspace/'baselines/reference_audit_v1/evidence/stereo_delay_v1/analysis1'/(observation['name']+'_observations.npz')
        assert sha(path)==previous['input_sha256'][str(path)];r['input_sha256'][str(path)]=sha(path)
        with np.load(path) as archive:data={key:archive[key] for key in archive.files}
        rows=evaluate(data,plan)
        r['observations'].append(dict(name=observation['name'],case=observation['case'],perspective=observation['perspective'],
            source=observation['source'],blocks=len(data['left']),bands=rows))
        print(json.dumps(dict(kind='source',name=observation['name'],qualified=sum(row['bidirectional_gate_passed'] for row in rows))),flush=True)
    r.update(result='diagnostics_completed',C_changes=False,models_changed=False,human_accepted=False,
        limits=[plan['scope'],plan['fit'],'The same previously observed time blocks support exploration; no independent recording or end-to-end source qualification',
            'Individual component gates concern this covariance metric, not stereo audibility or physical source identity'])
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(args.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
