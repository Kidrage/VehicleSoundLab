"""Band and stereo observations, without post-fit level correction."""
import numpy as np
from sound_dna.windowed import coefficients


def moments(audio, root, harmonics, bands):
    rows = coefficients(audio, harmonics).reshape(-1, harmonics, 4)
    z = rows[:, :, ::2]+1j*rows[:, :, 1::2]
    orders = np.arange(1, harmonics+1)
    power, correlation = [], []
    for lo, hi in bands:
        keep = (orders*root >= lo) & (orders*root < hi)
        p = np.mean(abs(z[:, keep])**2, axis=0).sum(axis=0)/2
        cross = np.mean(z[:, keep, 0]*np.conj(z[:, keep, 1]), axis=0).sum()/2
        power.append(p)
        correlation.append(cross/np.sqrt(max(float(p.prod()), 1e-60)))
    return np.asarray(power), np.asarray(correlation)


def difference(first, second):
    a, ac = first
    b, bc = second
    return dict(power_difference_db_LR=(10*np.log10(np.maximum(b,1e-30)/np.maximum(a,1e-30))).tolist(),
                complex_correlation_difference=abs(bc-ac).tolist(),
                power_before_LR=a.tolist(), power_after_LR=b.tolist())
