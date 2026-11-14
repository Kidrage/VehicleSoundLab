"""Replay all new catalog takes with the preserved pre-catalog player."""
import argparse,shutil,subprocess,time
from pathlib import Path
from research_archive_v1 import save,load,sha
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
old=Path('E:/VehicleSoundLab/baselines/layer_monitor_v1/evidence/bin/VslAtlasTake_render.exe')
current=repo/'build-catalog-drive-v1/catalog-check'
shutil.copy2(old,a.out/'old_player.exe');shutil.copy2(__file__,a.out/'regress_catalog_drive_v1.py')
shutil.copytree(current,a.out/'new_render');r=dict(result='running',commands=[],cases=[])
try:
    for k in range(7):
        take=a.out/'new_render'/f'voice_{k}.vslrun';expected=load(current/f'voice_{k}.json');dest=a.out/f'old_voice_{k}.wav'
        argv=list(map(str,[a.out/'old_player.exe',take,dest]));start=time.perf_counter();done=subprocess.run(argv,cwd=repo,capture_output=True,timeout=90)
        log=a.out/f'old_voice_{k}.log';log.write_bytes(done.stdout+done.stderr)
        r['commands'].append(dict(argv=argv,exit_code=done.returncode,seconds=time.perf_counter()-start,log=log.name,sha256=sha(log)))
        assert done.returncode==0,(k,log)
        assert expected['audio_hash'].encode() in done.stdout and expected['source_hash'].encode() in done.stdout
        assert sha(dest)==sha(current/f'voice_{k}.wav'),k
        r['cases'].append(dict(selection=k,frames=expected['frames'],audio_hash=expected['audio_hash'],source_hash=expected['source_hash'],
            render_id=expected['render_id'],wav_sha256=sha(dest),full_old_new_wav_exact=True))
        save(a.out/'report.json',r);print('PASS original player, catalog voice',k,flush=True)
    assert len({c['render_id'] for c in r['cases']})==1;r['result']='passed'
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
