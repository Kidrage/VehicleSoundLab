"""Actual pedal-driven C renders, zero bypass, chunk/layout invariants and owned replay."""
import argparse, csv, shutil, subprocess, time
from pathlib import Path
from research_archive_v1 import load, save, sha
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','out','probe']:p.add_argument('--'+key,type=Path,required=True)
p.add_argument('--source-dir',type=Path,default=Path('experiments/stationary_recipe_v1'))
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',commands=[],cases=[],sources={})


def run(argv, label):
    start=time.perf_counter();done=subprocess.run(list(map(str,argv)),cwd=repo,capture_output=True,timeout=180)
    log=a.out/(label+'.log');log.write_bytes(done.stdout+done.stderr)
    r['commands'].append(dict(argv=list(map(str,argv)),exit_code=done.returncode,
                             seconds=time.perf_counter()-start,log=log.name,sha256=sha(log)))
    save(a.out/'report.json',r)
    assert done.returncode==0,log


try:
    for file in (repo/a.source_dir).iterdir():
        if file.is_file():
            dest=a.out/'exact_sources'/file.relative_to(repo);dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(file,dest);r['sources'][file.relative_to(repo).as_posix()]=sha(file)
    shutil.copy2(__file__,a.out/'executed_verify.py')
    shutil.copy2(a.probe,a.out/'probe.exe');probe=a.out/'probe.exe'
    original=a.workspace/'baselines/drive_catalog_v1/evidence/bin/VslAtlasTake_render.exe'
    shutil.copy2(original,a.out/'old_player.exe')
    for scenario in ['neutral','shifts']:
        for variant,channels,block in [(0,2,240),(1,2,240),(2,2,240),(2,12,240),(2,2,37)]:
            label=f'{scenario}_{variant}_{channels}_{block}';prefix=a.out/label
            run([probe,prefix,variant,scenario,channels,block],label)
            row=load(prefix.with_suffix('.json'));assert row['result']=='pass'
            replay=a.out/(label+'_replayed.wav')
            run([a.out/'old_player.exe',prefix.with_suffix('.vslrun'),replay,'--channels',channels],label+'_replay')
            assert sha(replay)==sha(prefix.with_suffix('.wav')),label
            row.update(label=label,whole_old_player_WAV_exact=True,WAV_sha256=sha(replay))
            r['cases'].append(row);save(a.out/'report.json',r)
            print(dict(label=label,active_frames=row['detail_supported_frames'],peak=row['peak'],replay_exact=True),flush=True)
        base=a.out/(scenario+'_0_2_240.wav')
        zero=a.out/(scenario+'_1_2_240.wav')
        assert sha(base)==sha(zero),'zero changes full output'
        full=a.out/(scenario+'_2_2_240.wav');irregular=a.out/(scenario+'_2_2_37.wav')
        assert sha(full)==sha(irregular),'chunk changes full output'
        labels=[f'{scenario}_{v}_{c}_{b}' for v,c,b in [(0,2,240),(1,2,240),(2,2,240),(2,12,240),(2,2,37)]]
        tables=[]
        for label in labels:
            with (a.out/(label+'.csv')).open(encoding='utf-8') as stream:table=list(csv.DictReader(stream))
            tables.append([{k:v for k,v in row.items() if k!='detail_support'} for row in table])
        assert all(table==tables[0] for table in tables),'driving changed'
        for suffix in ['_detail.wav','_layers.f32']:
            assert sha(a.out/(scenario+'_2_2_240'+suffix))==sha(a.out/(scenario+'_2_12_240'+suffix))
            assert sha(a.out/(scenario+'_2_2_240'+suffix))==sha(a.out/(scenario+'_2_2_37'+suffix))
        source=[c['source_hash'] for c in r['cases'] if c['label'].startswith(scenario+'_2_')]
        assert len(set(source))==1
    r.update(result='passed',zero_full_WAV_exact=True,chunk_full_WAV_exact=True,
             driver_unchanged=True,detail_and_dry_layers_2_12_exact=True,
             source_hash_2_12_exact=True,old_player_owned_replays=10,
             human_accepted=False,native_device_tested=False,actual_12_speakers_tested=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
