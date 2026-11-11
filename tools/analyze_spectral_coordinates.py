"""Past-only conditional high-frequency shape evidence; no native retuning."""
import csv
import json
from dataclasses import asdict, replace
from runtime_review import ROOT, sha
from reference_segments import read_segment
from spectral_coordinates import ShapeSettings, smooth_spectra, fit, predict, compare
import numpy as np
import soundfile as sf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT = ROOT/'references/analysis/spectral_coordinates_log_v1'
TRACKS = ROOT/'references/analysis/rev_descent_v1/results.json'
SMOOTHING = [.125, .25]


def controls():
    settings = ShapeSettings()
    frequency = np.geomspace(600, 14000, 220)
    times = np.arange(100)*.01
    ridge = 300*2**(-times)
    fixed = -18*np.exp(-(np.log2(frequency/4200)/.25)**2)
    moving = 15*np.exp(-(np.log2(frequency[None, :]/ridge[:, None]/18)/.24)**2)
    cases = {}
    for name, shape in [('fixed', np.broadcast_to(fixed, moving.shape)), ('moving', moving),
                        ('combined', fixed+moving)]:
        db = np.stack((shape, .7*shape), axis=1)
        row = compare(frequency, times, ridge, db, settings)
        score = row['spectral_shape_rmse_db_lr']
        assert row['status'] == 'measured'
        if name in ['fixed', 'moving']:
            other = 'moving' if name == 'fixed' else 'fixed'
            assert max(score[name]) < .12 and score[other][0] > 1.5, (name, score)
        else:
            assert score['combined'][0] < min(score['fixed'][0], score['moving'][0])*.25, score
        # A constant scaling of the conditioning ridge cannot identify an order.
        scaled = compare(frequency, times, ridge*2, db+np.arange(len(times))[:, None, None], settings)
        for method in score:
            assert np.max(abs(np.asarray(score[method])-scaled['spectral_shape_rmse_db_lr'][method])) < 1e-6
        cases[name] = row
    flat_ridge = np.full(len(times), 250.)
    constant = compare(frequency, times, flat_ridge,
        np.stack((moving, .7*moving), axis=1), settings)
    assert np.max(abs(np.asarray(constant['spectral_shape_rmse_db_lr']['fixed'])-
                      constant['spectral_shape_rmse_db_lr']['moving'])) < 1e-6
    cases['constant_ridge_cannot_distinguish_coordinates'] = constant
    # Full STFT/smoothing pipeline, deterministic additive OSC only.
    rate = 48000
    t = np.arange(rate*2)/rate
    alpha = np.log(1.5)/2
    f0 = 90*np.exp(-alpha*t)
    phase = 2*np.pi*90*(1-np.exp(-alpha*t))/alpha
    waves = {}
    for name in ['fixed', 'moving']:
        audio = np.zeros((len(t), 2))
        for n in range(1, 241):
            envelope = (.05+np.exp(-(np.log2(n*f0/5000)/.3)**2) if name == 'fixed'
                        else .05+np.exp(-(np.log2(n/70)/.3)**2))
            for c in range(2):
                audio[:, c] += .02/np.sqrt(n)*envelope*np.cos(n*phase+.3*n+.23*c)
        hz, at, db = smooth_spectra(audio, rate, settings)
        row = compare(hz, at, 90*np.exp(-alpha*at), db, settings)
        score = row['spectral_shape_rmse_db_lr']
        other = 'moving' if name == 'fixed' else 'fixed'
        assert score[name][0] < score[other][0]*.5, (name, score)
        waves[name] = row
    return dict(result='pass', analytic_spectral_shapes=cases, noiseless_OSC_pipeline=waves,
                meaning='Known-coordinate recovery, ridge-scale/log-level invariance, no-sweep ambiguity, and complete deterministic OSC analysis controls. No physical noise or source inference.')


