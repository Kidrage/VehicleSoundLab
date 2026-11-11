"""Independent FFT, known-clock and pitch-only counterexamples for shift analysis."""
import argparse
import json
from pathlib import Path
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--analysis', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(args.workspace / 'tools/python_deps'))
import numpy as np
from drive_evidence_v1.sources import read, sha
from drive_evidence_v1.family import follow
from shift_evidence_v1.spectrum import observe, region_stats, BANDS, RELATIVE_BANDS
from shift_evidence_v1.timing import descent, guided_peaks, delay_intervals

target = args.analysis / 'verification.json'
assert not target.exists(), 'Preserve completed verification'
report_path = args.analysis / 'report.json'
report = json.loads(report_path.read_text(encoding='utf-8'))
for name, expected in report['source_sha256'].items():
    assert sha(repo / name) == expected, name
assert sha(repo / 'research/drive_evidence_v1_annotations.json') == report['annotation_sha256']
audio, provenance = read(args.workspace, 'E_corsa_second_context', 'cabin_dynamic_observation')
assert provenance == report['provenance']
guide = np.load(args.analysis / 'window_80.npz')
direct_checks = []
rate, fft = 48000, 16384
hz = np.fft.rfftfreq(fft, 1 / rate)
for result in report['analyses']:
    data = np.load(args.analysis / f"window_{result['window_ms']}.npz")
    times = data['seconds']
    size = round(result['window_ms'] * rate / 1000)
    window = .5 - .5 * np.cos(2 * np.pi * np.arange(size) / size)
    def independent(stamp, bands):
        first = round((stamp - provenance['seconds'][0]) * rate) - size // 2
        x = audio[first:first + size]
        z = np.fft.rfft(window[:, None] * x, fft, axis=0)
        density = abs(z) ** 2 / (rate * sum(window ** 2))
        cross = z[:, 0] * z[:, 1].conj() / (rate * sum(window ** 2))
        density[1:-1] *= 2
        cross[1:-1] *= 2
        powers = np.array([density[(hz >= lo) & (hz < hi)].sum(axis=0) * rate / fft for lo, hi in bands]).T
        crosses = np.array([cross[(hz >= lo) & (hz < hi)].sum() * rate / fft for lo, hi in bands])
        time_power = np.sum((x * window[:, None]) ** 2, axis=0) / sum(window ** 2)
        assert np.max(abs(density.sum(axis=0) * rate / fft - time_power)) < 1e-14
        return powers, crosses
    error = 0.
    for at in np.linspace(0, len(times) - 1, 5).astype(int):
        p, c = independent(times[at], BANDS)
        error = max(error, float(abs(p - data['band_power_LR'][:, :, at]).max()),
                    float(abs(c - data['band_cross_LR'][:, at]).max()))
    for event in result['events']:
        for key in ('before', 'after'):
            stats = event['relative_' + key]
            keep = (times >= stats['seconds'][0]) & (times < stats['seconds'][1])
            ps, cs = [], []
            for stamp in times[keep]:
                root = np.interp(stamp, guide['family_seconds'], guide['reference_hz']) / 5
                p, c = independent(stamp, [(lo * root, hi * root) for lo, hi in RELATIVE_BANDS])
                ps.append(p)
                cs.append(c)
            p, c = np.mean(ps, axis=0), np.mean(cs, axis=0)
            rho = c / np.sqrt(p[0] * p[1])
            expected = np.array(stats['complex_band_correlation'])
            error = max(error, float(abs(p - np.array(stats['power_LR'])).max()),
                        float(abs(rho - (expected[:, 0] + 1j * expected[:, 1])).max()))
    assert error < 1e-11
    correlation = data['band_cross_LR'] / np.sqrt(np.maximum(
        data['band_power_LR'][0] * data['band_power_LR'][1], 1e-60))
    assert np.max(abs(correlation)) <= 1 + 1e-12
    direct_checks.append(dict(window_ms=result['window_ms'], direct_max_error=error,
                              max_correlation_magnitude=float(abs(correlation).max())))

