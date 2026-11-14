"""Joint spectral budgets including literal harmonic/remainder cross terms."""
import numpy as np


def fft_frames(audio, spec):
    n, hop, size = [spec[k] for k in ['window_samples', 'hop_samples', 'fft_samples']]
    starts = np.arange(0, len(audio)-n+1, hop)
    window = .5-.5*np.cos(2*np.pi*np.arange(n)/n)
    return starts, np.fft.rfft(audio[starts[:, None]+np.arange(n)]*window[None, :, None], n=size, axis=1)


def cross(left, right, spec):
    size, rate, n = [spec[k] for k in ['fft_samples', 'rate', 'window_samples']]
    window = .5-.5*np.cos(2*np.pi*np.arange(n)/n)
    scale = np.full(size//2+1, 2/(size*np.dot(window, window)))
    scale[[0, -1]] *= .5
    hz = np.arange(len(scale))*rate/size
    rows = []
    for low, high in spec['bands_hz']:
        keep = (hz >= low)&(hz < high)
        rows.append(np.einsum('wfc,wfd,f->wcd', left[:, keep], right[:, keep].conj(), scale[keep]))
    return np.stack(rows, axis=1) # windows,bands,2,2


def measure(full, harmonic, remainder, spec):
    starts, f = fft_frames(full, spec)
    _, h = fft_frames(harmonic, spec)
    _, r = fft_frames(remainder, spec)
    p, ph, pr, x = [cross(a, b, spec) for a, b in [(f, f), (h, h), (r, r), (h, r)]]
    coupling = x+x.conj().swapaxes(-1, -2)
    arrays = dict(window_starts=starts, P_full=p, P_harmonic=ph, P_remainder=pr,
                  X_HR=x, cross_HR_RH=coupling)
    return arrays