def reference_runs():
    saved = json.loads(TRACKS.read_text(encoding='utf-8'))
    audio, rate, provenance = read_segment('A_exterior_blips', 'exterior_dynamic_observation')
    assert provenance['master_sha256'] == saved['reference']['master_sha256']
    names = ['first_upper_80ms_mean_power', 'first_upper_128ms_mean_power',
             'first_upper_192ms_mean_power', 'second_upper_128ms_mean_power']
    output = {}
    arrays = {}
    for smoothing in SMOOTHING:
        settings = replace(ShapeSettings(), smoothing_octaves=smoothing)
        hz, at, db = smooth_spectra(audio, rate, settings)
        at += provenance['source_seconds'][0]
        for name in names:
            track = saved['runs'][name]
            assert track['status'] == 'connected_peak_path' and track['support_fraction'] == 1
            tt = np.array([r['seconds'] for r in track['rows']])
            ff = np.array([r['hz'] for r in track['rows']])
            selected = (at >= tt[0]) & (at <= tt[-1])
            ridge = np.interp(at[selected], tt, ff)
            key = name+f'_smooth{smoothing:g}'
            row = compare(hz, at[selected], ridge, db[selected], settings)
            row.update(settings=asdict(settings), observed_ridge_endpoints_hz=[float(ridge[0]), float(ridge[-1])],
                       conditioning='Saved offline anchored ridge, not an identified crank order/RPM. Its full path is conditioned on, not forecast.',
                       reference=provenance)
            output[key] = row
            if name == 'first_upper_128ms_mean_power' and smoothing == .125:
                arrays['reference'] = (hz, at[selected], ridge, db[selected])
    return output, arrays


def native_runs():
    source = ROOT/'renders/exhaust_phase_v1'
    primary = json.loads((source/'results.json').read_text(encoding='utf-8'))
    original = ROOT/'renders/v0.16.0/neutral_base.csv'
    expected = json.loads((ROOT/'renders/v0.16.0/verification.json').read_text())['files'][original.name]
    assert sha(original) == expected
    with original.open() as stream:
        rows = list(csv.DictReader(stream))
    tt = np.array([float(r['seconds']) for r in rows])
    rpm = np.array([float(r['rpm']) for r in rows])
    arrays = {}
    mix, rate = sf.read(source/'neutral_base.wav', always_2d=True)
    inputs = {str(original.relative_to(ROOT)).replace('\\', '/'): sha(original)}
    assert sha(source/'neutral_base.wav') == primary['files']['neutral_base.wav']
    arrays['native_mix'] = mix
    for name, objects in [('native_exhaust', ['exhaust_left', 'exhaust_right']),
                          ('native_air', ['air_left', 'air_right'])]:
        audio = []
        for obj in objects:
            path = source/f'neutral_base_source_{obj}.wav'
            assert sha(path) == primary['files'][path.name]
            inputs[str(path.relative_to(ROOT)).replace('\\', '/')] = sha(path)
            x, sr = sf.read(path)
            assert sr == rate
            audio.append(x)
        arrays[name] = np.column_stack(audio)
    inputs[str((source/'neutral_base.wav').relative_to(ROOT)).replace('\\', '/')] = sha(source/'neutral_base.wav')
    output, plot_arrays = {}, {}
    for name, audio in arrays.items():
        for smoothing in SMOOTHING:
            settings = replace(ShapeSettings(), smoothing_octaves=smoothing)
            hz, at, db = smooth_spectra(audio, rate, settings)
            selected = (at >= 6.45) & (at <= 7.85)
            # The exported trace has drive RPM, not the exact 18ms-smoothed
            # audio clock. It is a declared conditioning proxy only.
            ridge = np.interp(at[selected], tt, rpm)*10/240
            row = compare(hz, at[selected], ridge, db[selected], settings)
            row.update(settings=asdict(settings), seconds=[6.45, 7.85],
                       conditioning='Frozen engineering drive RPM *10/240; approximate proxy for audio phase clock (18ms smoothing is not exported). Not exact order tracking.',
                       coordinate_endpoints_hz=[float(ridge[0]), float(ridge[-1])])
            output[name+f'_smooth{smoothing:g}'] = row
            if smoothing == .125:
                plot_arrays[name] = (hz, at[selected], ridge, db[selected])
    return output, inputs, plot_arrays


