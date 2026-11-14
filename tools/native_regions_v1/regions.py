"""Native frequency neighborhoods; overlap and unsupported are explicit classes."""
import numpy as np


def source_bounds(positions, times):
    slopes = 1/(1024*np.diff(positions))
    if not np.isfinite(slopes).all() or np.any(slopes <= 0):
        raise ValueError('Finite increasing frozen coordinates required')
    bounds = []
    for first, last in times:
        if first < positions[0] or last > positions[-1]:
            raise ValueError('Window outside observed frozen coordinates')
        at = (positions[:-1] <= last)&(positions[1:] >= first)
        bounds.append([float(slopes[at].min()), float(slopes[at].max())])
    return np.array(bounds)


def labels(bounds, spec, harmonics=288):
    hz = np.arange(spec['fft_samples']//2+1)*spec['rate']/spec['fft_samples']
    padding = 2*spec['rate']/spec['window_samples']
    result = []
    counts = []
    for low, high in bounds:
        if not 0 < low <= high or harmonics*high+padding >= spec['rate']/2:
            raise ValueError('Declared carrier intervals require sub-Nyquist support')
        coverage = np.zeros(len(hz), np.uint16)
        for order in range(1, harmonics+1):
            coverage += ((hz >= order*low-padding)&(hz <= order*high+padding)).astype(np.uint16)
        code = np.where(coverage == 0, 1, np.where(coverage == 1, 0, 2)).astype(np.uint8)
        code[(hz < low-padding)|(hz > harmonics*high+padding)] = 3
        result.append(code);counts.append(coverage)
    return np.array(result), np.array(counts)
