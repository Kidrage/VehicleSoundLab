"""Freeze both new source evidence and the modular C port with all attempts."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
from drive_evidence_v1.sources import sha
assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip()
for name in ('resonant_detail_c_v1','sport_acceleration_v1'):
    summary=json.loads((repo/'research'/f'{name}_summary.json').read_text(encoding='utf-8'))
    for path,digest in summary['evidence_sha256'].items():assert sha(a.workspace/path)==digest,path
out=a.workspace/'baselines/resonant_detail_c_v1';out.mkdir(exist_ok=False)
for name in ('resonant_detail_c_v1','sport_acceleration_v1'):
    shutil.copytree(a.workspace/'references/analysis'/name,out/'evidence'/name,ignore=shutil.ignore_patterns('__pycache__'))
commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
subprocess.run(['git','archive','--format=zip','--output='+str(out/'source.zip'),commit],cwd=repo,check=True)
with zipfile.ZipFile(out/'source.zip') as archive:assert archive.testzip() is None
files=[dict(path=p.relative_to(out).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(out.rglob('*')) if p.is_file()]
(out/'manifest.json').write_text(json.dumps(dict(schema='vsl.freeze/1',source_commit=commit,
    source_context_only=True,C_kernel_only=True,full_mixture_or_state_acceptance=False,files=files),ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
for row in files:assert sha(out/row['path'])==row['sha256']
print(json.dumps(dict(result='frozen',files=len(files),bytes=sum(v['bytes'] for v in files),commit=commit)))
