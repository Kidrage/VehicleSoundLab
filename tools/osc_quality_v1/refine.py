"""Short-time joint complex fit at unchanged long-window frequencies.

Offline parameter estimation only. A weak ridge toward the original spectral
coefficients stabilizes unresolved neighbours; no waveform enters runtime.
"""
import numpy as np


def transform(omega, size):
    """Exact centred DTFT of symmetric Hann; valid here away from +/-2pi."""
    def dirichlet(w):
        return size*np.sinc(size*w/(2*np.pi))/np.sinc(w/(2*np.pi))
    k = 2*np.pi/(size-1)
    return np.exp(-.5j*omega)*(.5*dirichlet(omega)+.25*dirichlet(omega+k)+.25*dirichlet(omega-k))


def refine(audio, rate, observations, window=1024, ridge_ratio=.005, limit=64):
    result = []
    half = window//2
    t = (np.arange(window)-half)/rate
    weights = np.hanning(window)
    control_error = 0
    changes = []
    for index, (center, detected) in enumerate(observations):
        row = detected[:limit].copy()
        if not len(row):
            result.append((center, row))
            continue
        omega = row[:, 0]*2*np.pi/rate
        difference = transform(omega[:, None]-omega[None, :], window)
        summation = transform(omega[:, None]+omega[None, :], window)
        cc = .5*(difference+summation).real
        ss = .5*(difference-summation).real
        cs = .5*(summation-difference).imag
        gram = np.block([[cc, cs], [cs.T, ss]])
        basis = np.exp(2j*np.pi*row[:, 0, None]*t[None, :])
        q = basis @ (weights*audio[center-half:center+half])
        rhs = np.concatenate([q.real, q.imag])
        prior = np.concatenate([row[:, 1]*np.cos(row[:, 2]), -row[:, 1]*np.sin(row[:, 2])])
        if index == 0:
            direct = np.column_stack([basis.real.T, basis.imag.T])
            exact = direct.T @ (weights[:, None]*direct)
            control_error = float(abs(gram-exact).max())
            assert control_error < 1e-8, control_error
        ridge = np.trace(gram)/len(gram)*ridge_ratio
        coefficients = np.linalg.solve(gram+np.eye(len(gram))*ridge, rhs+ridge*prior)
        size = len(row)
        amplitude = abs(coefficients[:size]-1j*coefficients[size:])
        phase = np.angle(coefficients[:size]-1j*coefficients[size:])
        changes.extend((amplitude/np.maximum(row[:, 1], 1e-12)).tolist())
        row[:, 1], row[:, 2] = amplitude, phase
        result.append((center, row))
    return result, dict(long_frequencies_unchanged=True, window=window, ridge_ratio=ridge_ratio,
        gram_vs_direct_control_max_error=control_error,
        amplitude_ratio_to_old_p50_p90_p99=np.percentile(changes, [50, 90, 99]).tolist(),
        scope='Offline short-time joint AM/phase coefficient fit at the identical64 long-window frequency candidates; no new high layer, EQ, normalization or noise injection.')
