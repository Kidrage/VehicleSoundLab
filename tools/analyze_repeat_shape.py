"""Repeated exterior descents at matched observed ridge; no runtime calibration."""
import csv
from dataclasses import asdict, replace
import json
from pathlib import Path
from runtime_review import ROOT, sha
from reference_segments import read_segment
from spectral_coordinates import ShapeSettings, smooth_spectra
from matched_shapes import descending_crossings, at_times, shape_difference, window_band_powers
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT = ROOT/'references/analysis/repeat_shape_v1'
TRACKS = ROOT/'references/analysis/rev_descent_v1/results.json'
TARGETS = [180., 200., 220., 240., 260.]
BANDS = [(28, 400), (400, 1200), (1200, 3000), (3000, 8000), (8000, 16000)]


def controls():
    # An affine log spectrum can be checked independently without an FFT.
    frequency = 2**np.linspace(np.log2(600), np.log2(14000), 200)
    times = np.array([0., .2, .5, .8, 1.])
    q = np.array([.1, .35, .7])
    spatial = np.array([1., .7])[None, :, None]
    values = times[:, None, None]*spatial*np.log2(frequency)[None, None, :]
    sampled = at_times(times, values, q)
    truth = q[:, None, None]*spatial*np.log2(frequency)[None, None, :]
    error = float(abs(sampled-truth).max())
    assert error < 1e-13
    expected_shape = 3*np.exp(-.5*(np.log2(frequency/3500)/.35)**2)
    second = sampled+expected_shape+np.array([2., -7., 10.])[:, None, None]
    metrics, _ = shape_difference(frequency, sampled, second)
    mask = (frequency >= 1500) & (frequency <= 8000)
    expected_rms = float(np.std(expected_shape[mask]))
    assert np.max(abs(np.asarray(metrics['mean_removed_shape_RMS_db'])-expected_rms)) < 1e-13
    gain_only, _ = shape_difference(frequency, sampled, sampled+13.7)
    assert np.max(gain_only['mean_removed_shape_RMS_db']) < 1e-13
    rows = [dict(seconds=t, hz=300-150*t) for t in times]
    crossings = descending_crossings(rows, TARGETS)
    assert all(r['status'] == 'single_descending_crossing' for r in crossings)
    assert max(abs(r['seconds']-(300-r['target_hz'])/150) for r in crossings) < 1e-15
    ambiguous = descending_crossings([dict(seconds=t, hz=f) for t, f in enumerate([300, 180, 300, 180])], [220])
    assert ambiguous[0]['status'] == 'ambiguous_or_missing_crossing'
    rejected = False
    try:
        at_times(times, values, [-.1])
    except ValueError:
        rejected = True
    assert rejected
    # Complete known OSC pipeline: same fixed-Hz amplitude law, different
    # descent rates/phases. Any apparent paired difference is analysis/sweep
    # behavior, despite no change in the generating spectral recipe.
    rate = 48000
    t = np.arange(round(1.7*rate))/rate
    generated, query, frequency_paths = [], [], []
    for start, half_seconds, phase_offset in [(330, 1.10, 0.), (290, 1.45, .47)]:
        alpha = np.log(2)/half_seconds
        upper = start*np.exp(-alpha*t)
        root = upper/5
        phase = 2*np.pi*start/5*(1-np.exp(-alpha*t))/alpha
        x = np.zeros((len(t), 2))
        for order in range(1, 257):
            hz = order*root
            envelope = (.1+np.exp(-.5*(np.log2(hz/1800)/.3)**2)
                +.6*np.exp(-.5*(np.log2(hz/4500)/.35)**2))*np.exp(-hz/6500)
            for c in range(2):
                x[:, c] += .018/order**.6*envelope*np.cos(order*phase+.3*order+.23*c+phase_offset)
        generated.append(x)
        query.append(np.log(start/np.asarray(TARGETS))/alpha)
        frequency_paths.append(dict(upper_start_hz=start, half_frequency_seconds=half_seconds,
                                    phase_offset=phase_offset))
    runs = {}
    for window in [.04, .08, .128]:
        settings = replace(ShapeSettings(), window_seconds=window)
        samples = []
        for x, tt in zip(generated, query):
            hz, at, db = smooth_spectra(x, rate, settings)
            samples.append(at_times(at, db, tt))
        result, _ = shape_difference(hz, *samples)
        runs[str(window)] = result
    # Full-pipeline gain/channel invariance, and raw power Parseval check.
    # Use supported broadband energy for this invariant: zero/silent bins
    # clipped to the analysis log floor cannot retain exact dB gain shifts.
    gain_input = generated[0]+np.random.default_rng(48271).normal(0, .01, generated[0].shape)
    hz, at, db = smooth_spectra(gain_input, rate)
    _, _, db2 = smooth_spectra(gain_input[:, ::-1]*.25, rate)
    gain_error = float(abs(db2-(db[:, ::-1]+20*np.log10(.25))).max())
    assert gain_error < 1e-10
    _, parseval = window_band_powers(generated[0], rate, .8, .08, BANDS)
    return dict(result='pass', affine_interpolation_max_error=error,
        analytic_shape_RMS_db=expected_rms, gain_only_shape_RMS_db=gain_only['mean_removed_shape_RMS_db'],
        missing_or_multiple_crossings_rejected=True, extrapolation_rejected=True,
        complete_pipeline_gain_channel_swap_max_db_error=gain_error,
        Parseval= parseval, identical_recipe_OSC_sweep_control=dict(
            paths=frequency_paths, root_coordinate='upper /5 chosen for a known synthetic control; no assignment to reference',
            cases=runs, meaning='Nonzero paired differences can arise from finite windows, different sweep rates and phases despite identical instantaneous amplitude law. Not an estimate to subtract from reference.'))


