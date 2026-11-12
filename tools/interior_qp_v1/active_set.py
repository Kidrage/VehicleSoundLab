"""Finite active-set, null-space least-squares refinement of the ORIGINAL QP."""
import numpy as np
import scipy.linalg as la


def polish(gram, gradient, weighted, rhs, rows, bounds, initial, settings):
    dense = rows.toarray()
    contact = np.flatnonzero(bounds-dense@initial <= settings['maximum_primal_violation']).tolist()
    maximum_gradient = float(abs(gradient).max())
    scale = maximum_gradient if maximum_gradient > 0 else max(float(abs(gram).max()), 1.)
    h = (gram+gram.T)/(2*scale)
    history = []
    x = initial.copy()
    z = np.zeros(len(bounds))
    for iteration in range(1, settings['active_set_maximum_steps']+1):
        if contact:
            active = dense[contact]
            q, r, permutation = la.qr(active.T, mode='full', pivoting=True)
            rank = int(np.sum(abs(np.diag(r)) > max(abs(r).max(), 1e-30)*np.finfo(float).eps*max(active.shape)))
            kept = [contact[int(index)] for index in permutation[:rank]]
            active = dense[kept]
            q, r = la.qr(active.T, mode='full')
            particular = q[:, :rank]@la.solve_triangular(r[:rank, :rank].T, bounds[kept], lower=True)
            null = q[:, rank:]
            contact = kept
        else:
            rank, particular, null = 0, np.zeros(len(gradient)), np.eye(len(gradient))
        free = weighted@null
        value, _, free_rank, _ = la.lstsq(free, rhs-weighted@particular, cond=None, lapack_driver='gelsy')
        x = particular+null@value
        slack = bounds-dense@x
        primal = float(max(0., -slack.min()))
        if primal > settings['maximum_primal_violation']:
            worst = int(np.argmin(slack))
            history.append(dict(iteration=iteration, action='add_violated', index=worst, violation=primal,
                contact_rank=rank, free_rank=int(free_rank)))
            if worst in contact:
                break
            contact.append(worst)
            continue
        normalized_gradient = h@x+gradient/scale
        z = np.zeros(len(bounds))
        if contact:
            multipliers = la.lstsq(dense[contact].T, -normalized_gradient, cond=None, lapack_driver='gelsy')[0]
            z[contact] = multipliers
            if multipliers.min() < -settings['maximum_primal_violation']:
                worst = int(np.argmin(multipliers))
                history.append(dict(iteration=iteration, action='drop_negative_dual', index=contact[worst],
                    dual=float(multipliers[worst]), contact_rank=rank, free_rank=int(free_rank)))
                contact.pop(worst)
                continue
        stationarity = float(abs(normalized_gradient+dense.T@z).max())
        sign = float(max(0., -z.min()))
        complementarity = float(abs(z*slack).max())
        success = bool(primal <= settings['maximum_primal_violation']
            and stationarity <= settings['maximum_normalized_stationarity']
            and sign <= settings['maximum_primal_violation']
            and complementarity <= settings['maximum_complementarity'])
        history.append(dict(iteration=iteration, action='certify', success=success, primal=primal,
            stationarity=stationarity, dual_sign=sign, complementarity=complementarity,
            contact_rank=rank, free_rank=int(free_rank)))
        return x, z, dict(success=success, history=history, iterations=iteration,
            stationarity=stationarity, primal=primal, dual_sign=sign, complementarity=complementarity,
            objective=float(.5*x@gram@x+gradient@x), original_limits_unchanged=True)
    return x, z, dict(success=False, history=history, iterations=iteration,
        reason='Finite active-set budget or repeated numerically violated contact', original_limits_unchanged=True)
