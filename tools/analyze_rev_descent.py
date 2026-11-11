"""Relative coastdown observations of approved exterior A; no runtime retuning."""
import csv
from dataclasses import asdict
import json
import math
from pathlib import Path
from runtime_review import ROOT, sha
from reference_segments import read_segment
from ridge_tracks import RidgeSettings, spectrogram, follow, descent_metrics
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT = ROOT/'references/analysis/rev_descent_v1'
WINDOWS = [.080, .128, .192]
VIEWS = ['mean_power', 'L', 'R']
# Manually chosen from a spectrogram of the canonical segment, not ECU events.
# The shorter lower-ridge windows avoid the near-100-Hz line overlap.
REGIONS = {
    'first_upper': [238.18, 239.00, 315],
    'first_lower': [238.18, 238.80, 189],
    'second_upper': [240.90, 241.70, 278],
    'second_lower': [240.90, 241.60, 168],
}


def controls():
    """Known chirps, stationary resonances, channel changes and missing lines."""
    rate = 48000
    t = np.arange(round(1.6*rate))/rate
    settings = RidgeSettings()
    reports = {}
    for name in ['fall', 'rise', 'even_only', 'dropout', 'stationary_only']:
        base = 63*2**(t-1 if name == 'rise' else -t)
        phase = 2*np.pi*np.cumsum(base)/rate
        orders = list(range(2, 11, 2) if name == 'even_only' else range(1, 11))
        envelope = np.ones(len(t))
        if name == 'dropout':
            envelope[(t > .65) & (t < .95)] = 0
        if name == 'stationary_only':
            envelope[:] = 0
        rng = np.random.default_rng(48271)
        x = np.zeros((len(t), 2))
        for order in orders:
            for c in range(2):
                x[:, c] += (.08/order**.6 * (1-.18*c) * envelope *
                    np.cos(order*phase+.3*order+.2*c))
        # Deliberately different channel amplitudes and phases; no mono mix.
        for c in range(2):
            x[:, c] += (.06*np.cos(2*np.pi*100*t+.5*c) +
                .03*np.cos(2*np.pi*840*t) + rng.normal(0, .0002, len(t)))
        hz, times, power = spectrogram(x, rate, settings)
        selected_order = 6 if name == 'even_only' else 5
        anchor = selected_order*float(np.interp(.2, t, base))
        observations = {}
        for view in VIEWS:
            p = power.mean(axis=1) if view == 'mean_power' else power[:, VIEWS.index(view)-1, :]
            track = follow(hz, times, p, .2, 1.2, anchor, settings)
            item = dict(status=track['status'], support_fraction=track.get('support_fraction'))
            if track['rows']:
                tt = np.array([r['seconds'] for r in track['rows']])
                estimate = np.array([r['hz'] for r in track['rows']])
                truth = selected_order*np.interp(tt, t, base)
                cents = 1200*np.log2(estimate/truth)
                item['absolute_error_cents_p50_p95_max'] = np.percentile(abs(cents), [50, 95, 100]).tolist()
                item['metrics'] = descent_metrics(track['rows'])
            if name in ['fall', 'rise', 'even_only']:
                assert track['status'] == 'connected_peak_path', (name, view)
                assert item['absolute_error_cents_p50_p95_max'][1] < 15, (name, view, item)
                expected_sign = 1 if name == 'rise' else -1
                assert item['metrics']['mean_octaves_per_second']*expected_sign > .9
                assert track['support_fraction'] == 1
            else:
                assert track['status'] == 'no_connected_path', (name, view)
            observations[view] = item
        reports[name] = dict(base_hz_formula='63 * 2**(t-1)' if name == 'rise' else '63 * 2**(-t)',
            emitted_family_orders=orders if name != 'stationary_only' else [],
            selected_ridge_order=selected_order, views=observations)
    # Two different hidden fundamentals generate exactly the same observations.
    # A missing odd-order family is compatible with a doubled hidden base.
    base = 63*2**(-t)
    phase = 2*np.pi*np.cumsum(base)/rate
    one = sum(.08/n**.6*np.cos(n*phase+.3*n) for n in range(2, 11, 2))
    two = sum(.08/(2*n)**.6*np.cos(n*(2*phase)+.6*n) for n in range(1, 6))
    error = float(np.max(abs(one-two)))
    assert error < 1e-12
    reports['hidden_base_nonidentifiability'] = dict(
        maximum_waveform_difference=error,
        description='63*2^-t Hz with orders 2,4,6,8,10 and 126*2^-t Hz with orders 1..5 produce the same waveform. An anchored ridge does not establish the hidden base or crank order.')
    return reports