# Constant-amplitude harmonics: an upper line crosses the3kHz boundary after
# a known pitch drop. A raw high-band loss must not be labelled torque cut.
time = np.arange(3 * rate) / rate
root = np.where(time < 1.45, 60 + 3 * time,
    np.where(time < 1.55, 64.35 + (52 - 64.35) * (time - 1.45) / .1, 52 + time - 1.55))
phase = 2 * np.pi * np.cumsum(root) / rate
synthetic = np.zeros((len(time), 2))
for harmonic, amplitude in ((2,.025), (3,.10), (5,.06), (7,.02), (53,.04)):
    for channel in (0, 1):
        synthetic[:, channel] += amplitude * np.cos(harmonic * phase + .2 * channel + .31 * harmonic)
control = observe(synthetic, 0, 80, clock=(time, root * 5))
family = follow(control['hz'], control['seconds'], control['power_low'], .2, 2.8,
                60.6, max_octaves_per_second=32)
assert family['status'] == 'connected_observed_family'
ft = np.array([r['seconds'] for r in family['rows']])
ff = np.array([r['reference_hz'] for r in family['rows']])
steady = abs(ft - 1.5) > .2
clock_error = float(np.max(abs(ff[steady] / 5 - np.interp(ft[steady], time, root))))
assert clock_error < .25
marker = descent(ft, ff, 1.25, 1.75)
assert abs(marker['marker_seconds'] - 1.5) < .1
pre, post = region_stats(control, 1.25, 1.35), region_stats(control, 1.70, 1.80)
fixed_loss = 10 * np.log10(np.array(post['power_LR']) / np.array(pre['power_LR']))
relative = dict(control, power_LR=control['relative_power_LR'], cross_LR=control['relative_cross_LR'])
pre_r, post_r = region_stats(relative, 1.25, 1.35), region_stats(relative, 1.70, 1.80)
relative_loss = 10 * np.log10(np.array(post_r['power_LR']) / np.array(pre_r['power_LR']))
assert fixed_loss[:, 4].max() < -20
assert abs(relative_loss[:, 4]).max() < .1

# Missing reference line must remain missing in the guided short-window view.
missing = np.zeros((rate, 2))
tt = np.arange(rate) / rate
for h in (2, 3, 7):
    missing += .04 * np.cos(2 * np.pi * h * 60 * tt)[:, None]
observed = observe(missing, 0, 60)
_, measured, _ = guided_peaks(observed, np.array([.1, .9]), np.array([300., 300.]))
assert not np.isfinite(measured).any()

# Exact constructed display intervals identify a feasible combined delay;
# one incompatible event must invalidate it, rather than silently widening.
known = [dict(marker_seconds=float(i), display=dict(to=i + 2,
    last_old_seconds=i + .27, first_new_seconds=i + .33)) for i in range(5)]
feasible = delay_intervals(known)
assert feasible['common_delay_feasible']
assert all(r['midpoint_inside_held_out'] for r in feasible['leave_one_out'])
known[-1]['display'].update(last_old_seconds=4.7, first_new_seconds=4.8)
assert not delay_intervals(known)['common_delay_feasible']

result = dict(schema='vsl.shift-evidence-verification/1', result='pass',
    report_sha256=sha(report_path), source_sha256={Path(__file__).relative_to(repo).as_posix():sha(Path(__file__))},
    real_stereo_direct_checks=direct_checks,
    controls=dict(known_steady_clock_max_error_hz=clock_error, known_drop_marker=marker,
        pitch_only_fixed_3k_8k_change_db_LR=fixed_loss[:, 4].tolist(),
        pitch_only_relative_45p5_110p5_change_db_LR=relative_loss[:, 4].tolist(),
        missing_reference_peak_stays_missing=True,
        feasible_and_infeasible_interval_controls=True),
    scope='File and signal checks, not listening acceptance or measured transmission timing')
target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, ensure_ascii=False))
