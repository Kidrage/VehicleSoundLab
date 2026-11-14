"""Verify twelve owned recipes against the frozen ten and both compatible players."""
import argparse
from pathlib import Path
import shutil
import subprocess
from research_archive_v1 import load, save, sha

p = argparse.ArgumentParser(description=__doc__)
for key in ('workspace', 'build-dir', 'host', 'out'):
    p.add_argument('--'+key, type=Path, required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
parent = a.workspace/'baselines/bandlimited_dna_v1'
manifest = {v['path']: v['sha256'] for v in load(parent/'manifest.json')['files']}
a.out.mkdir(parents=True, exist_ok=False)
shutil.copy2(__file__, a.out/'executed_regression.py')
shutil.copytree(a.build_dir/'catalog-check', a.out/'new_render')
empty = a.out/'no_external_voice_files'
empty.mkdir()
old = parent/'evidence/bin/VslAtlasTake_render.exe'
assert sha(old) == manifest[old.relative_to(parent).as_posix()]
players = {'old': old, 'new': a.build_dir/'bin/Release/VslAtlasTake_render.exe'}
for label, binary in list(players.items()):
    target = a.out/(label+'_player.exe')
    shutil.copy2(binary, target)
    players[label] = target
r = dict(result='running', commands=[], original=[], current=[], native=[], render_id=None)


def run(label, take, dest, channels=2):
    binary = players[label]
    args = [binary, take, dest]
    if channels != 2:
        args += ['--channels', channels]
    args = list(map(str, args))
    done = subprocess.run(args, cwd=empty, capture_output=True, timeout=180)
    log = a.out/('command_%03d.log' % len(r['commands']))
    log.write_bytes(done.stdout+done.stderr)
    r['commands'].append(dict(argv=args, binary_sha256=sha(binary), exit_code=done.returncode,
                              cwd=str(empty), log=log.name, sha256=sha(log)))
    save(a.out/'report.json', r)
    assert done.returncode == 0, log
    import json
    info = json.loads(done.stdout.decode('utf-8').strip())
    assert info['verified'] and info['channels'] == channels
    return info


try:
    ids = set()
    for k in range(12):
        base = a.out/('new_render/voice_%d' % k)
        now = load(base.with_suffix('.json'))
        assert now['driver_2_12_exact'] and now['stems_2_12_exact'] and now['owned_replay_PCM_exact']
        ids.add(now['render_id'])
        for label in players:
            dest = a.out/('voice_%d_%s.wav' % (k, label))
            info = run(label, base.with_suffix('.vslrun'), dest)
            assert sha(dest) == sha(base.with_suffix('.wav'))
            assert info['audio_hash'] == now['audio_hash'] and info['source_hash'] == now['source_hash']
        if k < 10:
            prior = parent/('evidence/catalog1/new_render/voice_%d' % k)
            for suffix in ('.wav', '.json', '.vslrun'):
                path = prior.with_suffix(suffix)
                assert sha(path) == manifest[path.relative_to(parent).as_posix()]
            meta = load(prior.with_suffix('.json'))
            ids.add(meta['render_id'])
            assert now['audio_hash'] == meta['audio_hash'] and now['source_hash'] == meta['source_hash']
            assert sha(base.with_suffix('.wav')) == sha(prior.with_suffix('.wav'))
            for label in players:
                dest = a.out/('prior_%d_%s.wav' % (k, label))
                run(label, prior.with_suffix('.vslrun'), dest)
                assert sha(dest) == sha(prior.with_suffix('.wav'))
            r['original'].append(dict(selection=k, whole_WAV_and_source_exact=True, both_players_exact=True))
        else:
            for label in players:
                info = run(label, base.with_suffix('.vslrun'), a.out/('voice_%d_%s_12.wav' % (k, label)), 12)
                assert info['source_hash'] == now['source_hash'] and info['frames'] == 192123
        r['current'].append(dict(selection=k, both_players_exact=True, external_models_absent=True))
        save(a.out/'report.json', r)
        print('PASS current/old catalog and compatible players', k, flush=True)
    assert len(ids) == 1
    r['render_id'] = ids.pop()
    ui = load(a.host/'ui.json')
    assert ui['result'] == 'pass' and ui['voices'] == 12 and len(ui['records']) == 12
    assert ui['cross_voice_replay_and_live_restore'] and ui['muted']
    for stem in ('bench', 'local0', 'local1'):
        take = a.host/('ui.json.'+stem+'.vslrun')
        reference = a.host/('ui.json.'+stem+'.wav')
        source_hashes = set()
        for label in players:
            for channels in (2, 12):
                dest = a.out/('native_%s_%s_%d.wav' % (stem, label, channels))
                info = run(label, take, dest, channels)
                assert info['frames'] == 240123
                source_hashes.add(info['source_hash'])
                if channels == 2:
                    assert sha(dest) == sha(reference)
        assert len(source_hashes) == 1
        r['native'].append(dict(name=stem, both_players_2_12_source_exact=True, native_stereo_WAV_exact=True))
    r.update(result='passed', old_ten_exact=True, new_twelve_owned_replay=True,
             both_players_same_identity=True, no_external_voice_paths=True,
             schema=10, controls=32, hearing=False, physical_7_1_4=False)
except Exception as exc:
    r.update(result='failed', error=repr(exc))
    raise
finally:
    save(a.out/'report.json', r)
