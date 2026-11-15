"""Two-sided orthogonal square-root projection; independent of LSMR recurrence."""
import numpy as np
from scipy import linalg
from observer_representer_v1.primal import PenaltyPrimal
from observer_representer_v1.dual import representer_certificate
from observer_inverse_v1.fit import complex_array
from observer_frequency_v1.optimality import bound


def orthogonalize(raw, basis):
    residual = raw.copy()
    coefficients = np.zeros(basis.shape[1])
    for _ in range(2):
        correction = basis.T@residual
        residual -= basis@correction
        coefficients += correction
    return residual, coefficients


def solve(operator, rhs, maxiter=4000, atol=1e-11, btol=1e-11, conlim=1e12):
    m, n = operator.shape
    capacity = min(maxiter, n)
    U, V = np.empty((m, capacity+1), order='F'), np.empty((n, capacity), order='F')
    H = np.zeros((capacity+1, capacity))
    beta0 = float(np.linalg.norm(rhs))
    if not beta0:
        raise ValueError('Zero rhs is outside these frozen qualification fixtures')
    U[:, 0] = rhs/beta0
    candidate = operator.rmatvec(U[:, 0])
    uc, vc, stop = 1, 0, 7
    checkpoints = []
    threshold = 64*np.finfo(float).eps
    status = 'dimension_or_iteration_limit'
    for j in range(capacity):
        residual, _ = orthogonalize(candidate, V[:, :vc])
        alpha = float(np.linalg.norm(residual))
        if alpha <= threshold*float(np.linalg.norm(candidate)):
            status = 'adjoint_near_breakdown'
            break
        V[:, j] = residual/alpha
        vc += 1
        raw = operator.matvec(V[:, j])
        residual, h = orthogonalize(raw, U[:, :uc])
        H[:uc, j] = h
        beta = float(np.linalg.norm(residual))
        near = beta <= threshold*float(np.linalg.norm(raw))
        if not near:
            H[uc, j] = beta
            U[:, uc] = residual/beta
            uc += 1
        if vc % 8 == 0 or near or vc == capacity:
            projected = H[:uc, :vc]
            Q, R = linalg.qr(projected, mode='economic')
            target = np.zeros(uc)
            target[0] = beta0
            y = linalg.solve_triangular(R, Q.T@target)
            z = V[:, :vc]@y
            r = operator.matvec(z)-rhs
            g = operator.rmatvec(r)
            nr, ng, nz = map(lambda v:float(np.linalg.norm(v)), (r, g, z))
            anorm = float(np.linalg.norm(projected))
            relative_normal = ng/max(anorm*nr, 1e-300)
            compatible = nr <= btol*beta0+atol*anorm*nz
            cond = float(np.linalg.cond(projected))
            stop = 1 if compatible else 2 if relative_normal <= atol else 3 if cond >= conlim else 7
            checkpoints.append(dict(directions=vc, residual_norm=nr, normal_norm=ng,
                projected_Frobenius_estimate=anorm, relative_normal=relative_normal,
                estimated_projected_condition=cond, stop=stop))
            if stop in (1, 2, 3):
                status = 'explicit_stopping_rule'
                break
        if near:
            status = 'forward_near_breakdown'
            break
        candidate = operator.rmatvec(U[:, uc-1])
    if not vc:
        raise ArithmeticError('No right Krylov direction')
    projected = H[:uc, :vc]
    Q, R = linalg.qr(projected, mode='economic')
    target = np.zeros(uc)
    target[0] = beta0
    y = linalg.solve_triangular(R, Q.T@target)
    z = V[:, :vc]@y
    # Near-adjoint termination may occur between declared8-direction checks.
    r, g = operator.matvec(z)-rhs, operator.rmatvec(operator.matvec(z)-rhs)
    nr, ng, nz = map(lambda v:float(np.linalg.norm(v)), (r, g, z))
    anorm = float(np.linalg.norm(projected))
    cond = float(np.linalg.cond(projected))
    stop = 1 if nr <= btol*beta0+atol*anorm*nz else 2 if ng <= atol*anorm*nr else 3 if cond >= conlim else 7
    capture = dict(U=U[:, :uc], V=V[:, :vc], H=projected, rhs=rhs, z=z, y=y,
        U_gram=U[:, :uc].T@U[:, :uc], V_gram=V[:, :vc].T@V[:, :vc])
    info = dict(solver='two_sided_reorthogonalized_square_root_projection', scipy_LSMR=False,
        iterations=vc, stop=stop, status=status, atol=atol, btol=btol, conlim=conlim,
        maxiter=maxiter, projected_condition=cond, projected_Frobenius_estimate=anorm,
        residual_norm=nr, transformed_normal_norm=ng, checkpoints=checkpoints,
        full_projected_corrections_retained=True, no_normal_equations_or_rank_truncation=True)
    return z, info, capture


def infer(system, audio):
    op = PenaltyPrimal(system)
    rhs = np.r_[system.rhs(audio)[:system.ysize], np.zeros(system.nsize)]
    z, info, capture = solve(op, rhs)
    x = op.prior.apply(z)
    nodes = complex_array(x, system.nshape)*system.scale[None]
    residual = system@x-system.rhs(audio)
    u = -residual[:system.ysize]
    gradient = float(np.linalg.norm(system.rmatvec(residual))/max(np.linalg.norm(system.rmatvec(system.rhs(audio))), 1e-24))
    info.update(relative_stationarity=gradient, objective=float(residual@residual),
        converged=bool(info['stop'] in (1, 2, 4, 5) and gradient < 2e-7), same_original_objective=True)
    return nodes, u, info, bound(system, audio, nodes), representer_certificate(system, audio, nodes, u), capture
