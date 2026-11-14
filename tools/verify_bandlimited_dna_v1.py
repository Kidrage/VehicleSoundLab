"""Independent FLOAT/analytic export checks and frozen-ten-catalog regression.

Synthetic checks validate carrier taper/loading, not new measured timbre/RPM.
"""
import argparse
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
from research_archive_v1 import load, save, sha

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
p.add_argument('--stage', choices=['export', 'catalog'], required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
build = repo / 'build-bandlimited-dna-v1'
a.out.mkdir(parents=True, exist_ok=False)
shutil.copy2(__file__, a.out / 'executed_verify.py')
r = dict(result='running', stage=a.stage, commands=[])


def run(binary, args, expected=0, missing=None):
    argv = list(map(str, [binary] + args))
    done = subprocess.run(argv, cwd=repo, capture_output=True, timeout=180)
    log = a.out / ('command_%03d.log' % len(r['commands']))
    log.write_bytes(done.stdout + done.stderr)
    r['commands'].append(dict(argv=argv, exit_code=done.returncode,
                             log=log.name, sha256=sha(log), binary_sha256=sha(binary)))
    save(a.out / 'report.json', r)
    assert done.returncode == expected, log
    if missing is not None:
        assert not missing.exists(), missing
    return done


def read_float(path):
    raw = path.read_bytes()
    assert raw[:4] == b'RIFF' and raw[8:12] == b'WAVE'
    assert struct.unpack_from('<I', raw, 4)[0] + 8 == len(raw)
    chunks = {}
    at = 12
    while at + 8 <= len(raw):
        tag, size = struct.unpack_from('<4sI', raw, at)
        assert at + 8 + size <= len(raw)
        chunks[tag] = raw[at+8:at+8+size]
        at += 8 + size + (size & 1)
    fmt = chunks[b'fmt ']
    tag, channels, rate, byte_rate, align, bits = struct.unpack_from('<HHIIHH', fmt)
    if tag == 0xFFFE:
        assert len(fmt) >= 40 and struct.unpack_from('<H', fmt, 16)[0] >= 22
        assert struct.unpack_from('<H', fmt, 18)[0] == 32
        assert fmt[24:40] == bytes.fromhex('0300000000001000800000aa00389b71')
    else:
        assert tag == 3
    assert channels == 2 and rate == 48000 and bits == 32 and align == 8 and byte_rate == rate*align
    data = np.frombuffer(chunks[b'data'], dtype='<f4').reshape(-1, 2).astype(float)
    assert np.isfinite(data).all()
    return data


def model(path, root, lines, textured=False):
    components = 2 if textured else 0
    tokens = ['VSL_SOUND_DNA 1 48000 1024 256 288 %d %.17g' % (components, root)]
    if textured:
        tokens += ['.6 -.2']
    for order in range(1, 289):
        al, pl, ar, pr = lines.get(order, (0, 0, 0, 0))
        values = [al*math.cos(pl), al*math.sin(pl), ar*math.cos(pr), ar*math.sin(pr)]
        if textured:
            values += [.0001, 0, 0, 0, 0, 0, 0, .00007]
        values += [.3 if textured else 0]
        values += [.00003 if textured and i == 0 else .00002 if textured and i == 10 else 0 for i in range(16)]
        tokens.append(' '.join(format(x, '.17g') for x in values))
    path.write_text('\n'.join(tokens)+'\n', encoding='utf-8', newline='\n')


try:
    if a.stage == 'export':
        for key in ['OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS']:
            os.environ[key] = '2'
        sys.path.insert(0, str(a.workspace / 'tools/python_deps'))
        import numpy as np
        exe = build / 'bin/Release/sound_dna_bandlimited_export.exe'
        raw = build / 'bin/Release/sound_dna_legacy_export.exe'
        frozen_raw = repo / 'build-sound-dna-export-v1/bin/Release/sound_dna_export.exe'
        assert run(exe, ['--describe']).stdout.strip() == b'vsl.sound-dna-bandlimited-export/1'
        r['analytic'] = []
        cases = [
            ('masked', 90, {288: (.2, .23, .13, -.71)}),
            ('mixed', 90, {13: (.1, .17, .07, -.3), 220: (.12, .3, .08, -.6), 288: (.02, .9, .01, .2)}),
            ('max_root', 1000, {1: (.1, .17, .07, -.3), 20: (.12, .3, .08, -.6), 288: (.02, .9, .01, .2)})]
        for name, root, lines in cases:
            source = a.out / (name+'.model')
            model(source, root, lines)
            dest = a.out / (name+'.wav')
            run(exe, [source, dest, 1, root, 0, 23117, 37])
            data = read_float(dest)
            assert len(data) == 48000
            time = np.arange(48000)/48000
            expected = np.zeros_like(data)
            for order, (al, pl, ar, pr) in lines.items():
                freq = order*root
                if freq >= 21600:
                    continue
                x = max(0, (freq-19200)/2400)
                weight = 1-3*x*x+2*x*x*x
                expected[:, 0] += weight*al*np.cos(2*np.pi*freq*time+pl)
                expected[:, 1] += weight*ar*np.cos(2*np.pi*freq*time+pr)
            error = float(np.max(np.abs(data-expected)))
            assert error < 3e-8, (name, error)
            alias_amplitude = None
            if root == 90:
                # 288*90=25920 folds to22080 without carrier suppression.
                alias_amplitude = float(np.max(np.abs(2*np.mean(data*np.exp(-2j*np.pi*22080*time)[:, None], axis=0))))
                assert alias_amplitude < 1e-9
            if name == 'masked':
                assert not np.any(data)
            r['analytic'].append(dict(name=name, frames=len(data), error_FS=error,
                                      folded_22080_amplitude_FS=alias_amplitude, sha256=sha(dest)))
        source = a.out / 'textured.model'
        model(source, 90, cases[1][2], True)
        for chunk in (37, 512):
            run(exe, [source, a.out/('texture_%d.wav' % chunk), .25, 90, 1, 61927, chunk])
        assert sha(a.out/'texture_37.wav') == sha(a.out/'texture_512.wav')
        invalid = [('-1', '1', '23117', '37'), ('1000.001', '1', '23117', '37'),
                   ('nan', '1', '23117', '37'), ('90', '1.01', '23117', '37'),
                   ('90', '1', '0', '37'), ('90', '1', '23117', '513')]
        for index, (root, detail, seed, chunk) in enumerate(invalid):
            dest = a.out / ('invalid_%d.wav' % index)
            run(exe, [source, dest, .01, root, detail, seed, chunk], 1, dest)
        source_bad = a.out / 'root_above.model'
        model(source_bad, 1000.001, {})
        dest = a.out / 'invalid_profile.wav'
        run(exe, [source_bad, dest, .01, 90, 1, 23117, 37], 2, dest)
        dest = a.out / 'legacy_high.wav'
        run(raw, [source, dest, .01, 1, 1, 23117, 37], 2, dest)
        r['legacy_raw_exact'] = []
        original = repo/'voices/F3_before_upshift_v1/F3 before upshift.model'
        for label, binary in [('old', frozen_raw), ('new', raw)]:
            run(binary, [original, a.out/(label+'_raw.wav'), .25, 1, 1, 23117, 37])
        assert sha(a.out/'old_raw.wav') == sha(a.out/'new_raw.wav')
        r.update(block_37_512_exact=True, invalid_before_output=8,
                 legacy_raw_exact=True, real_source_refit=False, hearing=False,
                 physical_RPM_claim=False, stochastic_sideband_brickwall_claim=False)
    else:
        parent = a.workspace / 'baselines/catalog_F3_v1'
        manifest = {x['path']: x for x in load(parent/'manifest.json')['files']}
        oldplayer = parent/'evidence/bin/VslAtlasTake_render.exe'
        assert sha(oldplayer) == manifest[oldplayer.relative_to(parent).as_posix()]['sha256']
        newplayer = build/'bin/Release/VslAtlasTake_render.exe'
        shutil.copytree(build/'catalog-check', a.out/'new_render')
        r['catalog'] = []
        oldids, newids = set(), set()
        for k in range(10):
            name = 'voice_%d' % k
            oldbase = parent/'evidence/regress1/new_render'/name
            newbase = a.out/'new_render'/name
            for suffix in ('.wav', '.vslrun', '.json'):
                path = oldbase.with_suffix(suffix)
                assert sha(path) == manifest[path.relative_to(parent).as_posix()]['sha256']
            prior, now = load(oldbase.with_suffix('.json')), load(newbase.with_suffix('.json'))
            assert now['driver_2_12_exact'] and now['stems_2_12_exact'] and now['owned_replay_PCM_exact']
            assert prior['audio_hash'] == now['audio_hash'] and prior['source_hash'] == now['source_hash']
            assert sha(oldbase.with_suffix('.wav')) == sha(newbase.with_suffix('.wav'))
            oldids.add(prior['render_id']);newids.add(now['render_id'])
            for label, binary, base in [('old', oldplayer, oldbase), ('new', newplayer, newbase)]:
                dest = a.out / (name+'_'+label+'_replay.wav')
                run(binary, [base.with_suffix('.vslrun'), dest])
                assert sha(dest) == sha(base.with_suffix('.wav'))
            if k in (0, 9):
                dest = a.out / (name+'_old_on_new.wav')
                run(oldplayer, [newbase.with_suffix('.vslrun'), dest], 3, dest)
                dest = a.out / (name+'_new_on_old.wav')
                run(newplayer, [oldbase.with_suffix('.vslrun'), dest], 3, dest)
            r['catalog'].append(dict(selection=k, WAV_exact=True, old_replay_exact=True,
                                     new_replay_exact=True, driver_stems_2_12_exact=True))
            save(a.out/'report.json', r)
            print('PASS frozen/new catalog and owned replay', k, flush=True)
        assert len(oldids) == len(newids) == 1 and oldids.isdisjoint(newids)
        r.update(old_render_id=oldids.pop(), new_render_id=newids.pop(),
                 strict_cross_identity_rejections=4, schema=10, controls=32,
                 high_root_owned_support=False, physical_7_1_4_verified=False)
    r['result'] = 'passed'
except Exception as exc:
    r.update(result='failed', error=repr(exc))
    raise
finally:
    save(a.out/'report.json', r)
print('PASS', a.stage, flush=True)
