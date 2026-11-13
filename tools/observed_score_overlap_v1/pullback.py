"""Source-domain adjoints, keeping contributions from each existing window."""
import numpy as np


def windows(operator, values):
    """Yield real sample pullbacks for stacked real/imaginary observation columns."""
    count = len(operator.starts)*len(operator.bins)
    if values.ndim != 2 or values.shape[0] != 2*count:
        raise ValueError('Expected stacked real/imaginary matrix')
    columns = values.shape[1]
    complex_values = (values[:count]+1j*values[count:]).reshape(
        len(operator.starts), len(operator.bins), columns)
    for row, start in enumerate(operator.starts):
        local = complex_values[row]*operator.rotations[row].conj()[:, None]
        if hasattr(operator, 'symmetric'):
            local = operator.symmetric.T@local
        spectrum = np.zeros((operator.size//2+1, columns), dtype=complex)
        spectrum[operator.bins] = local
        samples = np.fft.irfft(spectrum, n=operator.size, axis=0)
        samples *= (operator.size/operator.window.sum())*operator.window[:, None]
        yield int(start), samples


def accumulate(operator, values, frames):
    total = np.zeros((frames, values.shape[1]))
    independent = np.zeros((values.shape[1], values.shape[1]))
    for start, sample in windows(operator, values):
        total[start:start+operator.size] += sample
        independent += sample.T@sample
    return total, total.T@total, independent
