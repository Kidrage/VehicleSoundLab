"""Preserve current C ownership and original monitor/player binaries."""
import argparse,csv,hashlib,json,shutil,subprocess
from pathlib import Path
def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
out=a.workspace/'references/analysis/phase_texture_c_v1/before';out.mkdir(parents=True,exist_ok=False)
with (repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig') as stream:rows=list(csv.DictReader(stream))
assert len(rows)==472
for row in rows:
    name=row['文件'];assert sha(repo/name)==row['SHA-256'],name
    target=out/'sources'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,target)
shutil.copy2(repo/'handoff/C文件索引.csv',out/'C文件索引.csv')
for folder in ('handoff-build/bin/Release','build-startup-detail-host-v1/bin/Release'):
    for path in (repo/folder).glob('*.exe'):
        target=out/'bin'/Path(folder).parts[0]/path.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
shutil.copy2(__file__,out/'executed_prepare.py')
r=dict(result='prior_472_C_H_and_players_preserved',
       commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
       source_sha256={row['文件']:row['SHA-256'] for row in rows},
       binaries={str(x.relative_to(out)):sha(x) for x in (out/'bin').rglob('*.exe')})
(out/'report.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=r['result'],binaries=len(r['binaries']))))
