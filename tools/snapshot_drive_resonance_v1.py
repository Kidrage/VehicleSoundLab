"""Preserve the currently runnable driver/player before its optional detail API changes."""
import argparse,csv,hashlib,json,shutil,subprocess
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
r=dict(source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),C_H={},commands=[])
index=repo/'handoff/C文件索引.csv';shutil.copy2(index,a.out/'prior_C_index.csv')
with index.open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
assert len(rows)==511
for row in rows:assert sha(repo/row['文件'])==row['SHA-256'];r['C_H'][row['文件']]=row['SHA-256']
for name in ('VslAtlasDrive_probe','VslAtlasTake_render','VslAtlasTake_device_checks','VslAtlasMonitor'):
    source=repo/'build-resonant-monitor-v1/bin/Release'/f'{name}.exe';shutil.copy2(source,a.out/source.name)
shutil.copy2(repo/'build-resonant-monitor-v1/atlas-take/Release/atlas_take_build.h',a.out/'atlas_take_build.h')
def run(argv):
    proc=subprocess.run(list(map(str,argv)),cwd=repo,capture_output=True,timeout=180)
    path=a.out/f'command_{len(r["commands"]):02}.log';path.write_bytes(proc.stdout+proc.stderr)
    r['commands'].append(dict(argv=list(map(str,argv)),exit_code=proc.returncode,log=path.name,sha256=sha(path)))
    assert proc.returncode==0,(argv,path);print(json.dumps(dict(done=list(map(str,argv[:2])))),flush=True)
try:
    run([a.out/'VslAtlasTake_device_checks.exe',a.out/'old_schema5.vslrun','--stereo-bed','--startup-detail'])
    run([a.out/'VslAtlasTake_render.exe',a.out/'old_schema5.vslrun',a.out/'old_schema5.wav'])
    base=a.workspace/'references/analysis/stereo_bed_v1/before/report.json'
    r['cases']=json.loads(base.read_text())['cases'];renders=a.out/'renders';renders.mkdir()
    for case in r['cases']:
        opts=case['options']+(['--stereo-bed','1'] if case['name'].startswith('E_') else [])
        run([a.out/'VslAtlasDrive_probe.exe',*case['models'][:2],renders/case['name'],*opts])
    r['result']='before_snapshot_pass'
except Exception as e:r.update(result='failed',error=repr(e));raise
finally:
    r['files']={v.relative_to(a.out).as_posix():sha(v) for v in a.out.rglob('*') if v.is_file()}
    (a.out/'snapshot.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