def matched_runs(audio, rate, provenance, saved):
    runs, curves = {}, {}
    for view in ['mean_power', 'L', 'R']:
        pairing = []
        for event in ['first', 'second']:
            key = f'{event}_upper_128ms_{view}'
            track = saved['runs'][key]
            assert track['status'] == 'connected_peak_path' and track['support_fraction'] == 1
            crossing = descending_crossings(track['rows'], TARGETS)
            pairing.append(dict(track=key, crossings=crossing))
        if not all(r['status'] == 'single_descending_crossing' for p in pairing for r in p['crossings']):
            runs[view] = dict(status='ambiguous_or_missing_crossing', pairing=pairing)
            continue
        pair_times = np.array([[r['seconds'] for r in p['crossings']] for p in pairing])
        for window in [.04, .08, .128]:
            for smoothing in [.125, .25]:
                settings = replace(ShapeSettings(), window_seconds=window, smoothing_octaves=smoothing)
                hz, at, db = smooth_spectra(audio, rate, settings)
                at += provenance['source_seconds'][0]
                offsets = [(0., 0.)]
                if view == 'mean_power' and window == .08 and smoothing == .125:
                    offsets += [(-.02, 0.), (.02, 0.), (0., -.02), (0., .02)]
                for offsets_pair in offsets:
                    key = f'{view}_{window:g}s_smooth{smoothing:g}_offset{offsets_pair[0]:g}_{offsets_pair[1]:g}'
                    times = pair_times+np.asarray(offsets_pair)[:, None]
                    samples = [at_times(at, db, tt) for tt in times]
                    metrics, delta = shape_difference(hz, *samples)
                    powers, support = [], []
                    for tt in times:
                        group, windows = [], []
                        for centre in tt:
                            p, data = window_band_powers(audio, rate,
                                centre-provenance['source_seconds'][0], window, BANDS)
                            group.append(p);windows.append(data)
                        powers.append(np.asarray(group));support.append(windows)
                    assert np.min(powers) > 0
                    band_delta = 10*np.log10(powers[1]/powers[0])
                    runs[key] = dict(status='measured', targets_hz=TARGETS, pairing=pairing,
                        settings=asdict(settings), centre_offsets_seconds=list(offsets_pair),
                        paired_source_seconds=times.tolist(), log_shape=metrics,
                        band_power_ratio_second_over_first_db=band_delta.tolist(),
                        bands_hz=BANDS, raw_window_support_relative_to_segment=support)
                    if view == 'mean_power' and window == .08 and smoothing == .125 and offsets_pair == (0., 0.):
                        curves = dict(frequency=hz, first=samples[0], second=samples[1],
                                      shape_delta=delta, times=times, band_delta=band_delta)
    return runs, curves


