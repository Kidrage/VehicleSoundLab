"""Complete mean and lag covariance accounting for measured band powers."""
import numpy as np

PAIRS = [(b, c) for b in range(4) for c in range(b, 4)]


def covariance(x, y, lags):
    result = []
    for lag in lags:
        a, b = (x[:len(x)-lag], y[lag:]) if lag >= 0 else (x[-lag:], y[:len(y)+lag])
        ac, bc = a-a.mean(axis=0), b-b.mean(axis=0)
        result.append([np.mean(ac[:, i] * bc[:, j]) for i, j in PAIRS])
    return np.asarray(result).T


def decompose(target, predicted, scale, lags):
    residual = target-predicted
    denominator = np.asarray([scale[b]*scale[c] for b, c in PAIRS])[:, None]
    terms = {}
    for key, x, y in [('TT', target, target), ('PP', predicted, predicted),
                      ('PR', predicted, residual), ('RP', residual, predicted), ('RR', residual, residual)]:
        terms[key] = covariance(x, y, lags)/denominator
    error = terms['TT']-terms['PP']-terms['PR']-terms['RP']-terms['RR']
    return terms, dict(maximum_closure_error=float(abs(error).max()),
                       prediction_curve_rmse=np.sqrt(np.mean((terms['TT']-terms['PP'])**2, axis=1)).tolist(),
                       target_curve_rms=np.sqrt(np.mean(terms['TT']**2, axis=1)).tolist())
