"""Conditional cycle-envelope checks; no source separation or RPM inference.

The observable is short-band analytic power, normalized within each complete
supplied phase cycle. A past template predicts envelope shape, not waveform,
loudness or future frequency. A cycle-wise phase shift is a designed contrast,
not a physical null distribution or an uncertainty interval.
"""
from dataclasses import dataclass, asdict
from cycle_prediction import phase_grid, CycleSettings
import numpy as np
from scipy import signal, ndimage


@dataclass(frozen=True)
class EnvelopeSettings:
    filter_taps: int = 513
    train_cycles: int = 8
    test_cycles: int = 4
    purge_seconds: float = .200
    trend_sigma_seconds: float = .020
    trend_truncate: float = 4.
    surrogate_count: int = 64
    seed: int = 48271
    minimum_raw_mean_power: float = 1e-16
    minimum_shape_variance: float = 1e-10


def analytic_filter(rate, band, settings=EnvelopeSettings()):
    lo, hi = band
    if not 0 < lo < hi < rate/2 or settings.filter_taps < 33 or settings.filter_taps%2 != 1:
        raise ValueError('Valid band and odd finite FIR support required')
    offset = np.arange(settings.filter_taps)-(settings.filter_taps-1)/2
    lowpass = signal.firwin(settings.filter_taps, (hi-lo)/2, fs=rate, window='hann')
    return 2*lowpass*np.exp(2j*np.pi*(lo+hi)/2*offset/rate)


def band_analytic(audio, rate, band, settings=EnvelopeSettings()):
    x = np.asarray(audio)
    if x.ndim != 2 or x.shape[1] != 2 or not np.isfinite(x).all():
        raise ValueError('Finite two-channel analysis array required')
    h = analytic_filter(rate, band, settings)
    # Centred finite support is explicit, unlike an infinite Hilbert transform.
    # Preserve the full input context before selecting any phase-grid interval.
    return signal.fftconvolve(x, h[:, None], mode='same', axes=0)


def remove_slow_log_trend(z, rate, settings=EnvelopeSettings()):
    """Condition out smooth multiplicative level, with explicit finite support.

    Per-cycle means alone turn even an exponential fade into a repeatable
    intra-cycle ramp. This analysis-only raw-time log-power trend prevents
    that ramp from being mistaken for phase-linked energy pulses.
    """
    if settings.trend_sigma_seconds <= 0 or settings.trend_truncate <= 0:
        raise ValueError('Positive finite log-power trend support required')
    log_power = np.log(np.maximum(abs(z)**2,1e-30))
    trend = ndimage.gaussian_filter1d(log_power, settings.trend_sigma_seconds*rate,
        axis=0, truncate=settings.trend_truncate, mode='reflect')
    return z*np.exp(-.5*trend)


def power_grid(z, rate, times, frequency, divisor=1, origin=0, settings=EnvelopeSettings()):
    grid_settings = CycleSettings(train_cycles=settings.train_cycles,
        test_cycles=settings.test_cycles)
    real, meta, inverse = phase_grid(z.real, rate, times, frequency, divisor, origin, grid_settings)
    imag, imag_meta, imag_inverse = phase_grid(z.imag, rate, times, frequency, divisor, origin, grid_settings)
    assert meta == imag_meta and np.array_equal(inverse, imag_inverse)
    power = real*real+imag*imag
    meta.update(analysis='Squared magnitude of separately interpolated real/imaginary finite analytic band',
        centered_filter_half_support_seconds=(settings.filter_taps-1)/(2*rate),
        centered_log_trend_half_support_seconds=round(settings.trend_sigma_seconds*rate*settings.trend_truncate)/rate,
        normalization='Per-cycle, per-channel equal-phase mean; no raw reference samples modified')
    return power, meta, inverse


def folds(inverse, settings=EnvelopeSettings()):
    n = len(inverse)
    start = settings.train_cycles
    while start+settings.test_cycles <= n:
        past = np.flatnonzero(inverse[:start, -1] <= inverse[start, 0]-settings.purge_seconds)
        if len(past) < settings.train_cycles:
            start += 1
            continue
        train = past[-settings.train_cycles:]
        test = np.arange(start, start+settings.test_cycles)
        yield train, test
        start += settings.test_cycles


