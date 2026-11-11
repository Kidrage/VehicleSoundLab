"""Check paired raw band powers independently and retain a sweep counterexample."""
import json
from runtime_review import ROOT, sha
from reference_segments import read_segment
from matched_shapes import window_band_powers
import numpy as np
from scipy import signal

OUT = ROOT/'references/analysis/repeat_shape_v1'
BANDS = [(28, 400), (400, 1200), (1200, 3000), (3000, 8000), (8000, 16000)]


def independent_powers(x, rate, at, window):
    n = round(window*rate)
    first = round(at*rate)-n//2
    hz, p = signal.periodogram(x[first:first+n], fs=rate, window='hann',
        detrend=False, scaling='density', axis=0)
    return np.array([p[(hz >= lo) & (hz < hi)].sum(axis=0)*rate/n for lo, hi in BANDS])


def main():
    if (OUT/'verification.json').exists():
        raise SystemExit('Preserve completed repeat-shape verification.')
    result = json.loads((OUT/'results.json').read_text(encoding='utf-8'))
    for name, digest in result['files'].items():
        assert sha(OUT/name) == digest, name
    for name, digest in result['tools'].items():
        assert sha(ROOT/name) == digest, name
    for name, digest in result['native_preserved'].items():
        assert sha(ROOT/name) == digest, name
    x, rate, provenance = read_segment('A_exterior_blips', 'exterior_dynamic_observation')
    assert provenance == result['reference']
    error, relative_error = 0., 0.
    for run in result['runs'].values():
        if run['status'] != 'measured':
            continue
        a, b = [np.array([independent_powers(x, rate, at-238, run['settings']['window_seconds'])
                          for at in times]) for times in run['paired_source_seconds']]
        ratio = 10*np.log10(b/a)
        error = max(error, float(abs(ratio-np.array(run['band_power_ratio_second_over_first_db'])).max()))
    assert error < 1e-10
    # Known OSC source evaluated via complex exponentials; two exact analytic
    # paths have the same instantaneous amplitude law at the paired coordinate.
    t = np.arange(round(1.7*rate))/rate
    paths = [(330, 1.10, 0.), (290, 1.45, .47)]
    targets = np.array([180., 200., 220., 240., 260.])
    samples, query = [], []
    coordinate_error = 0.
    for initial, half, offset in paths:
        alpha = np.log(2)/half
        root = initial/5*np.exp(-alpha*t)
        phase = 2*np.pi*initial/5/alpha*(1-np.exp(-alpha*t))
        audio = np.zeros((len(t), 2))
        for order in range(1, 257):
            hz = order*root
            amplitude = .018/order**.6*np.exp(-hz/6500)*(.1
                +np.exp(-.5*(np.log2(hz/1800)/.3)**2)
                +.6*np.exp(-.5*(np.log2(hz/4500)/.35)**2))
            audio += amplitude[:, None]*np.real(np.exp(1j*(order*phase[:, None]
                +.3*order+np.array([0., .23])[None, :]+offset)))
        samples.append(audio)
        times = np.log(initial/targets)/alpha
        query.append(times)
        coordinate_error = max(coordinate_error, float(abs(initial*np.exp(-alpha*times)-targets).max()))
    controls = {}
    for window in [.04, .08, .128]:
        groups = []
        for audio, times in zip(samples, query):
            powers = []
            for at in times:
                primary, _ = window_band_powers(audio, rate, at, window, BANDS)
                oracle = independent_powers(audio, rate, at, window)
                relative_error = max(relative_error, float(np.max(abs(primary-oracle)/np.maximum(oracle, 1e-25))))
                powers.append(oracle)
            groups.append(powers)
        ratio = 10*np.log10(np.array(groups[1])/np.array(groups[0]))
        controls[str(window)] = dict(band_power_ratio_db=ratio.tolist(),
            high_band_3_8k_max_abs_db=float(abs(ratio[:, 3]).max()))
    assert relative_error < 1e-10 and coordinate_error < 1e-10
    ranges = {}
    for i, target in enumerate(targets):
        ratios = np.array([r['band_power_ratio_second_over_first_db'][i][3]
            for r in result['runs'].values() if r['status'] == 'measured'])
        ranges[str(target)] = dict(min_db_lr=ratios.min(axis=0).tolist(), max_db_lr=ratios.max(axis=0).tolist())
    check = dict(result='pass', study='repeat_shape_v1',
        raw_reference_band_ratios_vs_Scipy_periodogram_max_db_error=error,
        known_OSC_band_power_vs_periodogram_max_relative_error=relative_error,
        known_OSC_pair_coordinate_max_error_hz=coordinate_error,
        known_OSC_same_recipe_raw_band_controls=controls,
        reference_3_8k_sensitivity_ranges=ranges,
        interpretation='Matched-ridge high-band level contrast is repeatable within tested settings. Mean-removed log-shape contrasts cannot uniquely establish a changed transfer: an unchanged OSC recipe also produces comparable contrasts with these windows. Neither identifies load, physical orders, sources or realism.',
        results_sha256=sha(OUT/'results.json'),
        tools={name:sha(ROOT/name) for name in ['tools/verify_repeat_shape.py', 'tools/matched_shapes.py']})
    (OUT/'verification.json').write_text(json.dumps(check, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps(dict(result='pass', raw_band_ratio_max_db_error=error,
        known_OSC_high_band_max_db={k:v['high_band_3_8k_max_abs_db'] for k, v in controls.items()}), indent=2))


if __name__ == '__main__':
    main()