def source_tracks():
    audio, rate, provenance = read_segment('A_exterior_blips', 'exterior_dynamic_observation')
    runs = {}
    plot_data = None
    for window in WINDOWS:
        settings = RidgeSettings(window_seconds=window)
        hz, times, power = spectrogram(audio, rate, settings)
        times += provenance['source_seconds'][0]
        if window == .128:
            plot_data = (hz, times, power.mean(axis=1))
        for view in VIEWS:
            p = power.mean(axis=1) if view == 'mean_power' else power[:, VIEWS.index(view)-1, :]
            for region, (start, stop, anchor) in REGIONS.items():
                track = follow(hz, times, p, start, stop, anchor, settings)
                track.update(region=region, view=view, settings=asdict(settings),
                    selected_centre_interval_seconds=[start, stop], anchor_hz=anchor,
                    metrics=descent_metrics(track['rows']))
                key = f'{region}_{round(window*1000)}ms_{view}'
                runs[key] = track
    with (OUT/'tracks.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['run', 'source_seconds', 'ridge_hz', 'dbfs_per_hz', 'prominence_db', 'relative_level_supported'])
        for key, run in runs.items():
            writer.writerows([key, r['seconds'], r['hz'], r['dbfs_per_hz'],
                r['prominence_db'], r['level_supported']] for r in run['rows'])
    # Retain every failed run. There is no relaxed-threshold retry or hidden fill.
    failures = [key for key, run in runs.items() if run['status'] != 'connected_peak_path']
    primary = [run for run in runs.values() if run['region'] == 'first_upper']
    assert len(primary) == 9 and all(r['status'] == 'connected_peak_path' and r['support_fraction'] == 1 for r in primary)
    coherence = []
    for window in WINDOWS:
        for view in VIEWS:
            prefix = f'{round(window*1000)}ms_{view}'
            for event in ['first', 'second']:
                upper = runs[f'{event}_upper_{prefix}']['rows']
                lower = runs[f'{event}_lower_{prefix}']['rows']
                if not upper or not lower:
                    continue
                tt = np.array([r['seconds'] for r in lower])
                ratio = np.array([r['hz'] for r in lower])/np.interp(tt,
                    [r['seconds'] for r in upper], [r['hz'] for r in upper])
                coherence.append(dict(event=event, window_seconds=window, view=view,
                    lower_to_upper_ratio_p05_p50_p95=np.percentile(ratio, [5, 50, 95]).tolist(),
                    relative_to_three_fifths_error_percent_p95=float(np.percentile(abs(ratio/.6-1)*100, 95)),
                    interpretation='Three-fifths is a descriptive frequency-family ratio, not an identified physical order.'))
    summary = dict(total_runs=len(runs), connected_runs=len(runs)-len(failures), failed_runs=failures,
        first_upper_endpoint_ratio_range=[min(r['metrics']['endpoint_ratio'] for r in primary), max(r['metrics']['endpoint_ratio'] for r in primary)],
        first_upper_log_slope_range_per_second=[min(r['metrics']['log_slope_per_second'] for r in primary), max(r['metrics']['log_slope_per_second'] for r in primary)],
        first_upper_half_frequency_seconds_range=[min(r['metrics']['observed_half_frequency_seconds'] for r in primary), max(r['metrics']['observed_half_frequency_seconds'] for r in primary)],
        precision_warning='Variation across overlapping windows/channels is not a confidence interval. Windows smear 80-192 ms; report approximately 0.8 s, not millisecond timing.',
        frequency_family_coherence=coherence,
        second_region_status='Partial: 128 ms upper-ridge paths connect; 80/192 ms paths fail. Not an independent equally robust calibration.')
    return provenance, runs, summary, plot_data


def model_comparison(primary):
    """Conditional continuous zero-throttle equation from frozen V013 sources."""
    base = ROOT/'baselines/v0.13.0'
    manifest = json.loads((base/'manifest.json').read_text())
    for item in manifest['files']:
        assert sha(base/item['path']) == item['sha256'], item['path']
    source_files = ['src/profiles/vehicle.c', 'src/drive/powertrain.c',
                    'src/profiles/clutch.c', 'src/drive/clutch.c']
    hashes = {}
    for name in source_files:
        assert sha(ROOT/name) == sha(base/name), name
        hashes[name] = sha(base/name)
    # Explicit engineering constants, recorded alongside the frozen source hash.
    inertia, a, b, max_rpm = .22, 35., 55., 8500.
    vehicle = (base/'src/profiles/vehicle.c').read_text()
    assert '1600,70,.22' in vehicle and '600,35,55,.97' in vehicle
    def time_to_rpm(r0, r1):
        scale = inertia*(2*math.pi/60)*max_rpm/math.sqrt(a*b)
        return scale*(math.atan(r0/max_rpm*math.sqrt(b/a))-math.atan(r1/max_rpm*math.sqrt(b/a)))
    trace_path = ROOT/'renders/v0.13.0/neutral_v013.csv'
    with trace_path.open() as f:
        rows = list(csv.DictReader(f))
    frozen_trace = next(x for x in manifest['files'] if x['path'] == 'review/neutral_v013.csv')
    assert sha(trace_path) == frozen_trace['sha256']
    lo, hi = [min(rows, key=lambda r: abs(float(r['seconds'])-at)) for at in [6.505, 7.505]]
    check_rows = [r for r in rows if float(lo['seconds']) <= float(r['seconds']) <= float(hi['seconds'])]
    for r in check_rows:
        assert r['lifecycle'] == 'RUNNING' and int(r['gear']) == 0
        assert float(r['engine_throttle']) == 0 and float(r['clutch_torque_nm']) == 0
    trace_dt = float(hi['seconds'])-float(lo['seconds'])
    model_dt = time_to_rpm(float(lo['rpm']), float(hi['rpm']))
    assert abs(model_dt/trace_dt-1) < .002
    frequencies = primary['metrics']['endpoint_hz']
    cases = []
    for order in [2.5, 5., 7.5]:
        rpm0, rpm1 = [60*f/order for f in frequencies]
        # Idle support only appears below 850+400 in this engineering proxy.
        assert rpm1 > 1250 and rpm0 < max_rpm
        cases.append(dict(assumed_crank_order=order,
            formula='f_Hz = order * RPM / 60', hypothetical_rpm=[rpm0, rpm1],
            continuous_closed_throttle_open_clutch_seconds=time_to_rpm(rpm0, rpm1),
            measured_order=False))
    return dict(source_hashes=hashes, frozen_manifest_sha256=sha(base/'manifest.json'),
        frozen_manifest_files_verified=len(manifest['files']),
        engineering_constants=dict(inertia_kg_m2=inertia, loss_constant_nm=a,
            loss_quadratic_nm=b, max_rpm=max_rpm, idle_rpm=850, idle_window_rpm=400),
        equation='J*d(2*pi*RPM/60)/dt = -(35 + 55*(RPM/8500)^2)',
        domain='RUNNING, zero effective throttle, open clutch, above idle-control window, below limiter, no lifecycle kinematics. Continuous model; not car telemetry.',
        analytic_vs_frozen_trace=dict(trace=str(trace_path.relative_to(ROOT)).replace('\\', '/'),
            sha256=sha(trace_path), seconds=[float(lo['seconds']), float(hi['seconds'])],
            endpoint_rpm=[float(lo['rpm']), float(hi['rpm'])], logged_seconds=trace_dt,
            continuous_formula_seconds=model_dt,
            relative_difference=model_dt/trace_dt-1,
            interpretation='Small expected fixed-step/trace-rounding difference; validates this conditional formula against the frozen simulation.'),
        reference_elapsed_seconds=primary['metrics']['centre_seconds'][1]-primary['metrics']['centre_seconds'][0],
        conditional_order_cases=cases,
        conclusion='The same spectral ridge implies different RPM intervals and model descent times under different possible crank orders. Neutral/zero-throttle/order are not established by A, so no unique loss/inertia correction follows.')


def plots(runs, plot_data, model):
    hz, times, power = plot_data
    fig, axes = plt.subplots(2, 2, figsize=(13, 8), constrained_layout=True)
    for col, (event, limits) in enumerate([('first', [238.05, 239.10]), ('second', [240.75, 241.85])]):
        selected = (hz >= 70) & (hz <= 620)
        axes[0, col].pcolormesh(times, hz[selected],
            10*np.log10(np.maximum(power[selected], 1e-30)),
            shading='auto', cmap='magma', vmin=-65, vmax=-20, rasterized=True)
        for member, color in [('upper', 'cyan'), ('lower', 'lime')]:
            run = runs[f'{event}_{member}_128ms_mean_power']
            if not run['rows']:
                continue
            t = np.array([r['seconds'] for r in run['rows']])
            f = np.array([r['hz'] for r in run['rows']])
            axes[0, col].plot(t, f, color=color, lw=1.2, label=f'{member}: anchored 128 ms')
        axes[0, col].set(xlim=limits, ylim=(70, 620), xlabel='Source seconds', ylabel='Hz', title=f'{event}: manually selected visible ridges')
        axes[0, col].legend(fontsize=8)
        for window in WINDOWS:
            run = runs[f'{event}_upper_{round(window*1000)}ms_mean_power']
            if run['rows']:
                t = np.array([r['seconds'] for r in run['rows']])
                f = np.array([r['hz'] for r in run['rows']])
                axes[1, col].plot(t-t[0], f/f[0], label=f'{round(window*1000)} ms')
            else:
                axes[1, col].plot([], [], '--', label=f'{round(window*1000)} ms: NO PATH')
        axes[1, col].axhline(.5, color='grey', ls='--', lw=.8)
        axes[1, col].set(xlabel='Elapsed from first selected window centre (s)', ylabel='Upper-ridge frequency / initial frequency', ylim=(.44, 1.04))
        axes[1, col].legend(fontsize=8);axes[1, col].grid(alpha=.2)
    fig.suptitle('Approved A: unchanged L/R, mean powers only for selection. Ridges are not RPM telemetry.')
    fig.savefig(OUT/'descent_tracks.png', dpi=150);plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 4), constrained_layout=True)
    cases = model['conditional_order_cases']
    labels = [f'Assume order {c["assumed_crank_order"]:g}\n{c["hypothetical_rpm"][0]:.0f} to {c["hypothetical_rpm"][1]:.0f} RPM' for c in cases]
    ax.bar(labels, [c['continuous_closed_throttle_open_clutch_seconds'] for c in cases], color='#658da4', width=.55)
    ax.axhline(model['reference_elapsed_seconds'], color='#b45309', ls='--', label='Recorded ridge interval (~0.81 s); gear/pedal/order unknown')
    ax.set(ylabel='Elapsed seconds for the selected frequency ratio', title='Order ambiguity changes the model comparison\nFrozen V013 proxy: zero throttle, open clutch; no parameter fit')
    ax.legend(fontsize=8)
    fig.savefig(OUT/'conditional_order_comparison.png', dpi=150);plt.close(fig)


