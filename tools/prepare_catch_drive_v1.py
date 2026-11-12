"""Preserve the current schema4 player/source identity before opt-in integration."""
import argparse,csv,hashlib,json,shutil,subprocess
from pathlib import Path
def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
dirty=subprocess.check_output(['git','status','--porcelain'],cwd=repo,text=True).splitlines()
assert dirty in ([],['?? tools/prepare_catch_drive_v1.py']),dirty
with (repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig') as stream:rows=list(csv.DictReader(stream))
assert len(rows)==466
sources={}
for row in rows:
    name=row['文件'];assert sha(repo/name)==row['SHA-256'];sources[name]=row['SHA-256']
    dest=a.out/'sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest)
shutil.copy2(repo/'handoff/C文件索引.csv',a.out/'C文件索引.csv')
binary=repo/'build-startup-drive-v1/bin/Release';(a.out/'bin').mkdir()
for path in binary.glob('VslAtlas*.exe'):shutil.copy2(path,a.out/'bin'/path.name)
assert (a.out/'bin/VslAtlasTake_render.exe').exists()
shutil.copy2(__file__,a.out/'executed_prepare.py')
(a.out/'report.json').write_text(json.dumps(dict(result='schema4_sources_and_players_preserved',
    source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    C_H_count=466,source_sha256=sources,binary_sha256={x.name:sha(x) for x in (a.out/'bin').iterdir()}),indent=2)+'\n',encoding='utf-8',newline='\n')
print('Preserved466 C/H and schema4 players')
