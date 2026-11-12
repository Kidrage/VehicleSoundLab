"""Train-only stereo covariance complexity selection with two-direction checks."""
import argparse
import csv
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
from stereo_field_v1.model import evaluate
from stereo_field_v1.controls import cases
from stereo_field_v1.oracle import check

args.out.mkdir(parents=True,exist_ok=False)
plan_path=repo/'research/stereo_field_v1_plan.json';plan=json.loads(plan_path.read_text(encoding='utf-8'))
paths=[Path(__file__),plan_path,repo/'tools/drive_evidence_v1/sources.py',repo/'tools/stereo_delay_v1/spectrum.py',
    *sorted((repo/'tools/stereo_field_v1').glob('*.py'))]
for path in paths:
    dest=args.out/'exact_sources'/path.relative_to(repo);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest)
r=dict(schema='vsl.stereo-field-analysis/1',result='running',controls=[],observations=[],input_sha256={},
    source_sha256={p.relative_to(repo).as_posix():sha(p) for p in paths},
    base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip())
(args.out/'metadata.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8',newline='\n')

def bound(root,name):
    manifest=root/'manifest.json';expected=next(x['sha256'] for x in json.loads(manifest.read_text(encoding='utf-8'))['files'] if x['path']==name)
    assert sha(root/name)==expected,name
    r['input_sha256'][str(root/name)]=expected;r['input_sha256'][str(manifest)]=sha(manifest)
    return root/name

try:
    for seed in plan['known_seeds']:
        for name,audio in cases(plan,seed):
            data=measure(audio,48000,plan['size'],plan['hop'],plan['bands'])
            dft=scalar_check(audio,data,48000,plan['size'],plan['hop'])
            assert dft<plan['tolerances']['scalar_DFT_relative']
            oracle=check(data,plan);rows=evaluate(data,plan)
            qualified=sum(x['bidirectional_gate_passed'] for x in rows)
            row=dict(seed=seed,name=name,bidirectional_bands=qualified,scalar_DFT_relative=dft,oracle=oracle,bands=rows)
            r['controls'].append(row)
            if name=='coloured_delay':assert qualified>=plan['known_coloured_minimum_bidirectional_bands'],(seed,name,qualified)
            else:assert qualified==0,(seed,name,qualified)
            print(json.dumps(dict(kind='known',seed=seed,name=name,qualified=qualified)),flush=True)
    baseline=args.workspace/'baselines/reference_audit_v1'
    old=json.loads(bound(baseline,'evidence/stereo_delay_v1/analysis1/report.json').read_text(encoding='utf-8'))
    assert old['result']=='pass'
    catalog=args.workspace/'references/segments_v1.json';r['input_sha256'][str(catalog)]=sha(catalog)
    assert sha(catalog)==old['catalog_sha256']
    for identity,source in old['sources'].items():
        for key in ('raw','master'):
            path=args.workspace/source[key];assert sha(path)==source[key+'_sha256'];r['input_sha256'][str(path)]=sha(path)
    for name in plan['cases']:
        record=next(x for x in old['observations'] if x['case']['name']==name)
        path=bound(baseline,'evidence/stereo_delay_v1/analysis1/'+name+'_observations.npz')
        with np.load(path) as archive:data={key:archive[key] for key in archive.files}
        oracle=check(data,plan);rows=evaluate(data,plan)
        r['observations'].append(dict(name=name,case=record['case'],perspective=record['perspective'],source=record['source'],
            blocks=len(data['left']),source_previous_DFT_error=record['scalar_dft_max_relative_error'],oracle=oracle,bands=rows))
        print(json.dumps(dict(kind='source',name=name,qualified=sum(x['bidirectional_gate_passed'] for x in rows))),flush=True)
    index=repo/'handoff/C文件索引.csv'
    with index.open(encoding='utf-8-sig',newline='') as f:current=list(csv.DictReader(f))
    assert len(current)==442
    for row in current:assert sha(repo/row['文件'])==row['SHA-256'],row['文件']
    r['input_sha256'][str(index)]=sha(index)
    r.update(result='diagnostics_completed',controls_gate=True,C_H_unchanged=442,C_changes=False,models_changed=False,
        driver_changes=False,human_accepted=False,limits=[plan['scope'],plan['split'],
            'More detailed recording covariance is not automatically a PSD additive residual relative to the existing DNA',
            'No synthesis or spatial/listening improvement has been established by this raw-data prediction experiment'])
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(args.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
