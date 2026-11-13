"""Primal-feasible blocking path for the original least-squares QP."""
import numpy as np
import scipy.linalg as la


def evidence(gram, gradient, rows, bounds, x, contact):
    scale = float(abs(gradient).max())
    if scale == 0:
        scale = max(float(abs(gram).max()), 1.)
    h = (gram+gram.T)/(2*scale)
    normal = h@x+gradient/scale
    z = np.zeros(len(bounds))
    if contact:
        z[contact] = la.lstsq(rows[contact].T, -normal, cond=None, lapack_driver='gelsy')[0]
    slack = bounds-rows@x
    return z, dict(primal=float(max(0., -slack.min())),
        stationarity=float(abs(normal+rows.T@z).max()),
        dual_sign=float(max(0., -z.min())),
        complementarity=float(abs(z*slack).max()))


def passes(q, settings):
    return bool(q['primal'] <= settings['maximum_primal_violation']
        and q['stationarity'] <= settings['maximum_normalized_stationarity']
        and q['dual_sign'] <= settings['maximum_primal_violation']
        and q['complementarity'] <= settings['maximum_complementarity'])


def polish(gram, gradient, weighted, rhs, rows, bounds, initial, settings):
    dense = rows.toarray()
    x = initial.copy()
    initial_violation = float(max(0., np.max(dense@x-bounds)))
    if initial_violation > settings['maximum_primal_violation']:
        return x, np.zeros(len(bounds)), dict(success=False, iterations=0, history=[],
            reason='Saved coarse candidate is not feasible at original tolerance')
    contact = np.flatnonzero(bounds-dense@x <= settings['maximum_primal_violation']).tolist()
    history = []
    for iteration in range(1, settings['active_set_maximum_steps']+1):
        start = x.copy()
        if contact:
            active = dense[contact]
            q, r, permutation = la.qr(active.T, mode='full', pivoting=True)
            rank = int(np.sum(abs(np.diag(r)) > max(abs(r).max(), 1e-30)*np.finfo(float).eps*max(active.shape)))
            contact = [contact[int(index)] for index in permutation[:rank]]
            q, r = la.qr(dense[contact].T, mode='full')
            particular = q[:, :rank]@la.solve_triangular(r[:rank, :rank].T, bounds[contact], lower=True)
            null = q[:, rank:]
        else:
            rank, particular, null = 0, np.zeros(len(gradient)), np.eye(len(gradient))
        before_contact = contact.copy()
        free = weighted@null
        value, _, free_rank, _ = la.lstsq(free, rhs-weighted@particular, cond=None, lapack_driver='gelsy')
        minimum = particular+null@value
        direction = minimum-x
        projected = dense@direction
        slack = bounds-dense@x
        # Every original inequality participates; working rows aim at equality.
        eligible = np.ones(len(bounds), dtype=bool)
        eligible[contact] = False
        eligible &= projected > 0
        fractions = np.full(len(bounds), np.inf)
        fractions[eligible] = np.maximum(0., slack[eligible])/projected[eligible]
        blocker = int(np.argmin(fractions))
        alpha = min(1., float(fractions[blocker]))
        x = minimum if alpha == 1. else x+alpha*direction
        if alpha < 1.:
            contact.append(blocker)
        z, certificate = evidence(gram, gradient, dense, bounds, x, contact)
        passed = passes(certificate, settings)
        row = dict(iteration=iteration, start=start.tolist(), working_before=before_contact,
            contact_rank=rank, free_rank=int(free_rank), equality_minimum=minimum.tolist(),
            fraction=alpha, blocker=blocker if alpha < 1. else None,
            primal_solution=x.tolist(), inequality_dual=z.tolist(), working_after_move=contact.copy(),
            certificate=certificate, success=passed)
        if passed:
            row['action'] = 'certify'
            history.append(row)
            return x, z, dict(success=True, history=history, iterations=iteration,
                original_limits_unchanged=True, all_original_inequalities_retained=True)
        if alpha < 1.:
            row['action'] = 'first_blocker'
        elif contact and min(z[contact]) < -settings['maximum_primal_violation']:
            worst = int(np.argmin(z[contact]))
            row.update(action='drop_negative_dual', dropped=contact[worst])
            contact.pop(worst)
        else:
            row['action'] = 'full_minimum_uncertified'
            history.append(row)
            return x, z, dict(success=False, history=history, iterations=iteration,
                reason='Full feasible equality minimum fails original numerical certificate',
                original_limits_unchanged=True)
        history.append(row)
    return x, z, dict(success=False, history=history, iterations=iteration,
        reason='Original finite active-set budget exhausted', original_limits_unchanged=True)
