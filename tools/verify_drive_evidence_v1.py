"""Independent signal controls and sample/PTS checks for driving observations."""
import argparse
import json
from pathlib import Path
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--observations', type=Path, required=True)
parser.add_argument('--summary', type=Path, required=True)
args = parser.parse_args()
sys.path.insert(0, str(args.workspace / 'tools/python_deps'))
import numpy as np
from scipy import signal
import soundfile as sf
from drive_evidence_v1.sources import sha
from drive_evidence_v1.family import follow
from drive_evidence_v1.audio import strongest, BANDS

target = args.summary / 'verification.json'
if target.exists():
    raise RuntimeError('Preserve completed verification; use a new summary directory')
observed = json.loads((args.observations / 'observations.json').read_text(encoding='utf-8'))
report = json.loads((args.summary / 'report.json').read_text(encoding='utf-8'))
root = Path(__file__).resolve().parents[1]
for name, expected in observed['tools_sha256'].items():
    assert sha(root / 'tools' / name) == expected, name
assert report['observation_sha256'] == sha(args.observations / 'observations.json')
assert report['annotation_sha256'] == sha(root / 'research/drive_evidence_v1_annotations.json')
checks = []
for identity, record in observed['cases'].items():
    path = args.workspace / record['provenance']['master']
    assert sha(path) == record['provenance']['master_sha256']
    data = np.load(args.observations / identity / 'audio.npz')
    times, hz = data['seconds'], data['hz']
    measured_psd = data['psd_LR']
    bands = data['band_power_LR']
    max_psd_error, max_power_error, max_band_error = 0., 0., 0.
    # Independent direct FFT and Hann-weighted time-domain Parseval.
    window = .5-.5*np.cos(2*np.pi*np.arange(3840)/3840)
    for at in np.linspace(0, len(times)-1, 5).astype(int):
        start = round(times[at]*48000)-1920
        x, rate = sf.read(path, start=start, stop=start+3840, always_2d=True)
        z = np.fft.rfft(x*window[:, None], 32768, axis=0)
        psd = abs(z)**2/(48000*np.sum(window**2))
        psd[1:-1] *= 2
        max_psd_error = max(max_psd_error, float(abs(psd.T-measured_psd[:, :, at]).max()))
        weighted_power = np.sum((x*window[:, None])**2, axis=0)/np.sum(window**2)
        max_power_error = max(max_power_error, float(abs(psd.sum(axis=0)*48000/32768-weighted_power).max()))
        for j, (low, high) in enumerate(BANDS):
            value = psd[(hz >= low) & (hz < high)].sum(axis=0)*48000/32768
            max_band_error = max(max_band_error, float(abs(value-bands[:, j, at]).max()))
    assert max_psd_error < 1e-12 and max_power_error < 1e-12 and max_band_error < 1e-12
    checks.append(dict(segment=identity, direct_fft_max_psd_error=max_psd_error,
        weighted_time_parseval_max_error=max_power_error, direct_band_max_power_error=max_band_error))
    del measured_psd

video = observed['video']
assert sha(args.workspace / video['video']) == video['video_sha256']
assert all(r['source_frame_index']%video['step_source_frames'] == 0 for r in video['frames'])
assert all(sha(args.observations / 'E_video' / r['file']) == r['sha256'] for r in video['frames'])
assert all(abs(r['source_seconds']-r['pts']/1000) < 1e-12 for r in video['frames'])

# Known drifting oscillator family. The dominant line changes from3x to5x;
# the reference clock stays smooth. Include stereo differences and noise.
rate = 48000
t = np.arange(rate*3)/rate
phase = 2*np.pi*(55*t+t*t)
audio = np.zeros((len(t), 2))
for multiple, amplitude in [(2,.04), (3,.2), (5,.07), (7,.025)]:
    envelope = np.full(len(t), amplitude)
    if multiple == 3:
        envelope *= np.where(t < 1.5, 1., .1)
    for channel in (0, 1):
        audio[:, channel] += envelope*np.cos(multiple*phase+.37*multiple+.19*channel)
audio += np.random.default_rng(59107).normal(0, .001, audio.shape)
hz, times, psd = signal.spectrogram(audio.T, rate, window='hann', nperseg=3840,
    noverlap=3360, nfft=32768, detrend=False, scaling='density', mode='psd')
power = psd.mean(axis=0)
family = follow(hz, times, power, .2, 2.8, 55.4)
assert family['status'] == 'connected_observed_family'
measured_times = np.array([r['seconds'] for r in family['rows']])
clock = np.array([r['root_hz'] for r in family['rows']])
error = float(abs(clock-(55+2*measured_times)).max())
assert error < .2
dominant = np.array([strongest(hz, power[:, i]) for i in range(len(times))])
dominant_error = float(np.median(abs(dominant[(times >= .2) & (times < 1.3)]/5-(55+2*times[(times >= .2) & (times < 1.3)]))))
assert dominant_error > 10
scaled = follow(hz, times, psd[::-1].mean(axis=0)*.0625, .2, 2.8, 55.4)
gain_error = max(abs(a['root_hz']-b['root_hz']) for a, b in zip(family['rows'], scaled['rows']))
assert scaled['status'] == 'connected_observed_family' and gain_error < 1e-10
assert follow(hz, times, np.ones_like(power), .2, 2.8, 55.4)['status'] == 'no_connected_family'

data = np.load(args.observations / 'E_corsa_second_context/audio.npz')
second = follow(data['hz'], data['seconds'], data['psd_LR'].mean(axis=0), 83, 94.01, 64.5, max_octaves_per_second=32)
assert second['status'] == 'connected_observed_family'
reference = report['family']['rows']
assert len(second['rows']) == len(reference)
sensitivity = max(abs(a['reference_hz']-b['reference_hz']) for a, b in zip(reference, second['rows']))
# Record sensitivity as evidence; agreement would not prove the clock true.
result = dict(schema='vsl.drive-evidence-verification/1', result='pass', source_checks=checks,
    video_frames_verified=len(video['frames']),
    analytic_control=dict(drifting_clock_max_error_hz=error,
        strongest_line_divided_by5_median_error_hz=dominant_error,
        gain_and_channel_swap_max_clock_difference_hz=gain_error, no_peak_input_rejected=True),
    real_family_16_vs32_octaves_per_second_max_reference_difference_hz=sensitivity,
    summary_sha256=sha(args.summary / 'report.json'),
    tools_sha256={str(p.relative_to(root)).replace('\\','/'):sha(p) for p in [Path(__file__), root/'tools/summarize_drive_evidence_v1.py', root/'tools/drive_evidence_v1/family.py']},
    scope='Numerical / file / frame checks, not human audio acceptance, source separation or precision RPM validation')
target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(dict(result='pass', cases=len(checks), video_frames=len(video['frames']), analytic_max_error=error, strongest_error=dominant_error, sensitivity_hz=sensitivity)))
