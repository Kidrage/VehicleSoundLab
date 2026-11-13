"""Independent 2x2 residual geometry and replay of saved steps, without solves."""
import numpy as np
from joint_trust_v1.constraints import Region
from .loss import cost, gradient, hessian_apply, quadratic


def relative(a, b):
    return float(np.linalg.norm(a-b)/max(np.linalg.norm(b), 1e-30))


def explicit(residual, matrix, scale):
    """Build individual symmetric blocks, independently of the production helper."""
    count = len(residual)//2
    r = np.column_stack((residual[:count], residual[count:]))
    norm = np.hypot(r[:, 0], r[:, 1])
    v = 1/np.sqrt(1+(norm/scale)**2)
    unit = np.divide(r, norm[:, None], out=np.zeros_like(r), where=norm[:, None] != 0)
    projector = np.einsum('ni,nj->nij', unit, unit)
    tangent = np.eye(2)[None, :, :]-projector
    block = v[:, None, None]*tangent+v[:, None, None]**3*projector
    root = np.sqrt(v)[:, None, None]*tangent+v[:, None, None]**1.5*projector
    paired = np.stack((matrix[:count], matrix[count:]), axis=1)
    applied = np.einsum('nij,njk->nik', root, paired)
    weighted = np.concatenate((applied[:, 0], applied[:, 1]))
    psi = np.concatenate((v*r[:, 0], v*r[:, 1]))
    value = float(np.sum(norm**2/(np.hypot(1., norm/scale)+1)))
    return value, psi, weighted, block, root


def check_geometry(residual, matrix, scale):
    value, psi, weighted, blocks, roots = explicit(residual, matrix, scale)
    gram, linear, actual_weighted, rhs = quadratic(residual, matrix, scale)
    # Use executed helper arithmetic for bitwise replay of original certificates;
    # independently built blocks above check the geometry to a fixed tolerance.
    count = len(residual)//2
    paired = np.stack((matrix[:count], matrix[count:]), axis=1)
    full_h = np.einsum('nij,njk->nik', blocks, paired)
    full_h = np.concatenate((full_h[:, 0], full_h[:, 1]))
    errors = dict(cost=abs(value-cost(residual, scale))/max(abs(value), 1e-30),
        psi=relative(psi, gradient(residual, scale)), root_factor=relative(weighted, actual_weighted),
        hessian=relative(full_h, hessian_apply(residual, matrix, scale)),
        root_squared=relative(np.einsum('nij,njk->nik', roots, roots), blocks),
        gram=relative(weighted.T@weighted, gram), linear=relative(matrix.T@psi, linear),
        rhs_gradient=relative(actual_weighted.T@rhs, -linear))
    assert max(errors.values()) <= 1e-12, errors
    return gram, linear, actual_weighted, errors


def reconstruct(model, initial, target, plan, settings, fit, certificate, progress=None):
    outer, amplitudes = model.unpack(initial)
    scale = plan['soft_l1_scale']
    value, phase = model.prediction(outer, amplitudes, True)
    matrix = np.column_stack((phase, model.design(outer)))
    _, _, weighted, _, _ = explicit(value-target, matrix, scale)
    actual_weighted = hessian_apply(value-target, matrix, scale, .5)
    assert relative(weighted, actual_weighted) <= 1e-12
    def scales_from_factor(factor):
        norms = np.linalg.norm(factor, axis=0)
        m = model.original
        caps = np.r_[np.full(m.parts, np.pi), np.full(m.phase_count, model.phase_bound),
            np.full(len(m.selected)*m.departure_count, model.departure_bound)]
        theta = np.minimum(1/np.maximum(norms[:len(outer)], 1e-30), caps)
        group_norm = norms[len(outer):].reshape(amplitudes.shape).max(axis=1)
        group = np.minimum(1/np.maximum(group_norm, 1e-30), np.sqrt(2.))
        return np.r_[theta, np.broadcast_to(group[:, None], amplitudes.shape).ravel()]
    scales = scales_from_factor(actual_weighted)
    assert np.array_equal(scales, np.asarray(fit['scales']))
    independent_scale_error = relative(scales_from_factor(weighted), scales)
    assert independent_scale_error <= 1e-12
    assert cost(value-target, scale) == fit['initial_cost']
    radius, trace = settings['initial_radius'], []
    for index, row in enumerate(fit['history'], 1):
        assert row['iteration'] == index and row['radius'] == radius
        value, phase = model.prediction(outer, amplitudes, True)
        matrix = np.column_stack((phase, model.design(outer)))*scales[None, :]
        residual = value-target
        assert cost(residual, scale) == row['before_cost']
        gram, linear, weighted, errors = check_geometry(residual, matrix, scale)
        region = Region(model, outer, amplitudes, scales, radius, settings)
        checked = certificate(row['qp'], gram, linear, region, weighted)
        step = np.asarray(row['qp']['primal_solution'])
        new_outer, new_amplitudes, effective, feasible = region.retract(step)
        assert feasible == row['feasibility']
        assert np.array_equal(new_outer, np.asarray(row['candidate_outer']))
        assert np.array_equal(new_amplitudes, np.asarray(row['candidate_absolute_amplitudes']))
        candidate = cost(model.prediction(new_outer, new_amplitudes)-target, scale)
        predicted = float(-linear@effective-.5*effective@gram@effective)
        actual = row['before_cost']-candidate
        ratio = actual/predicted if predicted > 0 else None
        accepted = bool(checked['success'] and feasible['feasible'] and predicted > 0 and actual > 0
            and ratio >= settings['acceptance_ratio'])
        assert candidate == row['candidate_cost'] and predicted == row['predicted_reduction']
        assert actual == row['actual_reduction'] and ratio == row['ratio'] and accepted == row['accepted']
        assert float(abs(effective).max()) == row['scaled_step_maximum']
        if accepted:
            outer, amplitudes = new_outer, new_amplitudes
        if not accepted or ratio < .25:
            radius *= .25
        elif ratio > .75 and abs(effective).max() > .8*radius:
            radius = min(2*radius, settings['maximum_radius'])
        trace.append(dict(iteration=index, accepted=accepted, certificate=checked,
            independent_geometry_errors=errors, candidate_retraction_objective_radius_exact=True))
        if progress:
            progress(trace[-1])
        if radius < settings['minimum_radius']:
            assert index == len(fit['history'])
            break
    assert radius == fit['final_radius'] and len(trace) == fit['iterations']
    assert sum(row['accepted'] for row in trace) == fit['accepted_steps']
    parameters = model.pack(outer, amplitudes)
    residual = model.original.prediction(parameters)-target
    assert cost(residual, scale) == fit['final_cost']
    assert float(np.linalg.norm(residual)/np.linalg.norm(target)) == fit['normalized_projection_residual']
    return parameters, trace, independent_scale_error
