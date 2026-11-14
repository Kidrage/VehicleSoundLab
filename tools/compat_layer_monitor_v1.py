"""Check real old-schema identity with the preserved and new players."""
import argparse,shutil,subprocess
from pathlib import Path
from research_archive_v1 import save,sha
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
repo=Path(__file__).resolve().parents[1];evidence=Path('E:/VehicleSoundLab/references/analysis/layer_monitor_v1')
a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'compat_layer_monitor_v1.py')
take=a.out/'old_schema10.vslrun';shutil.copy2(Path('E:/VehicleSoundLab/baselines/fine_idle_drive_v1/evidence/device1/fine_idle_schema10.vslrun'),take)
r=dict(result='running',commands=[])
try:
    for kind,exe in [('old',evidence/'before/bin/VslAtlasTake_render.exe'),('new',repo/'build-layer-monitor-v1/bin/Release/VslAtlasTake_render.exe')]:
        dest=a.out/(kind+'.wav');argv=list(map(str,[exe,take,dest]));done=subprocess.run(argv,cwd=repo,capture_output=True,timeout=90)
        log=a.out/(kind+'.log');log.write_bytes(done.stdout+done.stderr)
        r['commands'].append(dict(argv=argv,exit_code=done.returncode,log=log.name,sha256=sha(log)))
        if kind=='old':
            assert done.returncode==0 and dest.exists()
            assert sha(dest)==sha(evidence/'before/old_schema10.wav')
            assert b'24060d7d761d429c' in done.stdout
            r['old_wav_sha256']=sha(dest)
        else:assert done.returncode!=0 and not dest.exists()
    r['result']='passed'
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
