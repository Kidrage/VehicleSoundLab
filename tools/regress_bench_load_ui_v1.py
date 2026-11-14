"""Check same-identity frozen replay of new UI load controls and nine voices."""
import argparse
from pathlib import Path
import shutil
import subprocess
from research_archive_v1 import load,save,sha

p=argparse.ArgumentParser(description=__doc__)
for key in ('workspace','build-dir','host','out'):
    p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args()
repo=Path(__file__).resolve().parents[1]
a.out.mkdir(parents=True,exist_ok=False)
shutil.copy2(__file__,a.out/'executed_regression.py')
parent=a.workspace/'baselines/catalog_decel_v1'
hashes={v['path']:v['sha256'] for v in load(parent/'manifest.json')['files']}
for label,source in [('frozen',parent/'evidence/bin/VslAtlasTake_render.exe'),
                     ('current',a.build_dir/'bin/Release/VslAtlasTake_render.exe')]:
    if label=='frozen':assert sha(source)==hashes[source.relative_to(parent).as_posix()]
    shutil.copy2(source,a.out/(label+'_player.exe'))
r=dict(result='running',commands=[],nine_preserved=[],bench_replays=[])


def run(player,take,dest,channels=2):
    argv=list(map(str,[a.out/(player+'_player.exe'),take,dest]))
    if channels!=2:argv+=['--channels',str(channels)]
    completed=subprocess.run(argv,cwd=repo,capture_output=True,timeout=90)
    log=a.out/f'command_{len(r["commands"]):02d}.log'
    log.write_bytes(completed.stdout+completed.stderr)
    r['commands'].append(dict(argv=argv,exit_code=completed.returncode,log=log.name,sha256=sha(log)))
    save(a.out/'report.json',r)
    assert completed.returncode==0,log
    import json
    result=json.loads(completed.stdout.decode('utf-8').strip())
    assert result['verified'] and result['channels']==channels
    return result


try:
    shutil.copytree(a.build_dir/'catalog-check',a.out/'new_render')
    for k in range(9):
        stem=f'voice_{k}'
        expected=load(a.out/'new_render'/(stem+'.json'))
        old=parent/'evidence/regress1/new_render'/(stem+'.wav')
        assert sha(old)==hashes[old.relative_to(parent).as_posix()]
        current=a.out/'new_render'/(stem+'.wav')
        assert sha(current)==sha(old)
        assert expected['owned_replay_PCM_exact'] and expected['driver_2_12_exact'] and expected['stems_2_12_exact']
        dest=a.out/(stem+'_frozen.wav')
        info=run('frozen',a.out/'new_render'/(stem+'.vslrun'),dest)
        assert sha(dest)==sha(current)
        assert info['render_id']==expected['render_id']==load(parent/'validation.json')['render_id_after']
        r['nine_preserved'].append(dict(selection=k,whole_WAV_exact=True,frozen_replay_exact=True,render_id=info['render_id']))
        save(a.out/'report.json',r)
        print('PASS unchanged voice / frozen replay',k,flush=True)
    ui=load(a.host/'ui.json')
    assert ui['result']=='pass' and ui['bench_load']['frames']==240123
    bench=load(a.host/'ui.json.bench.json')
    assert [v['load'] for v in bench['events']]==[.8,-.6,.25,0]
    assert all(v['mode']==0 and v['brake']==0 for v in bench['events'])  # VSL_BENCH
    assert bench['events'][0]['frame']==0 and all(x['frame']<y['frame'] for x,y in zip(bench['events'],bench['events'][1:]))
    for player,channels in [('current',2),('frozen',2),('current',12)]:
        dest=a.out/f'bench_{player}_{channels}.wav'
        info=run(player,a.host/'ui.json.bench.vslrun',dest,channels)
        assert info['frames']==bench['frames'] and info['render_id']==bench['render_id']
        assert info['source_hash']==bench['source_hash']
        if channels==2:assert info['audio_hash']==bench['audio_hash'] and sha(dest)==sha(a.host/'ui.json.bench.wav')
        r['bench_replays'].append(dict(player=player,channels=channels,frames=info['frames'],
            actual_native_WAV_exact=channels==2,source_hash_exact=True,render_id=info['render_id']))
        save(a.out/'report.json',r)
    r.update(result='passed',renderer_identity_unchanged=True,schema=10,controls=32,
             no_new_DSP_or_source_fit=True,physical_load_calibration=False,hearing=False)
except Exception as exc:
    r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
