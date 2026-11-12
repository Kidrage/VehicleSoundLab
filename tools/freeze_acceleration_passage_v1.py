"""Preserve exact current-C acceleration diagnostics without revising old freezes."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
from drive_evidence_v1.sources import sha

assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip()
summary = json.loads((repo/'research/acceleration_passage_v1_summary.json').read_text(encoding='utf-8'))
assert summary['result'] == 'existing_C_source_diagnostic_only'
for name,digest in summary['evidence_sha256'].items():
    assert sha(a.workspace/name) == digest
assert sha(repo/'voices/resonant_detail_v1/SELECTION.json') == summary['moving_selection_sha256']
out = a.workspace/'baselines/acceleration_passage_v1'
out.mkdir(exist_ok=False)
shutil.copytree(a.workspace/'references/analysis/acceleration_passage_v1',out/'evidence',
                ignore=shutil.ignore_patterns('__pycache__'))
commit = subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
subprocess.run(['git','archive','--format=zip','--output='+str(out/'source.zip'),commit],cwd=repo,check=True)
with zipfile.ZipFile(out/'source.zip') as archive:
    assert archive.testzip() is None
files = [dict(path=p.relative_to(out).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
         for p in sorted(out.rglob('*')) if p.is_file()]
(out/'manifest.json').write_text(json.dumps(dict(schema='vsl.freeze/1',source_commit=commit,
    files=files,new_timbre=False,new_C_H=False,human_accepted=False),ensure_ascii=False,indent=2)+'\n',
    encoding='utf-8',newline='\n')
for row in files:
    assert sha(out/row['path']) == row['sha256']
print(json.dumps(dict(result='frozen',files=len(files),bytes=sum(v['bytes'] for v in files),commit=commit)))
