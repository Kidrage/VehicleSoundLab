"""Observed closure coordinates and finite linear-overlap statistics, without a source model."""
import numpy as np
from scipy import signal
from idle_conditioned_detail_v1.features import phases

LAGS = np.arange(0, 24001, 48)
FREQUENCIES = np.array([75.03679765988039, 112.48553445984204, 187.52858173958495])
ORIGINS = np.array([-1.0999136177479023, 2.28663683508382, -1.2162815568787233])


def closure(z): return z[:, 2]*z[:, 1].conj()*z[:, 0].conj()


def linear_curves(angle, residual):
    n = len(angle); count = n-LAGS; size = 1 << (2*n-1).bit_length()
    def autocorrelation(x):
        X = np.fft.rfft(x, n=size); return np.fft.irfft(abs(X)**2, n=size)[LAGS]
    covariance = autocorrelation(residual)/count
    prefix = np.r_[0., np.cumsum(angle**2)]
    increments = (prefix[n]-prefix[LAGS]+prefix[n-LAGS]-2*autocorrelation(angle))/count
    variance = float(np.mean(residual**2))
    return dict(residual_covariance=covariance, residual_correlation=covariance/variance if variance > 0 else np.full(len(LAGS), np.nan),
                phase_increment_second=increments)


def observe(z):
    w = closure(z); mean = w.mean(); center = float(np.angle(mean))
    principal = np.angle(w*np.exp(-1j*center)); steps = np.angle(w[1:]*w[:-1].conj())
    angle = np.r_[np.angle(w[0]), np.angle(w[0])+np.cumsum(steps)]
    t = (np.arange(len(w))-(len(w)-1)/2)/48000
    slope = float(t@(angle-angle.mean())/(t@t)); residual = angle-angle.mean()-slope*t
    curves = linear_curves(angle, residual)
    chart = bool(abs(principal).max() < np.pi-.05)
    stats = dict(frames=len(w), circular_center_rad=center, resultant=float(abs(mean)),
        circular_mean_real_imag=[float(mean.real), float(mean.imag)],
        principal_quantiles=np.quantile(principal, [0., .01, .05, .5, .95, .99, 1.]).tolist(),
        observed_step_absmax_rad=float(abs(steps).max()), descriptive_linear_slope_hz=slope/(2*np.pi),
        detrended_std_rad=float(np.sqrt(np.mean(residual**2))),
        empirical_chart_valid=chart, empirical_arc_rad=[float(principal.min()), float(principal.max())])
    return stats, dict(closure=w, unwrapped=angle, residual=residual, lags_frames=LAGS, **curves)


def arc_membership(w, train):
    if not train['empirical_chart_valid']: return None
    deviation = np.angle(w*np.exp(-1j*train['circular_center_rad']))
    lo, hi = train['empirical_arc_rad']
    inside = (deviation >= lo) & (deviation <= hi)
    return inside


def known():
    n = 144000; t = np.arange(n)/48000; delta = FREQUENCIES[2]-FREQUENCIES[1]-FREQUENCIES[0]
    phi = ORIGINS[2]-ORIGINS[1]-ORIGINS[0]
    # Exactly independent deterministic oscillators. No feedback/coupling exists.
    centers = (np.arange(180000)+.5)/1000
    wlong = np.exp(1j*(phi+2*np.pi*delta*centers))
    short_resultant = float(abs(np.sinc(delta*2.5)/np.sinc(delta/48000)))
    long_resultant = float(abs(np.sinc(delta*180)/np.sinc(delta/1000)))
    assert short_resultant > .999 and long_resultant < .11
    assert abs(abs(wlong.mean())-long_resultant) < 1e-12
    tests = []
    for kind in ['independent_detuned', 'bounded_third_FM', 'independent_AM']:
        for portion in range(2):
            tt = t+portion*3; theta = 2*np.pi*tt[:, None]*FREQUENCIES+ORIGINS
            if kind == 'bounded_third_FM': theta[:, 2] += .18*np.sin(2*np.pi*2.3*tt)
            amplitudes = np.tile([.07959081914372979, .0751960872053696, .03924681140931266], (n, 1))
            if kind == 'independent_AM': amplitudes *= 1+.25*np.cos(2*np.pi*tt[:, None]*[1.3, 1.7, 2.1]+[.2, -.4, .7])
            audio = (np.cos(theta)*amplitudes).sum(axis=1)
            measured = phases(audio, FREQUENCIES)[12000:-12000]
            truth = np.exp(1j*theta[12000:-12000]); measured_w, truth_w = closure(measured), closure(truth)
            error = float(np.quantile(abs(np.angle(measured_w*truth_w.conj())), .95))
            assert error < .105, (kind, portion, error)
            stats, arrays = observe(measured)
            tests.append(dict(kind=kind, portion=portion, p95_observer_closure_error_rad=error, **stats))
    # All501linear-overlap values on a smaller analytic residual, including zero.
    tt = np.arange(30000)/48000
    angle = .31+2*np.pi*.013*tt+.17*np.sin(2*np.pi*3.1*tt)+.07*np.cos(2*np.pi*7.3*tt)
    tc = tt-tt.mean(); slope = tc@(angle-angle.mean())/(tc@tc); residual = angle-angle.mean()-slope*tc
    values = linear_curves(angle, residual)
    expected_cov = np.array([np.mean(residual[:len(angle)-lag]*residual[lag:]) for lag in LAGS])
    expected_inc = np.array([np.mean((angle[lag:]-angle[:len(angle)-lag])**2) for lag in LAGS])
    cov_error = float(abs(expected_cov-values['residual_covariance']).max())
    inc_error = float(abs(expected_inc-values['phase_increment_second']).max())
    assert cov_error < 1e-12 and inc_error < 1e-12
    z = np.exp(1j*(2*np.pi*tt[:, None]*FREQUENCIES+ORIGINS)); stats, arrays = observe(z)
    assert abs(stats['descriptive_linear_slope_hz']-delta) < 1e-10
    changed = z*np.exp(1j*np.array([.1, -.3, .7])); other, y = observe(changed)
    assert abs(stats['resultant']-other['resultant']) < 1e-12
    assert np.array_equal(arc_membership(closure(z), stats), arc_membership(closure(changed), other))
    return dict(independent_short_resultant=short_resultant, independent180s_resultant=long_resultant,
                original_observer=tests, all501_covariance_error=cov_error, all501_increment_error=inc_error,
                analytic_slope_and_origin=True)
