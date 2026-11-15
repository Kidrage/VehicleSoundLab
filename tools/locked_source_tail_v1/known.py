"""Analytic stereo FIR response and same registered real clock controls."""
import numpy as np
from scipy import signal
from source_resampling_v1.query import interpolate
from .kernel import reference


def evaluate(relative_seconds, frequencies, coefficients, taps=None):
    pi = np.arccos(np.longdouble(-1))
    f = np.asarray(frequencies, np.longdouble)
    gain = np.ones(len(f), np.longdouble)
    if taps is not None:
        offsets = np.arange(len(taps), dtype=np.longdouble)-(len(taps)-1)/2
        gain = np.cos(2*pi*f[:, None]*offsets[None]/48000)@np.asarray(taps, np.longdouble)
    phase = np.remainder(np.asarray(relative_seconds, np.longdouble)[:, None]*f[None], 1.)
    phase *= 2*pi
    real = np.asarray(coefficients.real, np.longdouble)*gain[:, None]
    imag = np.asarray(coefficients.imag, np.longdouble)*gain[:, None]
    return np.asarray(np.cos(phase)@real-np.sin(phase)@imag, float)


def qualify(query, coordinates, source_start, crop, taps, source_frames):
    frequencies = np.array([0., 100., 1000., 5000., 9000., 13000., 13950., 14000.])
    coefficients = np.array([[.02, -.01], [.13, .09], [.03, -.05j], [.02j, .04],
                             [.01, .015j], [.008j, -.004], [.004, .006j], [.003j, .002]], complex)
    grid = np.arange(source_frames, dtype=np.longdouble)/48000
    native = evaluate(grid, frequencies, coefficients)
    filtered = signal.fftconvolve(native[int(crop[0]):int(crop[1])], taps[:, None], mode='same', axes=0)
    sample_time = np.arange(int(crop[0]), int(crop[1]), dtype=np.longdouble)/48000
    ideal_filtered = evaluate(sample_time, frequencies, coefficients, taps)
    registered = np.asarray(coordinates, np.longdouble)-np.longdouble(source_start)
    query_time = (np.longdouble(crop[0])+np.asarray(query, np.longdouble))/48000
    affine = np.linspace(registered[0], registered[-1], len(registered), dtype=np.longdouble)
    values = dict(exact_registered=evaluate(registered, frequencies, coefficients, taps),
        exact_query=evaluate(query_time, frequencies, coefficients, taps),
        exact_affine=evaluate(affine, frequencies, coefficients, taps),
        nominal128=interpolate(filtered, query, 128),
        ideal_native_nominal128=interpolate(ideal_filtered, query, 128))
    scale = float(np.sum(abs(coefficients)))
    errors = {}
    for radius in (512, 1024, 2048):
        name = 'reference'+str(radius)
        values[name] = reference(filtered, query, radius)
        error = float(np.max(abs(values[name]-values['exact_registered']))/scale)
        assert error < 2e-10, (name, error, 2e-10)
        errors[name] = error
    nominal = float(np.max(abs(values['nominal128']-values['exact_registered']))/scale)
    assert nominal < 2e-6
    probes = query[np.linspace(0, len(query)-1, 11, dtype=int)]
    checks = np.column_stack((filtered[:, 0], filtered[:, 0], np.zeros_like(filtered), filtered*1e-6))
    out = reference(checks, probes, 2048)
    assert np.array_equal(out[:, 0], out[:, 1]) and not np.count_nonzero(out[:, 2:4])
    assert np.max(abs(out[:, 4]-out[:, 0]*1e-6))/scale < 2e-12
    rejected = []
    for name, data, q, radius in (
        ('left_support', filtered, np.array([1.]), 512),
        ('right_support', filtered, np.array([len(filtered)-2.]), 512),
        ('nonfinite', filtered*np.nan, probes, 512),
        ('complex', filtered.astype(complex), probes, 512),
        ('radius', filtered, probes, 256)):
        try:
            reference(data, q, radius)
        except ValueError:
            rejected.append(name)
        else:
            raise AssertionError('Invalid reference accepted: '+name)
    arrays = dict(native=native, filtered=filtered, ideal_filtered=ideal_filtered, frequencies=frequencies,
                  coefficients=coefficients, query=query, coordinates=coordinates, crop=crop, taps=taps,
                  probe_source=checks, probe_query=probes, probe_output=out)
    return values, arrays, dict(all_qualified=True, source_L1=scale, reference_errors=errors,
        reference_analytic_gate_relative_source_L1=2e-10, nominal_error=nominal, nominal_gate=2e-6,
        mono_zero_weak_probe_checks_passed=True, invalid_rejections=rejected,
        exact_affine_is_counterfactual_not_replacement_clock=True)
