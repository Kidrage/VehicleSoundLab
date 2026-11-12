"""Preserve source ownership and schema5 players before adding an optional host recipe."""
import argparse,csv,hashlib,json,shutil,subprocess
from pathlib import Path
def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
assert subprocess.check_output(['git','status','--porcelain'],cwd=repo,text=True).splitlines() in (
    [],['?? tools/prepare_startup_detail_host_v1.py'])
a.out.mkdir(parents=True,exist_ok=False)
with (repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig') as stream:rows=list(csv.DictReader(stream))
assert len(rows)==469
hashes={}
for row in rows:
    name=row['文件'];assert sha(repo/name)==row['SHA-256'],name
    dest=a.out/'sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest);hashes[name]=sha(repo/name)
shutil.copy2(repo/'handoff/C文件索引.csv',a.out/'C文件索引.csv')
(a.out/'bin').mkdir()
for path in (repo/'build-catch-drive-v1/bin/Release').glob('VslAtlas*.exe'):shutil.copy2(path,a.out/'bin'/path.name)
shutil.copy2(__file__,a.out/'executed_prepare.py')
(a.out/'report.json').write_text(json.dumps(dict(result='schema5_sources_players_preserved',C_H_count=469,
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),source_sha256=hashes,
    binary_sha256={x.name:sha(x) for x in (a.out/'bin').iterdir()}),indent=2)+'\n',encoding='utf-8',newline='\n')
print('Preserved469 C/H and schema5 players')
