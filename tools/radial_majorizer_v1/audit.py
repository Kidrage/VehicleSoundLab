"""Scalar complex-power and cosine reconstruction independent of majorizer code."""
import math
import numpy as np
from aperture_model_v1.forward import real_rows
from complex_radial_v1.audit import relative
from .geometry import quadratic


def scalar_cost(residual, scale):
    n = len(residual)//2
    return math.fsum((float(residual[k])**2+float(residual[k+n])**2)/
        (math.sqrt(1+(float(residual[k])**2+float(residual[k+n])**2)/scale**2)+1) for k in range(n))


def geometry(residual, matrix, scale):
    n = len(residual)//2
    v = np.array([1/math.sqrt(1+(float(residual[k])**2+float(residual[k+n])**2)/scale**2) for k in range(n)])
    diagonal = np.r_[v, v]
    independent_weighted = matrix*np.sqrt(diagonal)[:, None]
    independent_gradient = matrix.T@(diagonal*residual)
    gram, g, weighted, rhs = quadratic(residual, matrix, scale)
    errors = dict(weighted=relative(independent_weighted, weighted),
        gram=relative(independent_weighted.T@independent_weighted, gram),
        gradient=relative(independent_gradient, g), rhs=relative(-np.sqrt(diagonal)*residual, rhs),
        factor_gradient=relative(weighted.T@rhs, -g))
    assert max(errors.values()) <= 1e-12
    return gram, g, weighted, errors, v


def independent_wave_and_jacobian(model, outer, controls):
    m = model.original; correction = m.phase_basis@outer[model.parts:]
    amplitude = model.full@controls.T
    result = np.zeros(len(correction)); slope = np.zeros((len(correction), model.parts))
    amplitude_columns = []
    for k, order in enumerate(m.orders):
        angle = 2*np.pi*order*(m.time+correction)+outer[k]
        cosine = np.cos(angle); sine = np.sin(angle)
        result += amplitude[:, k]*cosine; slope[:, k] = -amplitude[:, k]*sine
        amplitude_columns.append(cosine[:, None]*model.full)
    common = np.sum(slope*(2*np.pi*m.orders)[None, :], axis=1)
    jacobian = np.column_stack((slope, common[:, None]*m.phase_basis, *amplitude_columns))
    return real_rows(m.aperture.apply(result)), real_rows(m.aperture.apply(jacobian))
