"""Exercise current raw profile guard with fixed synthetic data only."""
import argparse
import math
from pathlib import Path
import shutil
import subprocess
from research_archive_v1 import load, save, sha

p = argparse.ArgumentParser(description=__doc__)
for key in ('out', 'dna-probe'):
    p.add_argument('--'+key, type=Path, required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
a.out.mkdir(parents=True, exist_ok=False)
r = dict(result='running', sources={}, inputs={}, cases=[])
try:
    for name in ('tools/check_dna_anchor_limits_v1.py', 'research/dna_anchor_limits_v1_plan.json',
                 'modules/sound_dna/profile.c', 'modules/sound_dna/voice.c',
                 'modules/sound_dna/oscillator.c', 'modules/dna_atlas/bank.c',
                 'modules/dna_atlas/voice.c', 'experiments/sound_dna_export_v1/probe.c',
                 'tools/research_archive_v1.py'):
        dest = a.out/'exact_sources'/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo/name, dest)
        r['sources'][name] = sha(repo/name)
    plan = load(repo/'research/dna_anchor_limits_v1_plan.json')
    r['inputs'][str(a.dna_probe)] = sha(a.dna_probe)
    assert subprocess.check_output([str(a.dna_probe), '--describe']).decode().strip() == 'vsl.sound-dna-raw-export/1'
    limit = 21600/(plan['harmonics']*1.1)
    for i, root in enumerate((limit-1e-6, limit+1e-6, 90.)):
        path = a.out/f'known_{i}.model'
        lines = [f"VSL_SOUND_DNA 1 48000 1024 256 {plan['harmonics']} 0 {root:.17g}", '']
        for h in range(plan['harmonics']):
            left = .2 if h == 0 else .01 if h == plan['harmonics']-1 else 0.
            lines.append(' '.join(map(str, [left, 0, left*.8, 0, 0]+[0]*16)))
        path.write_text('\n'.join(lines)+'\n', encoding='ascii')
        wave = a.out/f'known_{i}.wav'
        argv = list(map(str, [a.dna_probe, path, wave, plan['samples']/48000, 1, 1, plan['seed'], plan['chunk_frames']]))
        done = subprocess.run(argv, cwd=repo, capture_output=True, timeout=30)
        (a.out/f'known_{i}.log').write_bytes(done.stdout+done.stderr)
        expected = 0 if i == 0 else 2
        assert done.returncode == expected and wave.exists() == (i == 0)
        # WAV header declares IEEE FLOAT via the existing exporter; inspect data
        # with standard-library RIFF parsing, no dependency or DSP assumptions.
        frames = 0
        if wave.exists():
            import struct
            raw = wave.read_bytes()
            assert raw[:4] == b'RIFF' and raw[8:12] == b'WAVE'
            at = 12
            channels = bits = tag = rate = None
            data = None
            while at+8 <= len(raw):
                name, size = raw[at:at+4], int.from_bytes(raw[at+4:at+8], 'little')
                if name == b'fmt ':
                    tag, channels, rate, _, _, bits = struct.unpack('<HHIIHH', raw[at+8:at+24])
                    if tag == 0xfffe:
                        assert size == 40
                        extension, valid, mask = struct.unpack('<HHI', raw[at+24:at+32])
                        assert (extension, valid, mask) == (22, 32, 3)
                        assert raw[at+32:at+48] == bytes.fromhex('0300000000001000800000aa00389b71')
                        tag = 3
                if name == b'data':
                    data = raw[at+8:at+8+size]
                at += 8+size+(size % 2)
            assert (tag, channels, rate, bits) == (3, 2, 48000, 32)
            samples = struct.unpack('<'+'f'*(len(data)//4), data)
            assert all(math.isfinite(v) for v in samples)
            frames = len(samples)//2
            assert frames == plan['samples']
        r['cases'].append(dict(root_hz=root, root_limit_hz=limit, exit_code=done.returncode,
                               wave_created=wave.exists(), frames=frames, argv=argv,
                               profile_sha256=sha(path)))
    r.update(result='existing_288harmonic_profile_limit_reproduced', root_limit_hz=limit,
             only_known_synthetic_profiles=True, real_source_read=False, runtime_changed=False,
             next='Explicit bounded profile/renderer support before higher-root real anchors; retain old safe loader and replay contract.')
except Exception as exc:
    r.update(result='failed', error=repr(exc))
    raise
finally:
    save(a.out/'report.json', r)
print(dict(result=r['result'], root_limit_hz=r.get('root_limit_hz'), outcomes=[v['exit_code'] for v in r['cases']]))