def plots(curves, runs):
    hz = curves['frequency']
    mask = (hz >= 1500) & (hz <= 8000)
    fig, axes = plt.subplots(2, 2, figsize=(12, 7.5), constrained_layout=True)
    colors = plt.cm.viridis(np.linspace(.05, .9, len(TARGETS)))
    for c in range(2):
        for i, (target, color) in enumerate(zip(TARGETS, colors)):
            delta = curves['second'][i, c, mask]-curves['first'][i, c, mask]
            axes[0, c].semilogx(hz[mask], delta, color=color, label=f'{target:g} Hz coordinate')
            axes[1, c].semilogx(hz[mask], delta-delta.mean(), color=color)
        axes[0, c].set(title=f'Observation {"LR"[c]}: second minus first', ylabel='Log-PSD change / dB', ylim=(-14, 7))
        axes[1, c].set(ylabel='After frequency-bin mean removal / dB', xlabel='Hz', ylim=(-7, 7))
        axes[0, c].legend(fontsize=8)
        for a in axes[:, c]:
            a.grid(alpha=.2);a.axhline(0, color='gray', lw=.7)
    fig.suptitle('A repeated descents at the same observed ridge, not matched RPM/load\n80 ms Hann, 1/8-octave log-PSD smoothing; no waveform gain or cleaning')
    fig.savefig(OUT/'paired_shapes.png', dpi=150);plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), constrained_layout=True)
    for c, ax in enumerate(axes):
        for i, (target, color) in enumerate(zip(TARGETS, colors)):
            ax.plot(np.arange(len(BANDS)), curves['band_delta'][i, :, c], 'o-', color=color, label=f'{target:g} Hz')
        ax.axhline(0, color='gray', lw=.7)
        ax.set(xticks=np.arange(len(BANDS)), xticklabels=[f'{lo:g}–{hi:g}' for lo, hi in BANDS],
            ylabel='Second / first window power / dB', xlabel='Raw frequency band / Hz',
            title=f'Observation {"LR"[c]} / unchanged source gain')
        ax.grid(alpha=.2);ax.legend(fontsize=8)
    fig.suptitle('Hann-window raw PSD integrals; separate from mean-removed log-spectrum shape')
    fig.savefig(OUT/'paired_band_levels.png', dpi=150);plt.close(fig)


