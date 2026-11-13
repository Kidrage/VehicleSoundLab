"""Cross-innovation-seed conditional-power statistics and paired jackknife."""
import numpy as np
from scipy.stats import t

PAIRS = [(b, c) for b in range(4) for c in range(b+1, 4)]
LABELS = ([f'mean_{b}' for b in range(4)]+[f'mse_{b}' for b in range(4)]+
          [f'target_corr_{b}' for b in range(4)]+[f'cross_corr_{b}_{c}' for b, c in PAIRS])


def exact(values, target):
    centered = values-values.mean(axis=0); guide = target-target.mean(axis=0)
    cov = centered.T@centered/len(values); var = np.diag(cov)
    return np.r_[values.mean(axis=0), ((values-target)**2).mean(axis=0),
                 (centered*guide).mean(axis=0)/np.sqrt(var*(guide*guide).mean(axis=0)),
                 [cov[b, c]/np.sqrt(var[b]*var[c]) for b, c in PAIRS]]


def estimate(samples, target):
    count, size, _ = samples.shape
    mean = samples.mean(axis=0)
    centered = samples-samples.mean(axis=1, keepdims=True)
    average_centered = mean-mean.mean(axis=0)
    covariance = (count**2*(average_centered.T@average_centered)-
                  np.einsum('rtb,rtc->bc', centered, centered))/(size*count*(count-1))
    variance = np.diag(covariance)
    guide = target-target.mean(axis=0)
    correction = ((samples-mean)**2).sum(axis=0).mean(axis=0)/(count*(count-1))
    mse = ((mean-target)**2).mean(axis=0)-correction
    if np.any(variance <= 0):
        raise ValueError('Unstable estimated conditional variance; retain failed attempt')
    correlations = (average_centered*guide).mean(axis=0)/np.sqrt(variance*(guide*guide).mean(axis=0))
    cross = [covariance[b, c]/np.sqrt(variance[b]*variance[c]) for b, c in PAIRS]
    return np.r_[mean.mean(axis=0), mse, correlations, cross]


def jackknife(samples, target):
    full = estimate(samples, target)
    leave = np.asarray([estimate(np.delete(samples, i, axis=0), target) for i in range(len(samples))])
    se = np.sqrt((len(samples)-1)/len(samples)*((leave-leave.mean(axis=0))**2).sum(axis=0))
    radius = t.ppf(.975, len(samples)-1)*se
    return dict(point=full, leave=leave, se=se, low=full-radius, high=full+radius)


def contrast(pre, post, count):
    point = post['point']-pre['point']; leave = post['leave']-pre['leave']
    se = np.sqrt((count-1)/count*((leave-leave.mean(axis=0))**2).sum(axis=0))
    radius = t.ppf(.975, count-1)*se
    family_radius = t.ppf(1-.05/(2*8), count-1)*se[4:8]
    return dict(point=point, se=se, low=point-radius, high=point+radius,
                mse_family_low=point[4:8]-family_radius, mse_family_high=point[4:8]+family_radius)
