"""Explicit FIRE versus CUT source context for conditional spectrum study."""
import csv
import json
from dataclasses import replace, asdict
from runtime_review import ROOT, sha
from spectral_coordinates import ShapeSettings, smooth_spectra, compare
import numpy as np
import soundfile as sf
from scipy import signal, ndimage
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT = ROOT/'references/analysis/spectral_coordinates_log_v1'


def main():
    if (OUT/'fired_extension.json').exists():
        raise SystemExit('Preserve completed fired extension.')
    primary = json.loads((OUT/'results.json').read_text())
    for name, digest in primary['inputs'].items():
        assert sha(ROOT/name) == digest, name
    with (ROOT/'renders/v0.16.0/neutral_base.csv').open() as stream:
        trace = list(csv.DictReader(stream))
    tt = np.array([float(r['seconds']) for r in trace])
    rpm = np.array([float(r['rpm']) for r in trace])
    all_rows, levels = {}, {}
    groups = {'mix': ['neutral_base.wav'],
              'exhaust': ['neutral_base_source_exhaust_left.wav', 'neutral_base_source_exhaust_right.wav'],
              'air': ['neutral_base_source_air_left.wav', 'neutral_base_source_air_right.wav']}
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), constrained_layout=True)
    for name, paths in groups.items():
        values = []
        for filename in paths:
            value, sr = sf.read(ROOT/'renders/exhaust_phase_v1'/filename, always_2d=True)
            values.append(value)
        audio = np.concatenate(values, axis=1)
        assert audio.shape[1] == 2 and sr == 48000
        levels[name] = {}
        for state, interval in [('FIRE', (3., 4.2)), ('CUT', (6.45, 7.85))]:
            selected = [r for r in trace if interval[0] <= float(r['seconds']) <= interval[1]]
            assert selected and all(r['fuel_mode'] == state and r['lifecycle'] == 'RUNNING' for r in selected)
            x = audio[round(interval[0]*sr):round(interval[1]*sr)]
            hz, psd = signal.welch(x, sr, nperseg=4096, axis=0, scaling='density')
            power = psd[(hz >= 1500) & (hz < 8000)].sum(axis=0)*(hz[1]-hz[0])
            levels[name][state] = dict(seconds=list(interval), trace_fuel_mode=state,
                drive_rpm_endpoints=[float(selected[0]['rpm']), float(selected[-1]['rpm'])],
                raw_1500_8000_power_dbfs_lr=(10*np.log10(np.maximum(power, 1e-30))).tolist(),
                meaning='Integrated raw original-Hz Welch PSD, before any spectral-shape smoothing/mean removal. Source digital level, not physical acoustic loudness.')
        for smoothing in [.125, .25]:
            settings = replace(ShapeSettings(), smoothing_octaves=smoothing)
            hz, at, db = smooth_spectra(audio, sr, settings)
            selected = (at >= 3.) & (at <= 4.2)
            ridge = np.interp(at[selected], tt, rpm)*10/240
            row = compare(hz, at[selected], ridge, db[selected], settings)
            row.update(settings=asdict(settings), trace_fuel_mode='FIRE', seconds=[3., 4.2],
                conditioning='Engineering drive-RPM proxy, not exact 18ms-smoothed audio phase. Unmatched FREE REV input; not a calibrated reference comparison.')
            all_rows[name+f'_smooth{smoothing:g}'] = row
        for c, ax in enumerate(axes):
            row = all_rows[name+'_smooth0.125']
            i = list(groups).index(name)
            for j, method in enumerate(['fixed', 'moving', 'combined']):
                ax.bar(i+(j-1)*.23, row['spectral_shape_rmse_db_lr'][method][c], width=.23,
                       label=method if i == 0 else None)
    for c, ax in enumerate(axes):
        ax.set(xticks=range(3), xticklabels=list(groups), ylabel='Held-out shape RMSE / dB',
               title=f'C FIRE / channel or object {"LR"[c]} / 3.0-4.2s')
        ax.legend();ax.grid(axis='y', alpha=.2)
    fig.suptitle('Conditional geometric PSD shape; unmatched source context, not a realism score')
    fig.savefig(OUT/'fired_shape_prediction.png', dpi=160);plt.close(fig)
    # Isolate the smoothing failure with a known PSD array: a moving low-Hz
    # component can enter a broad finite Gaussian tail and raise quiet bins.
    x = np.arange(240)
    spectrum = np.full((2, len(x)), 1e-16)
    spectrum[0, 45] = .01
    spectrum[1, 55] = .01
    linear = 10*np.log10(ndimage.gaussian_filter1d(spectrum, 12, axis=-1, mode='reflect'))
    logarithmic = ndimage.gaussian_filter1d(10*np.log10(spectrum), 12, axis=-1, mode='reflect')
    at = 100
    linear_change = abs(float(linear[1, at]-linear[0, at]))
    log_change = abs(float(logarithmic[1, at]-logarithmic[0, at]))
    assert linear_change > 40 and log_change < .1, (linear_change, log_change)
    result = dict(result='pass', primary_results_sha256=sha(OUT/'results.json'),
                  fired_shape=all_rows, raw_source_levels=levels,
                  known_low_tone_smoothing_control=dict(linear_power_change_db=linear_change,
                      log_power_change_db=log_change, target_psd_unchanged=True,
                      meaning='The underlying quiet-bin PSD is fixed. Movement of a 140dB stronger distant bin changes linear-power smoothing through its finite tail. Log-power smoothing measures a different statistic and avoids this particular domination, not all leakage or tracking error.'),
                  decisions=['CUT exhaust is about -168dBFS in the evaluation band; its shape ranking cannot stand in for fired combustion or explain the audible full mix.',
                             'FIRE and CUT are explicitly separated. Neither input is RPM/load/microphone matched to A.',
                             'The combined model is retained even when worse on held-out data; no training fit or extra parameter count is treated as better physical identification.'],
                  source_sha256=sha(__file__), figure_sha256=sha(OUT/'fired_shape_prediction.png'))
    (OUT/'fired_extension.json').write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps(dict(levels=levels, fired_scores={k:v['spectral_shape_rmse_db_lr'] for k,v in all_rows.items()},
                          smoothing_control=result['known_low_tone_smoothing_control']), indent=2))


if __name__ == '__main__':
    main()
