"""Compare preserved PCM and verify strict renderer separation without rewriting takes."""
import argparse,shutil,subprocess,time
from pathlib import Path
from research_archive_v1 import load,save,sha
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--out',type=Path,required=True);p.add_argument('--build-dir',type=Path,required=True);a=p.parse_args()
repo=Path(__file__).resolve().parents[1]
old=Path('E:/VehicleSoundLab/baselines/catalog_bridge_v1/evidence')
current=a.build_dir/'catalog-check';a.out.mkdir(parents=True,exist_ok=False)
shutil.copy2(__file__,a.out/Path(__file__).name)
shutil.copy2(old/'bin/VslAtlasTake_render.exe',a.out/'old_player.exe')
shutil.copy2(a.build_dir/'bin/Release/VslAtlasTake_render.exe',a.out/'new_player.exe')
shutil.copytree(current,a.out/'new_render')
r=dict(result='running',commands=[],old_cases=[],new_cases=[],crossing=[])
def run(player,take,dest,label,accept):
    argv=list(map(str,[player,take,dest]));start=time.perf_counter()
    done=subprocess.run(argv,cwd=repo,capture_output=True,timeout=90)
    log=a.out/(label+'.log');log.write_bytes(done.stdout+done.stderr)
    r['commands'].append(dict(argv=argv,exit_code=done.returncode,seconds=time.perf_counter()-start,log=log.name,sha256=sha(log)))
    save(a.out/'report.json',r)
    if accept:
        assert done.returncode==0 and b'"verified":true' in done.stdout,(label,done.returncode)
        return done.stdout
    assert done.returncode==3 and not dest.exists() and b'Render failed' in done.stderr,label
try:
    old_ids=set();new_ids=set()
    for k in range(9):
        new=load(current/f'voice_{k}.json');new_ids.add(new['render_id'])
        wav=a.out/f'new_replay_{k}.wav'
        data=run(a.out/'new_player.exe',current/f'voice_{k}.vslrun',wav,f'new_replay_{k}',True)
        assert sha(wav)==sha(current/f'voice_{k}.wav')
        assert new['audio_hash'].encode() in data and new['source_hash'].encode() in data
        r['new_cases'].append(dict(selection=k,whole_WAV_exact=True,owned_irregular_replay=new['owned_replay_PCM_exact'],
                                   renderer=new['render_id'],wav_sha256=sha(wav)))
        run(a.out/'old_player.exe',current/f'voice_{k}.vslrun',a.out/f'old_on_new_{k}.wav',f'old_on_new_{k}',False)
        if k<8:
            prior=old/f'regress1/new_render/voice_{k}'
            meta=load(prior.with_suffix('.json'));old_ids.add(meta['render_id'])
            assert sha(current/f'voice_{k}.wav')==sha(prior.with_suffix('.wav')),(k,'original PCM changed')
            assert new['audio_hash']==meta['audio_hash'] and new['source_hash']==meta['source_hash']
            dest=a.out/f'old_replay_{k}.wav'
            run(a.out/'old_player.exe',prior.with_suffix('.vslrun'),dest,f'old_replay_{k}',True)
            assert sha(dest)==sha(prior.with_suffix('.wav'))
            run(a.out/'new_player.exe',prior.with_suffix('.vslrun'),a.out/f'new_on_old_{k}.wav',f'new_on_old_{k}',False)
            r['old_cases'].append(dict(selection=k,new_PCM_exact=True,source_hash_exact=True,frozen_player_whole_WAV_exact=True))
            r['crossing'].append(dict(selection=k,old_rejects_new=True,new_rejects_old=True))
        else:r['crossing'].append(dict(selection=k,old_rejects_new=True))
        save(a.out/'report.json',r);print('PASS preserved PCM / owned replay / strict identities:',k,flush=True)
    assert len(old_ids)==len(new_ids)==1 and old_ids.isdisjoint(new_ids)
    r.update(result='passed',old_render_id=old_ids.pop(),new_render_id=new_ids.pop(),schema=10,controls=32)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
