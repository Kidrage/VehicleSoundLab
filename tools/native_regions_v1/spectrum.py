"""Disjoint positive matrix budgets for fixed native FFT regions."""
import numpy as np


def measure(audio, region, spec):
    n, hop, size, rate = [spec[k] for k in ['window_samples', 'hop_samples', 'fft_samples', 'rate']]
    starts = np.arange(0, len(audio)-n+1, hop)
    window = .5-.5*np.cos(2*np.pi*np.arange(n)/n)
    ft = np.fft.rfft(audio[starts[:, None]+np.arange(n)]*window[None, :, None], n=size, axis=1)
    hz = np.arange(size//2+1)*rate/size
    weight = np.full(len(hz), 2/(size*np.dot(window, window)))
    weight[[0, -1]] *= .5
    assert region.shape == ft.shape[:2] and set(np.unique(region)) <= {0, 1, 2, 3}
    total, parts, count = [], [], []
    for low, high in spec['bands_hz']:
        keep = (hz >= low)&(hz < high)
        products = ft[:, keep, :, None]*ft[:, keep, None, :].conj()*weight[keep][None, :, None, None]
        total.append(products.sum(axis=1))
        parts.append(np.stack([(products*(region[:, keep] == k)[:, :, None, None]).sum(axis=1) for k in range(4)], axis=1))
        count.append(np.stack([(region[:, keep] == k).sum(axis=1) for k in range(4)], axis=1))
    return dict(P_total=np.stack(total, axis=1), P_regions=np.stack(parts, axis=1),
                region_bin_counts=np.stack(count, axis=1), window_starts=starts)
