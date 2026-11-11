"""Known-clock time-warp check and independent C anchor measurements."""
import argparse
import json
from pathlib import Path
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--anchors', type=Path, required=True)
args = parser.parse_args()
sys.path.insert(0, str(args.workspace / 'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal
from drive_evidence_v1.normalize import cycles
from drive_evidence_v1.sources import sha
from sound_dna.profile import export

target = args.anchors / 'verification.json'
if target.exists():
    raise RuntimeError('Preserve verified anchors')
build = json.loads((args.anchors / 'build.json').read_text(encoding='utf-8'))
repository = Path(__file__).resolve().parents[1]
for name, expected in build['tools_sha256'].items():
    assert sha(repository/'tools'/name) == expected

rate = 48000
t = np.arange(rate*4)/rate
phase_cycles = 55*t+t*t
multiples = (2, 3, 5, 7, 100)
audio = np.zeros((len(t), 2))
for multiple in multiples:
    for channel in (0, 1):
        audio[:, channel] += .03*np.cos(2*np.pi*multiple*phase_cycles+.11*multiple+.37*channel)
clock_times = np.arange(401)/100
normalized, meta = cycles(audio, 0., clock_times, 55+2*clock_times, .5, 2.5)
expected = np.zeros_like(normalized)
coordinate = np.arange(len(normalized))/1024 + 55*.5+.5**2
for multiple in multiples:
    for channel in (0, 1):
        expected[:, channel] += .03*np.cos(2*np.pi*multiple*coordinate+.11*multiple+.37*channel)
error = float(abs(normalized-expected).max())
assert error < 1e-4
unsupported_rejected = False
try:
    cycles(audio, 0., clock_times, 55+2*clock_times, -.1, 2.5)
except ValueError:
    unsupported_rejected = True
assert unsupported_rejected

bands = [(28,120),(120,400),(400,1200),(1200,3000),(3000,8000),(8000,14000)]
def powers(x):
    hz, psd = signal.welch(x, rate, nperseg=4096, noverlap=2048, axis=0, detrend=False)
    return np.array([psd[(hz>=low)&(hz<high)].sum(axis=0)*rate/4096 for low,high in bands])

records = []
for record in build['anchors']:
    out = args.anchors/record['name']
    assert sha(out/'voice.model') == record['model_sha256']
    m = dict(np.load(out/'statistics.npz'))
    copied = args.anchors/(record['name']+'.export-check.model')
    export(copied, m, record['warp']['root_hz_median'])
    assert sha(copied) == record['model_sha256']
    reference, rate = sf.read(out/'fixed_reference.wav', always_2d=True)
    generated, _ = sf.read(out/'raw_1.0.wav', always_2d=True)
    # Undo only the fixed0.5 listening gain; skip endpoints in the reference.
    reference_power = powers(reference[240:-240]*2)
    generated_power = powers(generated[48000:])
    delta = 10*np.log10(np.maximum(generated_power,1e-30)/np.maximum(reference_power,1e-30))
    captures = []
    for render in record['render']:
        path = out/render['raw']
        assert sha(path) == render['raw_sha256']
        audio, sample_rate = sf.read(path, always_2d=True)
        assert sample_rate == 48000 and audio.shape == (384000,2) and np.isfinite(audio).all()
        assert not np.array_equal(audio[:192000],audio[192000:])
        captures.append(dict(pitch=render['relative_pitch'], frames=len(audio),peak=float(abs(audio).max())))
    records.append(dict(name=record['name'], captures=captures,
        generated_minus_fixed_reference_band_db_LR=delta.tolist(),
        source_context_stereo_difference_relative_db=float(10*np.log10(max(np.mean((reference[:,0]-reference[:,1])**2)/np.mean(reference**2),1e-30))),
        interpretation='Broad finite-duration spectral comparison; no score of realism or sample-exact reconstruction claim'))
result = dict(schema='vsl.cabin-anchor-verification/1', result='pass',
    known_time_varying_clock_max_waveform_error=error,
    known_clock_complete_cycles=meta['complete_cycles'], extrapolation_rejected=True,
    band_hz=[list(b) for b in bands], anchors=records, build_sha256=sha(args.anchors/'build.json'),
    verifier_sha256=sha(__file__), status='Technical checks only; subjective quality / continuous anchor interpolation remain open')
target.write_text(json.dumps(result, ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(result='pass',known_clock_max_error=error,anchors=[dict(name=r['name'],band_db_L=[round(d[0],2) for d in r['generated_minus_fixed_reference_band_db_LR']],stereo_db=r['source_context_stereo_difference_relative_db']) for r in records])))
