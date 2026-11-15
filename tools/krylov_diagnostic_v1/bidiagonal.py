"""Unreorthogonalized Golub-Kahan vectors; this probe does not solve or fit audio."""
import numpy as np


def probe(operator, rhs, steps):
    m, n = operator.shape
    rhs = np.asarray(rhs, dtype=float)
    if rhs.shape != (m,) or not np.isfinite(rhs).all() or steps < 1:
        raise ValueError('Invalid diagnostic rhs or step count')
    U = np.empty((m, steps+1))
    V = np.empty((n, steps))
    alpha, beta = [], []
    beta0 = float(np.linalg.norm(rhs))
    uc = vc = 0
    status = 'zero_rhs'
    threshold = 64*np.finfo(float).eps
    if beta0:
        U[:, 0] = rhs/beta0
        uc = 1
        status = 'step_limit'
        for j in range(steps):
            raw = np.asarray(operator.rmatvec(U[:, j]))
            r = raw.copy()
            if j:
                r -= beta[j-1]*V[:, j-1]
            a = float(np.linalg.norm(r))
            alpha.append(a)
            if a <= threshold*max(float(np.linalg.norm(raw)), beta[j-1] if j else 0.):
                status = 'adjoint_near_breakdown'
                break
            V[:, j] = r/a
            vc += 1
            raw = np.asarray(operator.matvec(V[:, j]))
            r = raw-alpha[j]*U[:, j]
            b = float(np.linalg.norm(r))
            beta.append(b)
            if b <= threshold*max(float(np.linalg.norm(raw)), alpha[j]):
                status = 'forward_near_breakdown'
                break
            U[:, j+1] = r/b
            uc += 1
    U, V = U[:, :uc], V[:, :vc]
    gu, gv = U.T@U, V.T@V
    def off(g):
        return float(np.max(abs(g-np.diag(np.diag(g))))) if g.size else 0.
    def diag(g):
        return float(np.max(abs(np.diag(g)-1))) if g.size else 0.
    info = dict(requested_steps=steps, forward_steps=len(beta), adjoint_steps=len(alpha),
        status=status, beta0=beta0, near_breakdown_relative_threshold=threshold,
        U_columns=uc, V_columns=vc, U_max_offdiagonal=off(gu), V_max_offdiagonal=off(gv),
        U_max_diagonal_error=diag(gu), V_max_diagonal_error=diag(gv),
        reorthogonalized=False, no_solution_or_source_fit=True,
        near_breakdown_is_not_rank_or_convergence_proof=True)
    return dict(U=U, V=V, alpha=np.array(alpha), beta=np.array(beta),
        U_gram=gu, V_gram=gv, rhs=rhs), info
