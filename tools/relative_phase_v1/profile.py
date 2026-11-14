"""Compile a source-independent stereo copula with explicit relative phase."""
import numpy as np
from scipy.special import ndtri
from scipy.stats import rankdata
from radial_copula_v1.quantiles import integral
from .coordinates import encode


def compile_rows(rows, components=12, rho_cap=.95):
    n, width = rows.shape
    h = width//4
    q = rows.reshape(n, h, 2, 2)
    z = q[..., 0]+1j*q[..., 1]
    amplitude = abs(z).reshape(n, 2*h)
    phase, cuts = encode(z)
    amp_table = np.sort(amplitude, axis=0)
    second = np.mean(amplitude**2, axis=0)
    normalization = np.sqrt(np.divide(second, integral(amp_table, 2),
                                     out=np.ones_like(second), where=second>0))
    amp_table *= normalization
    features = np.column_stack([amplitude, phase])
    tolerance = np.r_[64*np.finfo(float).eps*np.maximum(amplitude.max(axis=0), 1e-6),
                      np.full(2*h, 1e-12)]
    active = np.ptp(features, axis=0)>tolerance
    scores = ndtri((rankdata(features, axis=0, method='average')-.5)/n)
    scores -= scores.mean(axis=0)
    std = np.sqrt(np.mean(scores**2, axis=0))
    scores = np.divide(scores, std, out=np.zeros_like(scores), where=active & (std>0))
    u, s, v = np.linalg.svd(scores, full_matrices=False)
    rank = int(np.sum(s>max(float(s[0])*1e-10, 1e-12))) if len(s) else 0
    k = min(components, rank, n-1)
    basis = (v[:k]*(s[:k, None]/np.sqrt(n))).T
    pc = u[:, :k]*np.sqrt(n)
    for j in range(k):
        if basis[np.argmax(abs(basis[:, j])), j]<0:
            basis[:, j] *= -1
            pc[:, j] *= -1
    residual = scores-pc@basis.T
    def rho(value):
        denominator = np.sum(value[:-1]**2, axis=0)
        return np.clip(np.divide(np.sum(value[1:]*value[:-1], axis=0), denominator,
                                out=np.zeros(value.shape[1]), where=denominator>1e-20),
                       -rho_cap, rho_cap)
    model = dict(amplitude=amp_table, phase=np.sort(phase, axis=0),
                 fixed_phase=np.angle(z.mean(axis=0)), phase_cuts=cuts,
                 basis=basis, rho=rho(pc), residual_std=np.sqrt(np.mean(residual**2, axis=0)),
                 residual_rho=rho(residual), active=active, target_amplitude_second=second)
    training = dict(source_rows=rows, amplitude=amplitude, coordinates=phase, scores=scores,
                    pc=pc, residual=residual, normalization=normalization)
    return model, training