def main():
    if OUT.exists() and any(OUT.iterdir()):
        raise SystemExit('Preserve completed repeat_shape_v1; use a new version.')
    OUT.mkdir(parents=True, exist_ok=True)
    known = controls()
    audio, rate, provenance = read_segment('A_exterior_blips', 'exterior_dynamic_observation')
    saved = json.loads(TRACKS.read_text(encoding='utf-8'))
    assert provenance['master_sha256'] == saved['reference']['master_sha256']
    # Verify the saved path evidence against its immutable analysis snapshot.
    manifest_path = ROOT/'baselines/observed_dna_v1/manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    matches = [f for f in manifest['files'] if f['sha256'] == sha(TRACKS)]
    assert len(matches) >= 1
    runs, curves = matched_runs(audio, rate, provenance, saved)
    assert curves
    plots(curves, runs)
    np.savez_compressed(OUT/'primary_arrays.npz', **curves)
    primary_key = 'mean_power_0.08s_smooth0.125_offset0_0'
    primary = runs[primary_key]
    with (OUT/'summary.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream)
        writer.writerow(['run', 'coordinate_hz', 'first_source_seconds', 'second_source_seconds',
            'L_logPSD_mean_delta_db', 'R_logPSD_mean_delta_db', 'L_shape_RMS_db', 'R_shape_RMS_db'])
        for key, row in runs.items():
            if row['status'] != 'measured':
                continue
            for i, target in enumerate(TARGETS):
                writer.writerow([key, target, row['paired_source_seconds'][0][i], row['paired_source_seconds'][1][i],
                    *row['log_shape']['mean_log_PSD_change_db'][i], *row['log_shape']['mean_removed_shape_RMS_db'][i]])
    native_manifest_path = ROOT/'baselines/v0.19.0/manifest.json'
    native = json.loads(native_manifest_path.read_text(encoding='utf-8'))
    preserved = {}
    for item in native['files']:
        if item['path'].startswith(('src/', 'tests/')) or item['path'] == 'CMakeLists.txt':
            assert sha(ROOT/item['path']) == item['sha256'], item['path']
            preserved[item['path']] = item['sha256']
        elif item['path'].startswith('bin/'):
            path = ROOT/'build-v019/Release'/Path(item['path']).name
            assert sha(path) == item['sha256'], str(path)
            preserved[path.relative_to(ROOT).as_posix()] = item['sha256']
    exploration = ROOT/'references/analysis/rev_direction_v1/exploration'
    result = dict(study='repeat_shape_v1', runtime='0.19.0 unchanged', previous_goal_turn='progress',
        reference=provenance, reference_processing='None; stereo decoded float32 read unchanged, no new reference WAV.',
        tracks=dict(path=TRACKS.relative_to(ROOT).as_posix(), sha256=sha(TRACKS),
            frozen_manifest=manifest_path.relative_to(ROOT).as_posix(), frozen_manifest_sha256=sha(manifest_path),
            limitation='The second descent has connected128ms paths only; saved80/192ms runs failed. All three coordinate views are dependent observations.'),
        primary_key=primary_key, primary=primary, runs=runs, controls=known,
        selection='Five fixed targets inside the two saved upper-ridge ranges. Single descending crossings only. No equal-RPM/order/load assertion.',
        exploration=dict(files={p.relative_to(ROOT).as_posix():sha(p) for p in sorted(exploration.iterdir()) if p.is_file()},
            result='Two manually anchored whole rise/fall intervals failed at40/80/128ms with8oct/s bound. No rise-side matching or runtime calibration is supported.'),
        native_preserved=preserved, native_manifest_sha256=sha(native_manifest_path),
        limits=['Same observed frequency does not prove same physical order or RPM across repetitions.',
            'No independent pedal, load, fuel state or acoustic transfer measurement; cannot assign differences to a specific layer.',
            'Window averaging, chirp rate/phase, channel transfer, noise and encoding can change spectra; controls show a nonzero difference without a recipe change.',
            'Sensitivity settings and targets use overlapping data, not independent trials, confidence intervals or a realism score.',
            'Log-PSD bin means are geometric statistics, not integrated band levels. Raw band powers are separately calculated with Parseval checks.',
            'No baseline, default voice, driving policy, playback routing, pending listening question or source media was changed.'],
        tools={f'tools/{name}':sha(ROOT/'tools'/name) for name in ['analyze_repeat_shape.py', 'matched_shapes.py', 'spectral_coordinates.py', 'reference_segments.py']})
    result['files'] = {p.name:sha(p) for p in sorted(OUT.iterdir()) if p.is_file()}
    (OUT/'results.json').write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps(dict(primary=primary['log_shape'], band_power_delta=primary['band_power_ratio_second_over_first_db'],
        total_runs=len(runs), controls=known), indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
