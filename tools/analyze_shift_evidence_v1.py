"""Measure E's five shifts without changing C or accepted sound profiles."""
import argparse
import json
from pathlib import Path
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(args.workspace / 'tools/python_deps'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from drive_evidence_v1.sources import read, sha
from drive_evidence_v1.family import follow
from shift_evidence_v1.spectrum import observe, region_stats, BANDS, RELATIVE_BANDS
from shift_evidence_v1.timing import descent, delay_intervals, guided_peaks

args.out.mkdir(parents=True, exist_ok=False)
audio, provenance = read(args.workspace, 'E_corsa_second_context', 'cabin_dynamic_observation')
annotation_path = repo / 'research/drive_evidence_v1_annotations.json'
annotation = json.loads(annotation_path.read_text(encoding='utf-8'))
report = dict(schema='vsl.shift-evidence/1', provenance=provenance,
    annotation_sha256=sha(annotation_path), band_hz=BANDS,
    relative_clock_bands=RELATIVE_BANDS, analyses=[], human_accepted=False,
    limits=['E cabin, five upshifts only; gear display intervals are coarse',
        'No independent A/V offset or cluster latency',
        'No pedal, torque, injector or clutch telemetry',
        'Band correlation is not physical source separation',
        'Short Hann windows smear events; FFT padding does not improve time resolution',
        'Same pitch does not imply same load, speed, gear, position or acoustic path',
        'No C, runtime model, or accepted baseline changes'])
fig, axes = plt.subplots(5, 3, figsize=(14, 15), constrained_layout=True)
for window_ms in (80, 60, 40):
    observed = observe(audio, provenance['seconds'][0], window_ms)
    family = follow(observed['hz'], observed['seconds'], observed['power_low'],
        83, 94.01, 64.5, max_octaves_per_second=32)
    if window_ms == 80:
        assert family['status'] == 'connected_observed_family'
        ft = np.array([r['seconds'] for r in family['rows']])
        ff = np.array([r['reference_hz'] for r in family['rows']])
        support = np.array([r['independent_line_support'] for r in family['rows']])
        guide_times, guide_hz = ft.copy(), ff.copy()
        tracking = 'Continuous multi-line path, anchored at83s / root64.5Hz'
    else:
        ft, ff, support = guided_peaks(observed, guide_times, guide_hz)
        tracking = ('Observed peaks conditioned on80ms path, within max12Hz/4%; '
                    'prominence>=4dB and power>=-30dB relative to low-band maximum; '
                    'missing measurements are NaN, not filled')
    # Re-observe with frequency-integration boundaries following the80ms
    # acoustic guide. This is not physical order identification or separation.
    observed = observe(audio, provenance['seconds'][0], window_ms, clock=(guide_times, guide_hz))
    relative_observed = dict(observed, power_LR=observed['relative_power_LR'],
                             cross_LR=observed['relative_cross_LR'])
    events = []
    for index, display in enumerate(annotation['gear_display_changes']):
        event = descent(ft, ff, display['last_old_seconds'] - .7, display['first_new_seconds'] + .1)
        at = event['marker_seconds']
        event['display'] = display
        event['before'] = region_stats(observed, at - .20, at - .10)
        event['after'] = region_stats(observed, at + .10, at + .20)
        pre, post = np.array(event['before']['power_LR']), np.array(event['after']['power_LR'])
        event['band_after_minus_before_db_LR'] = (10 * np.log10(post / pre)).tolist()
        event['relative_before'] = region_stats(relative_observed, at - .20, at - .10)
        event['relative_after'] = region_stats(relative_observed, at + .10, at + .20)
        event['relative_band_after_minus_before_db_LR'] = (10 * np.log10(
            np.array(event['relative_after']['power_LR']) /
            np.array(event['relative_before']['power_LR']))).tolist()
        # Same-reference-frequency comparison on the preceding ascent. Keep
        # both windows so speed/gear/recording changes remain explicit.
        lower = 83.0 if index == 0 else events[-1]['marker_seconds'] + .30
        candidates = np.flatnonzero((ft >= lower + .05) & (ft <= at - .30) & np.isfinite(ff))
        matched = None
        if len(candidates):
            target = event['after_hz']
            nearest = candidates[np.argmin(abs(ff[candidates] - target))]
            stamp = float(ft[nearest])
            error = float(abs(ff[nearest] / target - 1))
            if error <= .015:
                stats = region_stats(observed, stamp - .05, stamp + .05)
                before_f = ff[(ft >= stamp - .05) & (ft < stamp + .05)]
                before_f = before_f[np.isfinite(before_f)]
                root_error = float(abs(np.median(before_f) / target - 1))
                if root_error <= .02:
                    matched = dict(ascent=stats, reference_ratio=float(np.median(before_f) / target),
                        after_minus_ascent_db_LR=(10 * np.log10(post / np.array(stats['power_LR']))).tolist(),
                        warning='Pitch-matched observation only; speed/gear/load/path are not controlled')
        event['pitch_matched_ascent'] = matched
        events.append(event)
        if window_ms == 80:
            scope = (ft >= at - .6) & (ft <= at + .65)
            axes[index, 0].plot(ft[scope] - at, ff[scope], lw=1)
            axes[index, 0].set_ylabel(f"{display['from']}->{display['to']} | Hz")
            times = observed['seconds']
            keep = (times >= at - .6) & (times <= at + .65)
            powers = observed['power_LR'].mean(axis=0)
            base = pre.mean(axis=0)
            for band in (1, 3, 4):
                axes[index, 1].plot(times[keep] - at,
                    10 * np.log10(powers[band, keep] / base[band]), label=str(BANDS[band]))
            cross = observed['cross_LR']
            power = observed['power_LR']
            for band in (1, 4):
                rho = cross[band] / np.sqrt(np.maximum(power[0, band] * power[1, band], 1e-60))
                axes[index, 2].plot(times[keep] - at, abs(rho[keep]), label=str(BANDS[band]))
            for column in range(3):
                axes[index, column].axvline(0, color='grey', lw=.7)
            axes[index, 2].set_ylim(0, 1.03)
    result = dict(window_ms=window_ms, status='observed', events=events,
        full_continuity_status=family['status'], tracking=tracking,
        measured_peak_fraction=float(np.isfinite(ff).mean()),
        fraction_two_independent_support_lines=float(np.mean((support > 0).sum(axis=1) >= 2)),
        delay=delay_intervals(events))
    report['analyses'].append(result)
    np.savez_compressed(args.out / f'window_{window_ms}.npz',
        seconds=observed['seconds'], band_power_LR=observed['power_LR'],
        band_cross_LR=observed['cross_LR'], family_seconds=ft, reference_hz=ff, support=support)
    print(json.dumps(dict(window_ms=window_ms, markers=[e['marker_seconds'] for e in events],
        durations=[e['acoustic_25_75_duration_seconds'] for e in events],
        delay=result['delay']['common_intersection_seconds'])), flush=True)
axes[0, 0].set_title('Tracked reference; acoustic coordinate')
axes[0, 1].set_title('Band power / pre-window (dB)')
axes[0, 2].set_title('Magnitude of integrated complex L/R correlation')
axes[0, 1].legend(fontsize=8)
axes[0, 2].legend(fontsize=8)
for axis in axes[-1]:
    axis.set_xlabel('Seconds relative to persistent acoustic descent; not ECU time')
fig.savefig(args.out / 'shifts.png', dpi=140)
plt.close(fig)
report['source_sha256'] = {p.relative_to(repo).as_posix(): sha(p) for p in
    [Path(__file__), repo/'tools/drive_evidence_v1/sources.py', repo/'tools/drive_evidence_v1/family.py',
     *sorted((repo/'tools/shift_evidence_v1').glob('*.py'))]}
(args.out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
