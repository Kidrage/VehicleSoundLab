"""Keep current schema7 players and a verified real-device take before edits."""
import argparse,hashlib,json,shutil,subprocess
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
shutil.copy2(__file__,a.out/'executed_snapshot.py')
r=dict(schema='vsl.full-recipe-before/1',result='running',source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip())
try:
    files=subprocess.check_output(['git','ls-files'],cwd=repo,text=True).splitlines()
    r['C_H']={name:sha(repo/name) for name in files if Path(name).suffix.lower() in ('.c','.h')}
    assert len(r['C_H'])==530
    r['voices']={name:sha(repo/name) for name in files if name.startswith('voices/')}
    binaries=repo/'build-stereo-drive-v1/bin/Release'
    for name in ('VslAtlasDrive_probe','VslAtlasTake_render','VslAtlasMonitor','VslDriveResonance_device','VslResonantSource_probe'):
        shutil.copy2(binaries/(name+'.exe'),a.out/(name+'.exe'))
    shutil.copy2(repo/'build-stereo-drive-v1/atlas-take/Release/atlas_take_build.h',a.out/'atlas_take_build.h')
    take=a.workspace/'references/analysis/stereo_drive_v1/verify3/stereo_pedals/detail_schema7.vslrun'
    shutil.copy2(take,a.out/'device_schema7.vslrun')
    command=[str(a.out/'VslAtlasTake_render.exe'),str(a.out/'device_schema7.vslrun'),str(a.out/'device_schema7.wav')]
    done=subprocess.run(command,cwd=repo,capture_output=True,timeout=120)
    (a.out/'old_player.log').write_bytes(done.stdout+done.stderr)
    assert done.returncode==0 and b'"verified":true' in done.stdout
    r.update(result='verified_old_player_preserved',command=command)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:
    r['files']={v.relative_to(a.out).as_posix():sha(v) for v in a.out.rglob('*') if v.is_file()}
    (a.out/'report.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(result=r['result'],C_H=len(r['C_H']))),flush=True)