def score(power, inverse, harmonics=8, settings=EnvelopeSettings()):
    p = np.asarray(power)
    if p.ndim != 3 or p.shape[-1] != 2 or p.shape[:2] != inverse.shape or not np.isfinite(p).all() or np.min(p) < 0:
        raise ValueError('Nonnegative complete two-channel power cycles required')
    if not 0 < harmonics < p.shape[1]/2:
        raise ValueError('Harmonic projection must exclude Nyquist')
    if settings.purge_seconds <= 0 or settings.surrogate_count < 8:
        raise ValueError('Positive purge and at least eight phase contrasts required')
    means = p.mean(axis=1, keepdims=True)
    if np.min(means) <= np.finfo(float).tiny:
        return dict(status='unmeasured', reason='Cycle envelope has zero numerical power')
    shape = p/means-1
    variance = np.mean(shape*shape, axis=(0,1))
    if np.min(variance) < settings.minimum_shape_variance:
        return dict(status='unmeasured', reason='Envelope shape is essentially constant', normalized_shape_variance_lr=variance.tolist())
    coefficients = np.fft.rfft(shape, axis=1, norm='forward')[:,1:harmonics+1,:]
    rng = np.random.default_rng(settings.seed)
    actual = np.zeros(2);errors = np.zeros(2);projection_floor = np.zeros(2)
    contrasts = np.zeros((settings.surrogate_count, 2))
    ledger = []
    k = np.arange(1,harmonics+1)
    for train,test in folds(inverse, settings):
        template = coefficients[train].mean(axis=0)
        signal_power = np.mean(shape[test]**2, axis=1).sum(axis=0)
        template_power = 2*np.sum(abs(template)**2, axis=0)*len(test)
        cross = coefficients[test]*template.conj()[None,:,:]
        error = signal_power+template_power-4*cross.real.sum(axis=(0,1))
        projection_floor += np.maximum(0,signal_power-2*np.sum(abs(coefficients[test])**2,axis=(0,1)))
        # One fractional circular phase shift per held-out cycle, shared by
        # both channels, preserves cycle energy and interchannel relationship.
        offsets = rng.uniform(0,1,(settings.surrogate_count,len(test)))
        rotation = np.exp(-2j*np.pi*offsets[:,:,None]*k[None,None,:])
        contrast = signal_power+template_power-4*np.einsum('stp,tpc->sc',rotation,cross).real
        actual += signal_power;errors += error;contrasts += contrast
        ledger.append(dict(train_cycles=[int(train[0]),int(train[-1]+1)],
            test_cycles=[int(test[0]),int(test[-1]+1)],
            train_last_seconds=float(inverse[train[-1],-1]),test_first_seconds=float(inverse[test[0],0]),
            centre_gap_seconds=float(inverse[test[0],0]-inverse[train[-1],-1])))
    if not ledger:
        return dict(status='unmeasured', reason='Insufficient complete cycles for past template, purge and held-out block')
    ratio = np.maximum(errors/actual,1e-20)
    db = 10*np.log10(ratio)
    contrast_db = 10*np.log10(np.maximum(contrasts/actual,1e-20))
    quantiles = np.percentile(contrast_db,[5,50,95],axis=0)
    return dict(status='measured',harmonics=harmonics,settings=asdict(settings),
        future_envelope_error_db_lr=db.tolist(),phase_shift_error_db_p05_median_p95_lr=quantiles.tolist(),
        per_test_cycle_harmonic_projection_floor_db_lr=(10*np.log10(np.maximum(projection_floor/actual,1e-20))).tolist(),
        phase_contrast_db_lr=(quantiles[1]-db).tolist(),
        normalized_shape_variance_lr=variance.tolist(),cycle_mean_power_range_lr=[means.min(axis=(0,1)).tolist(),means.max(axis=(0,1)).tolist()],
        held_out_cycles=len(ledger)*settings.test_cycles,folds=ledger,
        meaning='Past-cycle low-harmonic envelope template error versus observed future envelope shape. 0 dB equals zero-shape prediction. Projection floor uses each test cycle independently for a diagnostic representational lower bound, not as the past prediction. Phase contrast is designed cycle-phase destruction, not stochastic source fraction, confidence or realism.')
