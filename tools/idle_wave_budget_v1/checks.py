"""Exact local innovation ensembles before any recording-derived architecture is read."""
import itertools
import numpy as np
from .response import Fields
from .moments import pooled, MOMENTS


def fixtures():
    h = np.array([[[.8, .3], [-.2, .5]], [[.1, -.4], [.6, .2]]])
    warmup, frames = 2, 8
    time = np.arange(warmup+frames)
    v = np.column_stack((1+.4*np.cos(time*.73), .8+.3*np.sin(time*.37)))
    m = np.column_stack((.1+.2*np.cos(time[warmup:]*.31), -.04+.15*np.sin(time[warmup:]*.59)))
    return h, v, m, warmup, frames


def ensembles(h, v, m, warmup, b, c, lag, levels, probabilities):
    raw = []; conditional_covariance = []; conditional_cumulant = []
    for n in range(max(0, -lag), min(len(m), len(m)-lag)):
        keys = sorted({(i, n+warmup-u) for i in range(2) for u in range(2)} |
                      {(i, n+lag+warmup-u) for i in range(2) for u in range(2)})
        draws = np.array(list(itertools.product(range(len(levels)), repeat=len(keys))))
        weights = np.prod(np.asarray(probabilities)[draws], axis=1)
        values = np.asarray(levels)[draws]
        output = []
        for band, moment in [(b, n), (c, n+lag)]:
            out = np.full(len(draws), m[moment, band])
            for i in range(2):
                for u in range(2):
                    k = moment+warmup-u
                    out += h[band, i, u]*np.sqrt(v[k, i])*values[:, keys.index((i, k))]
            output.append(out)
        x, y = output
        raw.append([weights@(x**p*y**q) for p, q in MOMENTS])
        a, d = x-m[n, b], y-m[n+lag, c]
        covariance = weights@(a*d)
        conditional_covariance.append(covariance)
        conditional_cumulant.append(weights@(a*a*d*d)-(weights@(a*a))*(weights@(d*d))-2*covariance**2)
    return np.mean(raw, axis=0), np.asarray(conditional_covariance), np.asarray(conditional_cumulant)


def run(out):
    h, v, m, warmup, frames = fixtures()
    outcomes = []
    for label, levels, weights, kappa in [
        ('binary', [-1., 1.], [.5, .5], -2.),
        ('Gaussian_moments', [-np.sqrt(3), 0., np.sqrt(3)], [1/6, 2/3, 1/6], 0.),
        ('sparse', [-np.sqrt(6), 0., np.sqrt(6)], [1/12, 5/6, 1/12], 3.)]:
        model = Fields(h, v, warmup, frames, np.full(2, kappa))
        variance = model.variances()
        maximum = 0.; saved = dict(h=h, v=v, m=m, levels=np.asarray(levels), weights=np.asarray(weights))
        for b, c in [(0, 0), (0, 1), (1, 1)]:
            for lag in range(-2, 3):
                C, J = model.pair(b, c, lag)
                first, last = max(0, -lag), min(frames, frames-lag)
                section = slice(first, last); other = slice(first+lag, last+lag)
                result = pooled(m[section, b], m[other, c], variance[section, b], variance[other, c], C[section], J[section])
                raw, expected_C, expected_J = ensembles(h, v, m, warmup, b, c, lag, levels, weights)
                error = max(float(abs(raw-result['raw']).max()), float(abs(expected_C-C[section]).max()),
                            float(abs(expected_J-J[section]).max()))
                assert error < 1e-12, (label, b, c, lag, error)
                # Cumulant from explicit pooled raw moments, independent of decomposition.
                mx, my, xx, yy, xy, xxy, xyy, xxyy = raw
                central = xxyy-2*my*xxy-2*mx*xyy+4*mx*my*xy+my*my*xx+mx*mx*yy-3*mx*mx*my*my
                cumulant = central-(xx-mx*mx)*(yy-my*my)-2*(xy-mx*my)**2
                assert abs(cumulant-result['cumulant']) < 1e-12
                maximum = max(maximum, error, abs(cumulant-result['cumulant']))
                saved[f'raw_{b}_{c}_{lag}'] = raw
        path = out/(label+'.npz'); np.savez_compressed(path, **saved)
        outcomes.append(dict(label=label, kappa=kappa, error=maximum, file=path.name))
    stationary = Fields(h, np.ones_like(v), warmup, frames, np.array([1., 3.]), stationary=True)
    general = Fields(h, np.ones_like(v), warmup, frames, np.array([1., 3.]))
    for b in range(2):
        for c in range(2):
            for lag in range(-2, 3):
                for x, y in zip(stationary.pair(b, c, lag), general.pair(b, c, lag)):
                    assert abs(x-y).max() < 1e-12
    return dict(exact_ensembles=outcomes, stationary_identity=True, source_read=False)