def plots(references, native, arrays):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), constrained_layout=True)
    groups = [('A first descent', references['first_upper_128ms_mean_power_smooth0.125']),
              ('A second descent', references['second_upper_128ms_mean_power_smooth0.125']),
              ('C mix', native['native_mix_smooth0.125']),
              ('C exhaust objects', native['native_exhaust_smooth0.125']),
              ('C air objects', native['native_air_smooth0.125'])]
    for c, ax in enumerate(axes):
        xx = np.arange(len(groups))
        for j, method in enumerate(['fixed', 'moving', 'combined']):
            ax.bar(xx+(j-1)*.23, [v['spectral_shape_rmse_db_lr'][method][c] for _, v in groups], width=.23, label=method)
        ax.set(xticks=xx, xticklabels=[n.replace(' ', '\n', 1) for n, _ in groups],
               title=f'Channel {"LR"[c]} / independent observation or source', ylabel='Held-out log-spectral shape RMSE / dB')
        ax.legend();ax.grid(axis='y', alpha=.2)
    fig.suptitle('Conditional envelope prediction; no matched RPM/load, phase, level or realism score')
    fig.savefig(OUT/'shape_prediction.png', dpi=160);plt.close(fig)
    hz, at, ridge, db = arrays['reference']
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), constrained_layout=True)
    train = np.arange(20)
    test = np.arange(len(at)-10, len(at))
    for c, ax in enumerate(axes):
        actual = db[test, c].mean(axis=0)
        mask = (hz >= 1500) & (hz <= 8000)
        ax.semilogx(hz[mask], actual[mask]-actual[mask].mean(), color='black', lw=2, label='Observed future mean')
        for method in ['fixed', 'moving', 'combined']:
            estimate, support = predict(fit(hz, ridge[train], db[train, c], method), hz, ridge[test])
            valid = mask & support.all(axis=0)
            y = estimate.mean(axis=0)
            ax.semilogx(hz[valid], y[valid]-y[valid].mean(), label=method)
        ax.set(title=f'A first descent / {"LR"[c]} / illustrated early20 to last10 frames',
               xlabel='Hz', ylabel='Mean-removed log-power shape / dB', xlim=(1500, 8000))
        ax.legend(fontsize=8);ax.grid(alpha=.2)
    fig.savefig(OUT/'future_shape_example.png', dpi=160);plt.close(fig)


def main():
    if (OUT/'results.json').exists():
        raise SystemExit('Preserve completed spectral_coordinates_log_v1.')
    OUT.mkdir(parents=True, exist_ok=True)
    known = controls()
    references, arrays = reference_runs()
    native, inputs, native_arrays = native_runs()
    arrays.update(native_arrays)
    plots(references, native, arrays)
    with (OUT/'summary.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream)
        writer.writerow(['group', 'case', 'method', 'L_shape_rmse_db', 'R_shape_rmse_db', 'folds', 'spectral_bins_per_channel'])
        for group, cases in [('reference', references), ('native', native)]:
            for case, row in cases.items():
                for method, values in row['spectral_shape_rmse_db_lr'].items():
                    writer.writerow([group, case, method, *values, len(row['folds']), row['compared_spectral_bins_per_channel']])
    result = dict(study='spectral_coordinates_log_v1', runtime='0.16.0 unchanged', controls=known,
                  reference_tracks=dict(path=str(TRACKS.relative_to(ROOT)).replace('\\', '/'), sha256=sha(TRACKS)),
                  references=references, native=native, inputs=inputs,
                  source_processing='Unchanged approved float32 stereo; fractional-bandwidth Gaussian smoothing of log PSD in analysis matrices only (geometric power shape, not integrated band power). No new reference audio file, normalization, denoise or channel fold.',
                  initial_linear_power_study=dict(path='references/analysis/spectral_coordinates_v1/results.json',
                      sha256=sha(ROOT/'references/analysis/spectral_coordinates_v1/results.json'),
                      reason_for_replacement='Broad smoothing of linear power leaked strong low-frequency cut/pumping content into nearly silent high-frequency bins. Initial files and exact tools retained; their native wide-smoothing ranking is not used for a physical conclusion.'),
                  method='Regularized linear-hat smooth profiles in log2(Hz), log2(Hz/ridge), or both. Past-only fits with >=192ms centre gap and disjoint 10-frame future blocks. Spectral shape metric removes frame mean on common supported evaluation bins.',
                  limits=['Conditional spectrum-shape prediction only; full offline ridge is assumed known, not predicted.',
                          'No measured RPM/load/pedal/injector data; ridge scaling is arbitrary and proven not to determine an engine order.',
                          'Combined fixed and moving profiles have slope/intercept allocation ambiguity. They are not separated acoustic/excitation sources.',
                          'Reference is a mixed microphone observation; C sources and mixes are different unmatched engineering inputs.',
                          'Magnitude envelopes do not capture phase, cyclic event detail, spatial field or subjective realism.',
                          'Overlapping spectral bins, smoothing/windows/channels and repeated fits are dependent; no confidence interval or statistical significance claimed.'],
                  tool_hashes={f'tools/{name}':sha(ROOT/'tools'/name) for name in ['spectral_coordinates.py', 'analyze_spectral_coordinates.py', 'reference_segments.py']})
    result['files'] = {p.name:sha(p) for p in sorted(OUT.iterdir()) if p.is_file()}
    (OUT/'results.json').write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps({group: {case:row['spectral_shape_rmse_db_lr'] for case,row in cases.items()}
                      for group,cases in [('reference', references), ('native', native)]}, indent=2))


if __name__ == '__main__':
    main()
