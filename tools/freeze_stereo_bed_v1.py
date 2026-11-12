"""Freeze integrated stereo-bed routing and retain previous schema2 executables."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True);args=p.parse_args()
repo=Path(__file__).resolve().parents[1];assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip()
r=json.loads((repo/'research/stereo_bed_v1_summary.json').read_text(encoding='utf-8'));root=args.workspace/'references/analysis/stereo_bed_v1'
for name,digest in r['current_source_sha256'].items():assert sha(repo/name)==digest,name
for name,digest in r['evidence_sha256'].items():assert sha(root/name)==digest,name
assert sha(repo/'handoff/C文件索引.csv')==r['c_index_sha256']
out=args.workspace/'baselines/stereo_bed_v1';out.mkdir(exist_ok=False)
shutil.copytree(root,out/'evidence',ignore=shutil.ignore_patterns('__pycache__'));(out/'docs').mkdir()
for name in ['research/立体声声床接入V1.md','research/stereo_bed_v1_summary.json','handoff/算法说明.md','handoff/C模块与接口.md',
             'handoff/研究续接.md','handoff/C文件索引.csv','AGENTS.md']:
    shutil.copy2(repo/name,out/'docs'/Path(name).name)
revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
subprocess.run(['git','archive','--format=zip','--output='+str(out/'source.zip'),revision],cwd=repo,check=True)
with zipfile.ZipFile(out/'source.zip') as z:assert z.testzip() is None
files=[dict(path=x.relative_to(out).as_posix(),bytes=x.stat().st_size,sha256=sha(x)) for x in sorted(out.rglob('*')) if x.is_file()]
(out/'manifest.json').write_text(json.dumps(dict(schema='vsl.stereo-bed-freeze/1',source_commit=revision,human_accepted=False,
    hardware12_checked=False,files=files),ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
for row in files:assert sha(out/row['path'])==row['sha256']
print(json.dumps(dict(path=str(out),commit=revision,files=len(files),bytes=sum(x['bytes'] for x in files))))
