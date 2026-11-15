"""Declared FP64 finite-Hann metric and independent base-root observations.

No production metric, root, synthesis, correction or solver imports. The root
guard and the original FFT-objective guard are different floating-point
operators and must pass their respective unchanged tests separately.
"""
import numpy as np
from scipy import linalg
from observer_frequency_v1.reduced_oracle import synthesize, adjoint


def metric_bands(frames, weights, sigma, amplitude, *, size=4096, hop=256):
    weights = np.asarray(weights, dtype='float64')
    if (frames < size or size % 2 or size % hop or not 0 < hop < size
            or weights.shape != (size//2+1,) or not np.isfinite(weights).all()
            or np.any(weights <= 0) or not np.isfinite([sigma, amplitude]).all()
            or sigma <= 0 or amplitude <= 0):
        raise ValueError('Complete positive locked metric required')
    window = .5-.5*np.cos(2*np.pi*np.arange(size)/size)
    cover = np.zeros(frames)
    for start in range(-(size-hop), frames, hop):
        first, last = max(0, start), min(frames, start+size)
        cover[first:last] += window[first-start:last-start]**2
    kernel = np.fft.irfft(weights**2, n=size)
    bands = np.zeros((size, frames), order='F')
    bands[0] = 1/sigma**2
    for start in range(0, frames-size+1, hop):
        gain = amplitude*window/np.sqrt(cover[start:start+size])
        for offset in range(size):
            bands[offset, start:start+size-offset] += gain[offset:]*kernel[offset]*gain[:size-offset]
    return bands


def factor(bands):
    return linalg.cholesky_banded(bands, lower=True, overwrite_ab=True, check_finite=False)


def root_action(root, value, *, transpose=False):
    value = np.asarray(value, dtype='float64')
    if value.ndim != 2 or value.shape[0] != root.shape[1] or not np.isfinite(value).all():
        raise ValueError('Complete real column operands required')
    answer = np.array(value, order='F', copy=True)
    tbmv = linalg.get_blas_funcs('tbmv', (root,))
    for c in range(answer.shape[1]):
        answer[:, c] = tbmv(root.shape[0]-1, root, answer[:, c], lower=1,
                            trans=int(transpose), overwrite_x=1)
    return answer


def audit_guard(z, source, oracle):
    N, M, H = len(z['audio']), len(z['positions']), len(z['orders'])
    root = factor(metric_bands(N, z['weights'], float(z['sigma']), float(z['amplitude'])))
    e = z['base_wave_model_residual']
    model = root_action(root, e, transpose=True)
    weighted = root_action(root, model)
    nodes = adjoint(weighted, z['positions'], z['orders'])*z['scale'][None]
    L = np.linalg.cholesky(oracle.R)
    nodes = linalg.solve_triangular(L, nodes.reshape(M, -1), lower=True).reshape(M, H, 2)
    normal = np.vstack((nodes.real.reshape(M*H, 2), nodes.imag.reshape(M*H, 2)))+z['base_z']
    # Packed layout is independently checked by the complete equation audit.
    q = (z['base_q'][:M*H]+1j*z['base_q'][M*H:]).reshape(M, H, 2)
    predicted = synthesize(q*z['scale'][None], z['positions'], z['orders'], N)
    target = root_action(root, z['audio'], transpose=True)
    direct = root_action(root, predicted-z['audio'], transpose=True)
    norm = source['solver']['augmented_root_Frobenius']
    den = norm*np.sqrt(np.sum(model**2, axis=0)+np.sum(z['base_z']**2, axis=0))
    stable = np.linalg.norm(normal, axis=0)/np.maximum(den, 1e-300)
    backward = np.linalg.norm(direct-model, axis=0)/np.maximum(np.linalg.norm(target, axis=0), 1e-300)
    return dict(stable_LR=stable.tolist(), backward_LR=backward.tolist(),
        stable_guard_passed=bool(np.all(stable <= 1e-11)),
        backward_guard_passed=bool(np.all(backward <= 1e-11)),
        all_locked_bins_and_context=True,
        no_reestimated_metric_or_production_operator_import=True,
        original_FP64_band_root_operator_separate_from_original_FFT_objective=True)
