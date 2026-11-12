"""Sparse independent QP backend, normalized by observed gradient magnitude."""
import numpy as np
import scipy.sparse as sp
import osqp


def linear_system(region):
    n = len(region.base)
    rows, columns, values = [], [], []
    lower, upper = list(region.lower), list(region.upper)
    for k in range(n):
        rows.append(k); columns.append(k); values.append(1.)
    def append(items, lo, hi):
        row = len(lower)
        for column, value in items:
            rows.append(row); columns.append(column); values.append(value)
        lower.append(lo); upper.append(hi)
    for k in range(region.model.parts):
        first = region.first[k]
        c0 = region.controls[k, 0]
        append([(first, region.scales[first])], -c0, np.sqrt(2)-c0)
        for j in range(1, region.model.controls):
            for multiplier in (1-region.model.bound, 1+region.model.bound):
                items = [(first+j, region.scales[first+j]), (first, -multiplier*region.scales[first])]
                offset = multiplier*c0-region.controls[k, j]
                append(items, offset if multiplier < 1 else -np.inf,
                    np.inf if multiplier < 1 else offset)
    for a, b, limit in region.planes:
        for k in range(region.model.parts):
            append([(region.first[k], a[k]), (k, b[k])], -np.inf, limit[k])
    return sp.csc_matrix((values, (rows, columns)), shape=(len(lower), n)), np.asarray(lower), np.asarray(upper)


def solve(gram, gradient, region, settings):
    matrix, lower, upper = linear_system(region)
    objective_scale = max(float(abs(gradient).max()), np.finfo(float).tiny)
    normalized = (gram+gram.T)/(2*objective_scale)
    problem = osqp.OSQP()
    problem.setup(P=sp.csc_matrix(np.triu(normalized)), q=gradient/objective_scale,
        A=matrix, l=lower, u=upper, verbose=False, eps_abs=settings['osqp_eps_abs'],
        eps_rel=settings['osqp_eps_rel'], max_iter=settings['osqp_max_iterations'],
        polishing=True, polish_refine_iter=10, check_termination=25)
    solution = problem.solve(raise_error=False)
    if solution.x is None or solution.y is None:
        raise ArithmeticError('Independent convex solver returned no primal/dual candidate')
    x = np.asarray(solution.x)
    observed = matrix@x
    violation = float(max(0., np.max(lower-observed), np.max(observed-upper)))
    stationarity = normalized@x+gradient/objective_scale+matrix.T@solution.y
    dual = float(abs(stationarity).max())
    native = solution.info
    largest = float(np.linalg.eigvalsh(gram)[-1])
    return x, dict(success=bool(native.status_val==1 and violation<=1e-9 and dual<=1e-8), iterations=int(native.iter),
        status=native.status, status_value=int(native.status_val), solver_version=osqp.__version__,
        normalized_dual_stationarity=dual, constraint_violation=violation,
        original_objective_dual_stationarity=dual*objective_scale,
        objective_scale=objective_scale, old_unit_floor_relative_to_gradient=1/objective_scale,
        native_primal_residual=float(native.prim_res), native_dual_residual=float(native.dual_res),
        objective=float(.5*x@gram@x+gradient@x), largest_eigenvalue=largest,
        maximum_projection_iterations=0, solve_seconds=float(native.solve_time),
        projection_kkt_not_used=True, linear_constraints=matrix.shape[0],
        primal_solution=x.tolist(), dual_solution=np.asarray(solution.y).tolist())
