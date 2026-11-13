"""Explicit finite controls before reading original dense observed input."""
import numpy as np
from aperture_model_v1.forward import Aperture, real_rows
from correlated_observation_v1.marginal import MarginalAperture
from complex_radial_v1.loss import gradient, hessian_apply
from .pullback import accumulate


def explicit_rows(operator, start):
    angle = 2*np.pi*operator.bins[:, None]*(np.arange(operator.size)[None, :]+start)/operator.size
    local_angle = 2*np.pi*operator.bins[:, None]*np.arange(operator.size)[None, :]/operator.size
    local = 2/operator.window.sum()*operator.window[None, :]*(np.cos(local_angle)-1j*np.sin(local_angle))
    if hasattr(operator, 'symmetric'):
        local = operator.symmetric@local
        local *= np.exp(-2j*np.pi*operator.bins*start/operator.size)[:, None]
    else:
        local = 2/operator.window.sum()*operator.window[None, :]*(np.cos(angle)-1j*np.sin(angle))
    return np.r_[local.real, local.imag]


def controls():
    plan = dict(samples_per_cycle=16, projection_cycles=2, projection_hop_cycles=1,
        observed_order_range=[1, 3], observed_order_step=.5)
    rng = np.random.default_rng(804319)
    derivative = rng.normal(size=(80, 3)); audio = rng.normal(0, .0003, 80)
    rows = []
    for label, op in (('native', Aperture(80, plan)), ('marginal', MarginalAperture(Aperture(80, plan)))):
        count = len(op.bins)*len(op.starts)
        matrix = np.zeros((2*count, 80)); pieces = []
        for row, start in enumerate(op.starts):
            part = explicit_rows(op, start)
            matrix[row*len(op.bins):(row+1)*len(op.bins), start:start+op.size] = part[:len(op.bins)]
            matrix[count+row*len(op.bins):count+(row+1)*len(op.bins), start:start+op.size] = part[len(op.bins):]
            pieces.append(part)
        assert np.max(abs(real_rows(op.apply(derivative))-matrix@derivative)) < 1e-12
        values = rng.normal(size=(2*count, 3))
        pull, full, independent = accumulate(op, values, 80)
        direct = matrix.T@values
        independent_direct = np.zeros((3, 3))
        for row, part in enumerate(pieces):
            block = np.r_[values[row*len(op.bins):(row+1)*len(op.bins)],
                values[count+row*len(op.bins):count+(row+1)*len(op.bins)]]
            local = part.T@block; independent_direct += local.T@local
        errors = [np.linalg.norm(pull-direct)/np.linalg.norm(direct),
            np.linalg.norm(full-direct.T@direct)/np.linalg.norm(full),
            np.linalg.norm(independent-independent_direct)/np.linalg.norm(independent)]
        assert max(errors) < 1e-12
        residual = real_rows(op.apply(audio)); j = matrix@derivative
        h = hessian_apply(residual, j, .0002); predicted = h.T@(matrix@audio)
        step = 1e-5
        measured = j.T@(gradient(residual+step*(matrix@audio), .0002)-
            gradient(residual-step*(matrix@audio), .0002))/(2*step)
        fd = np.linalg.norm(measured-predicted)/np.linalg.norm(predicted)
        assert fd < 1e-6
        # Fixed complex-coordinate rotation must leave source pullbacks unchanged.
        def rotate(x):
            n = len(x)//2; c, s = np.cos(.37), np.sin(.37)
            return np.r_[c*x[:n]-s*x[n:], s*x[:n]+c*x[n:]]
        rotated_pull = rotate(matrix).T@hessian_apply(rotate(residual), rotate(j), .0002)
        invariant = np.linalg.norm(rotated_pull-matrix.T@h)/np.linalg.norm(matrix.T@h)
        assert invariant < 1e-12
        zero = accumulate(op, np.zeros_like(values), 80)
        assert all(np.count_nonzero(x) == 0 for x in zero)
        rows.append(dict(id=label, explicit_relative_errors=errors, source_score_derivative_error=float(fd),
            fixed_rotation_relative_error=float(invariant), zero_exact=True))
    q = np.array([.2, -.3, .7]); unit = float(q@q)
    duplicate_full = float((q+q)@(q+q)); duplicate_independent = 2*unit
    disjoint = np.r_[q, q]
    assert abs(duplicate_full-4*unit) < 1e-12
    assert abs(duplicate_independent-2*unit) < 1e-12
    assert abs(disjoint@disjoint-duplicate_independent) < 1e-12
    return dict(passed=True, operators=rows, repeated_full_variance=duplicate_full,
        repeated_independent_variance=duplicate_independent, disjoint_equality=True)