def main():
    if (OUT/'results.json').exists():
        raise SystemExit('Preserve completed observations; use a new analysis version.')
    OUT.mkdir(exist_ok=True, parents=True)
    known = controls()
    provenance, runs, summary, plot_data = source_tracks()
    model = model_comparison(runs['first_upper_128ms_mean_power'])
    plots(runs, plot_data, model)
    result = dict(schema='vsl.relative-rev-descent/1', reference=provenance,
        source_processing='None. Unchanged decoded float32 stereo samples; channels never summed as waveforms. No new reference audio derivative.',
        region_selection='Manual anchor and centre intervals selected from the canonical spectrogram. No pedal-release/neutral/catch labels established.',
        stft=dict(windows_seconds=WINDOWS, hop_seconds=.01, fft_size=32768,
            native_bin_spacings_hz=[1/w for w in WINDOWS], padded_grid_hz=48000/32768,
            caution='Zero padding and peak interpolation do not improve resolving power. Overlapping channel/window results are not independent trials or a statistical confidence interval.'),
        algorithm='Local prominent peaks with parabolic interpolation; anchored maximum-score path with symmetric rate bound and velocity penalty. No monotonic or endpoint constraint; no gap filling or harmonic relabelling.',
        summary=summary, controls=known, runs=runs, conditional_model_comparison=model,
        limits=['No physical crank order, RPM, neutral gear, closed throttle, injector status, engine inertia or loss torque is identified.',
            'The method is for selected visible ridges, not unrestricted speech/music/engine pitch tracking. Stationary tones, overlaps, weak lines and edits can break a path.',
            'Failed window/region runs are retained; secondary-region evidence is partial.',
            'Camera-stationary context reduces obvious fly-by motion but does not measure source/microphone motion or A/V alignment.',
            'Relative audio descent cannot separately identify engine losses/inertia and remaining torque/clutch load.',
            'No DSP, driving constants, presets, binaries or historical listening artifacts changed. No subjective realism conclusion.'],
        tools={str(p.relative_to(ROOT)).replace('\\', '/'):sha(p) for p in [Path(__file__), ROOT/'tools/ridge_tracks.py', ROOT/'tools/reference_segments.py']})
    result['outputs'] = {p.name:sha(p) for p in sorted(OUT.iterdir()) if p.is_file()}
    (OUT/'results.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(dict(summary=summary, conditional_model_comparison=model), indent=2))


if __name__ == '__main__':
    main()
