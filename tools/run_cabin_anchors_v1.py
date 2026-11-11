"""Compile two distinct recorded cabin anchors with the existing C DNA codec."""
import argparse
from fractions import Fraction
import json
from pathlib import Path
import subprocess
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--summary', type=Path, required=True)
parser.add_argument('--probe', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
sys.path.insert(0, str(args.workspace / 'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal
from drive_evidence_v1.sources import read, sha
from drive_evidence_v1.normalize import cycles
from sound_dna.profile import export
from sound_dna.windowed import estimate

summary = json.loads((args.summary / 'report.json').read_text(encoding='utf-8'))
verification = json.loads((args.summary / 'verification.json').read_text(encoding='utf-8'))
assert verification['result'] == 'pass' and verification['summary_sha256'] == sha(args.summary / 'report.json')
rows = summary['family']['rows']
times = np.array([row['seconds'] for row in rows])
clock = np.array([row['root_hz'] for row in rows])
audio, provenance = read(args.workspace, 'E_corsa_second_context', 'cabin_dynamic_observation')
args.out.mkdir(parents=True, exist_ok=False)
result = dict(schema='vsl.cabin-anchor-build/1', provenance=provenance, anchors=[],
    summary_sha256=sha(args.summary / 'report.json'), verification_sha256=sha(args.summary / 'verification.json'),
    c_probe_sha256=sha(args.probe), shared_renderer='Unmodified modules/sound_dna C11',
    acceptance='Experimental unaccepted recording-derived cabin contexts, not new vehicle types',
    limits=['No phase alignment or interpolation between anchors yet',
        'Recorded cabin mixture includes its acoustic transfer; never combine with A exterior LF',
        'No physical intake/exhaust source separation or complete state library',
        '0.90..1.10 relative pitch only; not wide-RPM driving integration'])
for name, start, stop in [('E Cabin Lower',89.3,90.3), ('E Cabin Upper',90.6,91.6)]:
    out = args.out / name
    out.mkdir()
    normalized, warp = cycles(audio, provenance['seconds'][0], times, clock, start, stop)
    base_hz = warp['root_hz_median']
    assert 288*base_hz*1.1 < 21600
    model, statistics = estimate(normalized, harmonics=288, components=12)
    export(out / 'voice.model', model, base_hz)
    sf.write(out / 'normalized_reference_float.wav', normalized, 48000, subtype='FLOAT')
    np.savez_compressed(out / 'statistics.npz', **model)
    ratio = Fraction(46.875/base_hz).limit_denominator(10000)
    fixed_reference = signal.resample_poly(normalized, ratio.numerator, ratio.denominator, axis=0, window=('kaiser', 8.6))
    def listen(path, x):
        envelope = np.ones(len(x))
        envelope[:240] = np.linspace(0, 1, 240)
        envelope[-240:] = np.linspace(1, 0, 240)
        x = .5*x*envelope[:, None]
        assert np.max(abs(x)) < .95
        sf.write(path, x, 48000, subtype='PCM_24')
    listen(out / 'fixed_reference.wav', fixed_reference)
    rendered = []
    for pitch in (.9, 1., 1.1):
        raw = out / f'raw_{pitch:.1f}.wav'
        command = [str(args.probe), str(out/'voice.model'), str(raw), '8', str(pitch), '1', '1']
        subprocess.run(command, check=True, capture_output=True, timeout=90)
        generated, rate = sf.read(raw, always_2d=True)
        assert rate == 48000 and generated.shape == (384000, 2) and np.isfinite(generated).all()
        listen(out / f'listen_{pitch:.1f}.wav', generated)
        rendered.append(dict(relative_pitch=pitch, raw=raw.name, raw_sha256=sha(raw),
            frames=len(generated), peak=float(abs(generated).max()),
            repeated_first_last4seconds=bool(np.array_equal(generated[:192000],generated[192000:])),
            command=command))
    record = dict(name=name, warp=warp, statistics=statistics,
        model_sha256=sha(out/'voice.model'), render=rendered,
        gain_policy='All reference/generated listening files share0.5 gain and5ms endpoint fades; no per-clip level matching',
        note='normalized_reference_float.wav plays at46.875Hz; fixed_reference.wav restores the anchor acoustic root')
    (out/'build.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    result['anchors'].append(record)
    print(name, 'base_hz=', base_hz, 'compiled and C-rendered', flush=True)
result['tools_sha256'] = {str(p.relative_to(Path(__file__).parent)).replace('\\','/'):sha(p)
    for p in [Path(__file__), Path(__file__).with_name('drive_evidence_v1')/'normalize.py', *Path(__file__).with_name('sound_dna').glob('*.py')]}
(args.out/'build.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
