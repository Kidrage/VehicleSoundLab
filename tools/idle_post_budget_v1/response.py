"""Time-varying POST kernels; explicit analytic observation-tail bounds."""
import numpy as np
from scipy import signal
from scipy.fft import next_fast_len


def support(sos, tolerance=1e-13):
    sections = []; radius = 0.
    for row in sos:
        discriminant = row[4]**2-4*row[3]*row[5]
        if abs(discriminant) <= 64*np.finfo(float).eps*(row[4]**2+4*abs(row[3]*row[5])):
            raise ValueError('Distinct poles required for this support bound')
        poles = np.roots(row[3:]); r = float(max(abs(poles)))
        if r >= 1 or abs(poles[0]-poles[1]) < 1e-10:
            raise ValueError('Stable distinct poles required for this support bound')
        impulse = signal.lfilter(row[:3], row[3:], [1., 0., 0., 0.])
        residues = np.linalg.solve(np.asarray([[1, 1], poles]), impulse[2:])
        sections.append((r, impulse[:2], float(abs(residues).sum())))
        radius = max(radius, r)
    R = 1/np.sqrt(radius)
    norm = float(np.prod([abs(h[0])+R*abs(h[1])+R*R*c/(1-R*r) for r, h, c in sections]))
    length = max(2, int(np.ceil(np.log(norm/tolerance)/np.log(R))))
    bound = float(norm*R**(-length))
    assert bound <= tolerance
    impulse = np.zeros(length); impulse[0] = 1
    return signal.sosfilt(sos, impulse), dict(length=length, R=float(R), weighted_norm=norm, tail_L1_bound=bound)


def kernels(origins, amplitudes, taps, observers):
    """Return [time,band,innovation-delay]; amplitudes indexed in full history."""
    size = next_fast_len(max(map(len, observers))+len(taps)-1)
    transfer = np.fft.rfft(taps, n=size); rows = []
    for impulse in observers:
        shifts = origins[:, None]-np.arange(len(impulse))
        if shifts.min() < 0: raise ValueError('Insufficient amplitude history')
        weighted = amplitudes[shifts]*impulse
        rows.append(np.fft.irfft(np.fft.rfft(weighted, n=size, axis=1)*transfer, n=size, axis=1))
    return np.stack(rows, axis=1)


def matrices(response):
    covariance = np.einsum('tbk,tck->tbc', response, response)
    squared = response**2
    operator = np.einsum('tbk,tck->tbc', squared, squared)
    return covariance, operator


def operator_error(response, epsilon):
    norm = np.linalg.norm(response, axis=2)
    second = norm[:, :, None]*epsilon[None, None, :]+norm[:, None, :]*epsilon[None, :, None]+np.outer(epsilon, epsilon)
    _, fourth = matrices(response)
    error4 = 2*np.sqrt(fourth)*second+second**2
    return second.max(axis=0), error4.max(axis=0)
