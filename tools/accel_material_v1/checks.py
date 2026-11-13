"""Known signals test what a spectral scale can and cannot identify."""
import numpy as np
from .features import whiten, scale_match, shifted_power
from idle_material_v1.features import spectrum


def controls(plan):
    n = 12000
    rate = 48000
    time = np.arange(n) / rate
    orders = np.arange(3, 61)
    frequencies = orders * 83.137
    amplitudes = .05 * orders ** -.7
    phase = orders * .173

    def wave(ratio, colour=0.):
        amp = amplitudes * (frequencies / 1500.) ** colour
        left = np.sum(amp[:, None] * np.cos(2 * np.pi * frequencies[:, None] * ratio *
                                          time[None, :] + phase[:, None]), axis=0)
        return np.column_stack((left, left * .67))

    settings, bands = plan['spectral_scale'], plan['bands_hz']
    first = spectrum(wave(1.), bands)
    feature = whiten(first['cells'], first['frequency'], settings)
    rows = []
    for shift in [-32, 0, 32, 64]:
        ratio = 2. ** (shift / settings['bins_per_octave'])
        measured = spectrum(wave(ratio), bands)
        result = scale_match(feature, whiten(measured['cells'], measured['frequency'], settings), settings)
        assert abs(result['shift_bins'] - shift) <= 1, (shift, result)
        assert result['supported'], (shift, result)
        rows.append(dict(expected_shift=shift, measured_shift=result['shift_bins'],
                         score=result['score'], margin=result['peak_margin']))
    altered = spectrum(wave(1., .4), bands)
    colour = scale_match(feature, whiten(altered['cells'], altered['frequency'], settings), settings)
    assert abs(colour['shift_bins']) <= 1
    low_gain = spectrum(.21 * wave(1.), bands)
    gain_error = float(np.max(abs(feature - whiten(low_gain['cells'], low_gain['frequency'], settings))))
    assert gain_error < 1e-8
    silent = spectrum(np.zeros((n, 2)), bands)
    silence = scale_match(feature, whiten(silent['cells'], silent['frequency'], settings), settings)
    assert not silence['supported']
    # Exact power-cell geometry with fractional band boundaries.
    f = np.arange(11, dtype=float) * 4
    cells = np.zeros((11, 2)); cells[5] = [2., 3.]
    power = shifted_power(cells, f, 1.25, [[23.75, 26.25], [0, 100]])
    assert np.max(abs(power - np.array([[1., 1.5], [2., 3.]]))) < 1e-14
    return dict(passed=True, known_scales=rows, colour_only_shift=colour['shift_bins'],
                global_gain_feature_error=gain_error, silence_rejected=True,
                fractional_cell_power_error=float(np.max(abs(power - [[1., 1.5], [2., 3.]]))))
