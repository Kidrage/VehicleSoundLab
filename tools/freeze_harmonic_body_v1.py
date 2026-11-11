"""Freeze the runnable LF driver, all evidence and a committed source archive."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
args=parser.parse_args()
repo=Path(__file__).resolve().parents[1]
def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip()
summary=repo/'research/harmonic_body_v1_summary.json'
r=json.loads(summary.read_text(encoding='utf-8'))
assert r['result']=='pass' and r['tests']==34 and not r['human_accepted']
root=args.workspace/'references/analysis/harmonic_body_v1'
assert str(root)==r['evidence_root']
for name,expected in r['source_sha256'].items():assert sha(repo/name)==expected,name
for name,expected in r['evidence_sha256'].items():assert sha(root/name)==expected,name
for name,expected in r['binaries_sha256'].items():assert sha(repo/'handoff-build/bin/Release'/name)==expected,name
assert sha(repo/'handoff/C文件索引.csv')==r['c_index_sha256']
revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
out=args.workspace/'baselines/harmonic_body_v1';out.mkdir(exist_ok=False)
shutil.copytree(root,out/'evidence',ignore=shutil.ignore_patterns('__pycache__'))
for name in ('exterior_anchors_v1','cabin_anchors_v1','residual_atlas_v1'):
    shutil.copytree(repo/'voices'/name,out/'voices'/name)
(out/'bin').mkdir()
for name in r['binaries_sha256']:shutil.copy2(repo/'handoff-build/bin/Release'/name,out/'bin'/name)
(out/'docs').mkdir()
for p in (summary,repo/'research/驾驶低频分层V1.md',repo/'handoff/C模块与接口.md',repo/'handoff/C文件索引.csv'):
    shutil.copy2(p,out/'docs'/p.name)
subprocess.run(['git','archive','--format=zip','--output='+str(out/'source.zip'),revision],cwd=repo,check=True)
with zipfile.ZipFile(out/'source.zip') as archive:assert archive.testzip() is None
(out/'Run-DNA-Drive.cmd').write_bytes(b'@echo off\r\ncd /d "%~dp0"\r\nstart "" "bin\\VslAtlasMonitor.exe"\r\n')
(out/'README.txt').write_text('驾驶低频分层V1\n提交：'+revision+'\n'
    '运行Run-DNA-Drive.cmd；默认停止／未点火／细节0%／低频分层0%。\n'
    'evidence/review/index.html提供相同主音量的0%／100%／低频独奏。\n'
    '这是现有OSC的互补低频声路与独立工况包络，未新增物理超低频／NVH声源。\n'
    '34项回归、17条旧音轨一致、2/12通道源及短时静音设备/UI验证通过；音色待听评。\n'
    '全部原始批准素材／历史档案沿用既有交接Release，未包含于本增量。\n',encoding='utf-8')
files=[dict(path=p.relative_to(out).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
    for p in sorted(out.rglob('*')) if p.is_file()]
(out/'manifest.json').write_text(json.dumps(dict(schema='vsl.harmonic-body-freeze/1',source_commit=revision,
    human_accepted=False,summary_sha256=sha(summary),files=files),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for row in files:assert sha(out/row['path'])==row['sha256']
print(json.dumps(dict(path=str(out),commit=revision,files=len(files),bytes=sum(row['bytes'] for row in files)),ensure_ascii=False))
