"""Separate RNG, scalar feature law, FFT synthesis and general15-partition oracle."""
import math
import numpy as np
from scipy.signal import fftconvolve

PAIRS = [(b, c) for b in range(4) for c in range(b, 4)]


class Random:
    def __init__(self, seed): self.state = seed or 1; self.spare = None
    def uniform(self):
        self.state ^= self.state >> 12
        self.state ^= (self.state << 25) & ((1 << 64)-1)
        self.state ^= self.state >> 27
        self.state &= (1 << 64)-1
        bits = ((self.state*2685821657736338717) & ((1 << 64)-1)) >> 11
        return (bits+.5)/9007199254740992.
    def normal(self):
        if self.spare is not None:
            z = self.spare; self.spare = None; return z
        radius = math.sqrt(-2*math.log(self.uniform())); angle = math.tau*self.uniform()
        self.spare = radius*math.sin(angle)
        return radius*math.cos(angle)


def native_power(profile, law, frames):
    t = np.arange(frames)/48000; phases = []
    for index in [1, 2, 4]:
        phases.append(math.tau*profile['modal']['frequencies_hz'][index]*t+
                      profile['modal']['initial_phase_LR'][index][0])
    phases += [phases[j]-phases[i] for i, j in [(0, 1), (0, 2), (1, 2)]]
    beta = np.asarray(law['coefficients']); exponent = np.tile(beta[0], (frames, 1))
    for k, theta in enumerate(phases):
        exponent += np.cos(theta)[:, None]*beta[1+k]
        exponent += np.sin(theta)[:, None]*beta[7+k]
    return np.exp(exponent)


def modal(profile, frames):
    y = np.zeros((frames, 2)); t = np.arange(frames)/48000
    for f, amp, phase in zip(*[profile['modal'][key] for key in
                              ['frequencies_hz', 'amplitude_LR', 'initial_phase_LR']]):
        for c in range(2): y[:, c] += amp[c]*np.cos(math.tau*f*t+phase[c])
    return y


def texture(profile, old_p, new_p, q, seed, frames):
    count = frames+profile['warmup_frames']; outputs = {name: np.zeros((frames, 2)) for name in ['static', 'sparse', 'post']}
    nfft = 1 << (count+max(len(k['taps']) for k in profile['kernels'])-2).bit_length()
    for index, kernel in enumerate(profile['kernels']):
        key = seed ^ ((0x9E3779B97F4A7C15*(index+1)) & ((1 << 64)-1))
        rng, marks, amp = Random(key), Random(key ^ 0xD1B54A32D192ED03), Random(key ^ 0x94D049BB133111EB)
        gaussian = np.array([rng.normal() for _ in range(count)])
        noises = dict(static=gaussian)
        if index < 2: noises.update(sparse=gaussian, post=gaussian)
        else:
            uniform = np.empty(count); normal = np.empty(count)
            for j in range(count): uniform[j] = marks.uniform(); normal[j] = amp.normal()
            for name, ps in [('sparse', old_p), ('post', new_p)]:
                p = ps[index-2]; noise = normal/math.sqrt(p); noise[uniform >= p] = 0.; noises[name] = noise
        H = np.fft.rfft(kernel['taps'], n=nfft)
        for name, x in noises.items():
            y = np.fft.irfft(np.fft.rfft(x, n=nfft)*H, n=nfft)[profile['warmup_frames']:count]*kernel['gain']
            if name == 'post' and index >= 2: y = y*np.sqrt(q[:, index-2])
            outputs[name][:, 0] += y; outputs[name][:, 1] += y*kernel['right_over_left']
    return outputs


def filter_polynomial(x, sos):
    size = 1 << (len(x)+131072-1).bit_length()
    z = np.exp(-2j*np.pi*np.arange(size//2+1)/size); X = np.fft.rfft(x, n=size); columns = []
    for cascade in sos:
        H = np.ones(len(z), complex)
        for s in cascade: H *= (s[0]+s[1]*z+s[2]*z*z)/(s[3]+s[4]*z+s[5]*z*z)
        columns.append(np.fft.irfft(H*X, n=size)[:len(x)])
    return np.array(columns).T


def partitions(items):
    if not items: yield []; return
    first = items[0]
    for rest in partitions(items[1:]):
        yield [[first]]+[block[:] for block in rest]
        for i in range(len(rest)):
            yield [([first]+block if i == j else block[:]) for j, block in enumerate(rest)]


PARTITIONS = list(partitions([0, 1, 2, 3]))
assert len(PARTITIONS) == 15


def curves(x, lags):
    n = len(x); x = x-np.array([math.fsum(x[:, b])/n for b in range(4)])
    v = np.array([math.fsum(x[:, b]**2)/n for b in range(4)])
    first = np.maximum(0, -lags); last = np.minimum(n, n-lags); count = n-abs(lags)
    prefix = {p: np.vstack((np.zeros(4), np.cumsum(x**p, axis=0))) for p in [1, 2]}
    cumulants, covariances = [], []
    for b, c in PAIRS:
        moments = {(0, 0): np.ones(len(lags))}
        for p in [1, 2]: moments[p, 0] = (prefix[p][last, b]-prefix[p][first, b])/count
        for q in [1, 2]: moments[0, q] = (prefix[q][last+lags, c]-prefix[q][first+lags, c])/count
        for p in [1, 2]:
            for q in [1, 2]:
                z = fftconvolve(x[::-1, b]**p, x[:, c]**q, mode='full')
                moments[p, q] = z[n-1+lags]/count
        terms = []
        for partition in PARTITIONS:
            term = np.ones(len(lags))*((-1)**(len(partition)-1)*math.factorial(len(partition)-1))
            for block in partition:
                p = sum(index < 2 for index in block); term *= moments[p, len(block)-p]
            terms.append(term)
        cumulants.append(np.sum(terms, axis=0))
        covariances.append(moments[1, 1]-moments[1, 0]*moments[0, 1])
    K = np.array(cumulants)
    return dict(cumulant=K, variance=v,
                normalized=np.array([K[j]/v[b]/v[c] for j, (b, c) in enumerate(PAIRS)]),
                normalized_covariance=np.array([covariances[j]/np.sqrt(v[b]*v[c]) for j, (b, c) in enumerate(PAIRS)]))


def direct(x, lags):
    v = np.var(x, axis=0); out = np.empty((10, len(lags)))
    for j, (b, c) in enumerate(PAIRS):
        for k, lag in enumerate(lags):
            first, last = max(0, -lag), min(len(x), len(x)-lag)
            u, w = x[first:last, b].copy(), x[first+lag:last+lag, c].copy()
            u -= u.mean(); w -= w.mean()
            out[j, k] = (np.mean((u*w)**2)-np.mean(u*u)*np.mean(w*w)-2*np.mean(u*w)**2)/v[b]/v[c]
    return out
