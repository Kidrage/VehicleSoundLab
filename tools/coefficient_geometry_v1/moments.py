"""Quadratic coefficient-power moments; no audio generation or preset fitting."""
import numpy as np


def groups(harmonics, root, bands):
    hz = np.arange(1, harmonics+1)*root
    return [np.array([4*h+2*c+j for h in np.flatnonzero((hz >= lo)&(hz < hi)) for j in (0, 1)], dtype=int)
            for lo, hi in bands for c in (0, 1)]


def empirical(a, index):
    q = np.stack([np.sum(a[:, g]**2, axis=1)/2 for g in index], axis=1)
    mean = q.mean(axis=0)
    centered = q-mean
    return dict(mean=mean, covariance=centered.T@centered/len(q), values=q)


def gaussian(mean, covariance, index):
    means = np.array([(np.sum(mean[g]**2)+np.trace(covariance[np.ix_(g, g)]))/2 for g in index])
    cov = np.empty((len(index), len(index)))
    for i, g in enumerate(index):
        for j, h in enumerate(index):
            block = covariance[np.ix_(g, h)]
            cov[i, j] = np.sum(block**2)/2+mean[g]@block@mean[h]
    return dict(mean=means, covariance=cov)


def model_covariance(model, u=None):
    h, k = model['basis'].shape[:2]
    basis = model['basis'].transpose(0, 2, 1).reshape(4*h, k)
    def scale(rho):
        return np.ones_like(rho) if u is None else 3/(2+rho)*((1-u)**2+u*u+2*rho*u*(1-u))
    covariance = (basis*scale(model['rho']))@basis.T
    residual = model['root']@model['root'].transpose(0, 2, 1)
    residual *= scale(model['residual_rho'])[:, None, None]
    for n in range(h):
        covariance[4*n:4*n+4, 4*n:4*n+4] += residual[n]
    return covariance


def integrate(model, index):
    nodes, weights = np.polynomial.legendre.leggauss(3)
    conditional = [gaussian(model['mean'].ravel(), model_covariance(model, (u+1)/2), index) for u in nodes]
    mean = sum(w*r['mean']/2 for w, r in zip(weights, conditional))
    conditional_covariance = sum(w*r['covariance']/2 for w, r in zip(weights, conditional))
    mean_ripple_covariance = sum(w*np.outer(r['mean']-mean, r['mean']-mean)/2 for w, r in zip(weights, conditional))
    return dict(mean=mean, covariance=conditional_covariance+mean_ripple_covariance,
                conditional_covariance=conditional_covariance, mean_ripple_covariance=mean_ripple_covariance)


def observe(a, root, bands, model):
    index = groups(a.shape[1]//4, root, bands)
    mean = a.mean(axis=0)
    centered = a-mean
    covariance = centered.T@centered/len(a)
    checkpoint = model_covariance(model)
    return dict(empirical=empirical(a, index),
                population_gaussian=gaussian(mean, covariance, index),
                model_checkpoint=gaussian(model['mean'].ravel(), checkpoint, index),
                model_interpolation=integrate(model, index))


def summarize(d):
    out = {}
    for name, r in d.items():
        mean = r['mean']
        std = np.sqrt(np.maximum(0, np.diag(r['covariance'])))
        out[name] = dict(mean_FS2=mean.tolist(), covariance_FS4=r['covariance'].tolist(),
                         power_CV=np.divide(std, mean, out=np.zeros_like(mean), where=mean > 0).tolist())
    delta = d['model_interpolation']['covariance']-d['empirical']['covariance']
    out['signed_model_minus_observed_covariance_eigenvalues_FS4'] = np.linalg.eigvalsh(delta).tolist()
    return out
