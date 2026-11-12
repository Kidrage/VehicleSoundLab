"""Preserve the schema6 player, native host and an actual owned device take."""
import argparse, csv, hashlib, json, shutil, subprocess
from pathlib import Path
p = argparse.ArgumentParser(description=__doc__)
for name in ('workspace', 'build', 'out'):
    p.add_argument('--'+name, type=Path, required=True)
a = p.parse_args(); repo = Path(__file__).resolve().parents[1]
a.out.mkdir(parents=True, exist_ok=False)
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
r = dict(result='running', commands=[], source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip())
def run(argv):
    proc = subprocess.run(list(map(str,argv)),cwd=repo,capture_output=True,timeout=120)
    log=a.out/f'command_{len(r["commands"]):02}.log'; log.write_bytes(proc.stdout+proc.stderr)
    r['commands'].append(dict(argv=list(map(str,argv)),exit=proc.returncode,log=log.name))
    assert proc.returncode==0, str(log)
try:
    index=repo/'handoff/C文件索引.csv'; shutil.copy2(index,a.out/'prior_C_index.csv')
    with index.open(encoding='utf-8-sig') as f: rows=list(csv.DictReader(f))
    assert len(rows)==529
    for row in rows: assert sha(repo/row['文件'])==row['SHA-256'],row['文件']
    r['C_H']={row['文件']:row['SHA-256'] for row in rows}
    for name in ('VslAtlasTake_render','VslAtlasDrive_probe','VslDriveResonance_device','VslAtlasMonitor'):
        shutil.copy2(a.build/'bin/Release'/f'{name}.exe',a.out/f'{name}.exe')
    shutil.copy2(a.build/'atlas-take/Release/atlas_take_build.h',a.out/'atlas_take_build.h')
    device=a.out/'device'; device.mkdir()
    run([a.out/'VslDriveResonance_device.exe',device])
    take=device/'detail_schema6.vslrun'
    assert int.from_bytes(take.read_bytes()[8:12],'little')==6
    run([a.out/'VslAtlasTake_render.exe',take,device/'export_2.wav'])
    r['device']=json.loads((device/'device.json').read_text())
    assert r['device']['result']=='pass'
    r['result']='before_snapshot_pass'
finally:
    r['files']={v.relative_to(a.out).as_posix():sha(v) for v in a.out.rglob('*') if v.is_file()}
    (a.out/'snapshot.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(result=r['result'],C_H=len(r['C_H']))))
