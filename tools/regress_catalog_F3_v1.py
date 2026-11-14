"""Check ten owned recipes, preserve nine prior WAVs and strict take identities."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
from research_archive_v1 import load, save, sha

p = argparse.ArgumentParser(description=__doc__)
for key in ('workspace', 'build-dir', 'host', 'out'):
    p.add_argument('--' + key, type=Path, required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
parent = a.workspace / 'baselines/catalog_decel_v1'
hashes = {v['path']: v['sha256'] for v in load(parent / 'manifest.json')['files']}
a.out.mkdir(parents=True, exist_ok=False)
shutil.copy2(__file__, a.out / 'executed_regression.py')
for name, source in [('old', parent / 'evidence/bin/VslAtlasTake_render.exe'),
                     ('new', a.build_dir / 'bin/Release/VslAtlasTake_render.exe')]:
    if name == 'old':
        assert sha(source) == hashes[source.relative_to(parent).as_posix()]
    shutil.copy2(source, a.out / (name + '_player.exe'))
shutil.copytree(a.build_dir / 'catalog-check', a.out / 'new_render')
r = dict(result='running', commands=[], old_cases=[], new_cases=[], crossing=[], bench=[])


def run(player, take, dest, accept=True, channels=2):
    argv = list(map(str, [a.out / (player + '_player.exe'), take, dest]))
    if channels != 2:
        argv += ['--channels', str(channels)]
    done = subprocess.run(argv, cwd=repo, capture_output=True, timeout=90)
    log = a.out / ('command_%02d.log' % len(r['commands']))
    log.write_bytes(done.stdout + done.stderr)
    r['commands'].append(dict(argv=argv, exit_code=done.returncode, log=log.name, sha256=sha(log)))
    save(a.out / 'report.json', r)
    if not accept:
        assert done.returncode == 3 and not dest.exists() and b'Render failed' in done.stderr, log
        return None
    assert done.returncode == 0, log
    info = json.loads(done.stdout.decode('utf-8').strip())
    assert info['verified'] and info['channels'] == channels
    return info


try:
    old_ids, new_ids = set(), set()
    for k in range(10):
        stem = 'voice_%d' % k
        base = a.out / 'new_render' / stem
        meta = load(base.with_suffix('.json'))
        assert meta['owned_replay_PCM_exact'] and meta['driver_2_12_exact'] and meta['stems_2_12_exact']
        new_ids.add(meta['render_id'])
        dest = a.out / (stem + '_new.wav')
        info = run('new', base.with_suffix('.vslrun'), dest)
        assert sha(dest) == sha(base.with_suffix('.wav'))
        assert info['audio_hash'] == meta['audio_hash'] and info['source_hash'] == meta['source_hash']
        r['new_cases'].append(dict(selection=k, owned_replay_exact=True, whole_WAV_exact=True))
        run('old', base.with_suffix('.vslrun'), a.out / (stem + '_old_on_new.wav'), False)
        if k < 9:
            prior = parent / 'evidence/regress1/new_render' / stem
            for suffix in ('.wav', '.vslrun', '.json'):
                path = prior.with_suffix(suffix)
                assert sha(path) == hashes[path.relative_to(parent).as_posix()]
            old_meta = load(prior.with_suffix('.json'))
            old_ids.add(old_meta['render_id'])
            assert sha(base.with_suffix('.wav')) == sha(prior.with_suffix('.wav'))
            assert meta['audio_hash'] == old_meta['audio_hash'] and meta['source_hash'] == old_meta['source_hash']
            dest = a.out / (stem + '_frozen.wav')
            info = run('old', prior.with_suffix('.vslrun'), dest)
            assert sha(dest) == sha(prior.with_suffix('.wav'))
            run('new', prior.with_suffix('.vslrun'), a.out / (stem + '_new_on_old.wav'), False)
            r['old_cases'].append(dict(selection=k, PCM_and_source_exact=True, frozen_old_replay_exact=True))
        r['crossing'].append(dict(selection=k, old_rejects_new=True, new_rejects_old=k < 9))
        save(a.out / 'report.json', r)
        print('PASS catalog replay/preserved PCM/strict identities', k, flush=True)
    assert len(old_ids) == len(new_ids) == 1 and old_ids.isdisjoint(new_ids)
    # A new F3 take is independent of external voice paths when replayed;
    # its owned parameters are already serialized by the catalog render check.
    meta = load(a.out / 'new_render/voice_9.json')
    info = run('new', a.out / 'new_render/voice_9.vslrun', a.out / 'F3_12.wav', channels=12)
    assert info['source_hash'] == meta['source_hash'] and info['frames'] == 192123
    ui = load(a.host / 'ui.json')
    assert ui['result'] == 'pass' and ui['voices'] == 10 and ui['cross_voice_replay_and_live_restore']
    bench = load(a.host / 'ui.json.bench.json')
    assert [v['load'] for v in bench['events']] == [.8, -.6, .25, 0]
    for channels in (2, 12):
        dest = a.out / ('bench_%d.wav' % channels)
        info = run('new', a.host / 'ui.json.bench.vslrun', dest, channels=channels)
        assert info['source_hash'] == bench['source_hash'] and info['frames'] == bench['frames'] == 240123
        if channels == 2:
            assert info['audio_hash'] == bench['audio_hash'] and sha(dest) == sha(a.host / 'ui.json.bench.wav')
        r['bench'].append(dict(channels=channels, source_hash_exact=True, native_WAV_exact=channels == 2))
    r.update(result='passed', old_render_id=old_ids.pop(), new_render_id=new_ids.pop(),
             F3_source_hash_2_12_exact=True, schema=10, controls=32, hearing=False,
             physical_7_1_4_verified=False)
except Exception as exc:
    r.update(result='failed', error=repr(exc))
    raise
finally:
    save(a.out / 'report.json', r)
