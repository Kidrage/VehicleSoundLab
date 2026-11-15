"""Independent offset accumulation and analytic tones; no producer imports."""
import numpy as np
from scipy.special import i0


def sinc_sum(samples, query, radius):
    samples, query = np.asarray(samples), np.asarray(query)
    assert samples.ndim == 2 and query.ndim == 1
    center = np.floor(query).astype(np.int64)
    assert center.min()+1-radius >= 0 and center.max()+radius < len(samples)
    numerator = np.zeros((len(query), samples.shape[1]))
    denominator = np.zeros(len(query))
    for offset in range(1-radius, radius+1):
        ids = center+offset
        d = query-ids
        sinc = np.ones(len(query))
        nz = d != 0
        sinc[nz] = np.sin(np.pi*d[nz])/(np.pi*d[nz])
        w = sinc*i0(20*np.sqrt(np.maximum(0., 1-(d/radius)**2)))/i0(20.)
        denominator += w
        for c in range(samples.shape[1]):
            numerator[:, c] += w*samples[ids, c]
    return numerator/denominator[:, None]


def analytic(seconds, frequencies, coefficients, taps=None):
    pi = np.arccos(np.longdouble(-1))
    seconds = np.asarray(seconds, np.longdouble)
    out = np.zeros((len(seconds), 2), np.longdouble)
    for k, frequency in enumerate(frequencies):
        f = np.longdouble(frequency)
        gain = np.longdouble(1)
        if taps is not None:
            offsets = np.arange(len(taps), dtype=np.longdouble)-(len(taps)-1)/2
            gain = np.sum(np.asarray(taps, np.longdouble)*np.cos(2*pi*f*offsets/48000))
        phase = np.remainder(seconds*f, 1)*2*pi
        for c in (0, 1):
            out[:, c] += gain*(np.longdouble(coefficients[k, c].real)*np.cos(phase)
                -np.longdouble(coefficients[k, c].imag)*np.sin(phase))
    return np.asarray(out, float)
