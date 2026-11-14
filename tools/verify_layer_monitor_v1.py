"""Compare the protected old renderer, then exercise native muted monitoring."""
import argparse,shutil,subprocess,time
from pathlib import Path
from research_archive_v1 import save,load,sha
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];base=Path('E:/VehicleSoundLab/references/analysis/layer_monitor_v1')
a.out.mkdir(parents=True,exist_ok=False);build=repo/'build-layer-monitor-v1/bin/Release'
r=dict(result='running',commands=[],canonical={},dry_source_2_12_exact={})
shutil.copy2(__file__,a.out/'verify_layer_monitor_v1.py')
try:
    old=base/'old_build2/probe';new=repo/'build-layer-monitor-v1/probe-check'
    assert load(base/'old_build2/report.json')['result']=='passed'
    assert load(base/'focused2/report.json')['result']=='passed'
    shutil.copytree(new,a.out/'canonical_new')
    for kind in ['base','fine']:
        for channels in [2,12]:
            tag=f'{kind}{channels}';o=load(old/(tag+'_report.json'));n=load(new/(tag+'_report.json'))
            assert o['audio_hash']==n['audio_hash'] and o['source_hash']==n['source_hash'],tag
            for suffix in ['_pcm.bin','_trace.csv']:
                assert (old/(tag+suffix)).read_bytes()==(new/(tag+suffix)).read_bytes(),tag+suffix
            assert o['render_id']!=n['render_id'] and n['maximum_stem_sum_error']<2e-7
            r['canonical'][tag]=dict(audio_hash=n['audio_hash'],source_hash=n['source_hash'],pcm_sha256=sha(new/(tag+'_pcm.bin')),
                trace_sha256=sha(new/(tag+'_trace.csv')),stem_sum_error=n['maximum_stem_sum_error'],layer_energy=n['layer_energy'])
        assert (new/(kind+'2_layers.bin')).read_bytes()==(new/(kind+'12_layers.bin')).read_bytes()
        assert load(new/(kind+'2_report.json'))['source_hash']==load(new/(kind+'12_report.json'))['source_hash']
        r['dry_source_2_12_exact'][kind]=True
    save(a.out/'report.json',r)
    (a.out/'device').mkdir()
    commands=[[build/'layer_monitor_device.exe',a.out/'device'],
              [build/'VslAtlasMonitor.exe','--fine-idle-study','--muted','--ui-check',a.out/'ui.json']]
    for command in commands:
        argv=list(map(str,command));started=time.perf_counter();done=subprocess.run(argv,cwd=repo,capture_output=True,timeout=90)
        log=a.out/('command_%02d.log'%len(r['commands']));log.write_bytes(done.stdout+done.stderr)
        row=dict(argv=argv,exit_code=done.returncode,seconds=time.perf_counter()-started,log=log.name,sha256=sha(log));r['commands'].append(row)
        save(a.out/'report.json',r);print(row,flush=True)
        if done.returncode:raise RuntimeError(str(log))
    assert load(a.out/'device/device.json')['result']=='pass' and load(a.out/'ui.json')['result']=='pass'
    r['result']='passed'
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
