"""Convert the original ranged polytope into nonnegative inequality cones."""
import numpy as np
import scipy.sparse as sp
import clarabel
from joint_trust_v1.osqp_backend import linear_system


def inequalities(matrix, lower, upper):
    high = np.flatnonzero(np.isfinite(upper))
    low = np.flatnonzero(np.isfinite(lower))
    rows = sp.vstack((matrix[high], -matrix[low]), format='csc')
    bounds = np.r_[upper[high], -lower[low]]
    return rows, bounds, high, low


def solve_polytope(gram, gradient, matrix, lower, upper, settings):
    rows, bounds, high, low = inequalities(matrix, lower, upper)
    maximum_gradient = float(abs(gradient).max())
    # Preserve the prior nonzero objective scale. A zero-gradient analytic
    # control has its optimum at zero and requires a finite scale as well.
    scale = maximum_gradient if maximum_gradient > 0 else max(float(abs(gram).max()), 1.)
    normalized = (gram+gram.T)/(2*scale)
    config = clarabel.DefaultSettings()
    config.verbose = False
    config.max_iter = settings['ipm_max_iterations']
    config.max_threads = settings['ipm_max_threads']
    config.tol_gap_abs = settings['ipm_tolerance']
    config.tol_gap_rel = settings['ipm_tolerance']
    config.tol_feas = settings['ipm_tolerance']
    problem = clarabel.DefaultSolver(sp.csc_matrix(np.triu(normalized)), gradient/scale,
        rows, bounds, [clarabel.NonnegativeConeT(len(bounds))], config)
    solution = problem.solve()
    x, z = np.asarray(solution.x), np.asarray(solution.z)
    if not np.isfinite(x).all() or not np.isfinite(z).all():
        raise ArithmeticError('Interior solver returned nonfinite primal/dual parameters')
    ranged_dual = np.zeros(matrix.shape[0])
    ranged_dual[high] += z[:len(high)]
    ranged_dual[low] -= z[len(high):]
    observed = matrix@x
    primal = float(max(0., np.max(lower-observed), np.max(observed-upper)))
    dual = float(abs(normalized@x+gradient/scale+matrix.T@ranged_dual).max())
    dual_sign = float(max(0., -z.min()))
    slack = bounds-rows@x
    complementarity = float(abs(z*slack).max())
    gap = float(z@slack)
    native_success = solution.status == clarabel.SolverStatus.Solved
    certified = bool(native_success and primal <= settings['maximum_primal_violation']
        and dual <= settings['maximum_normalized_stationarity']
        and dual_sign <= settings['maximum_primal_violation']
        and complementarity <= settings['maximum_complementarity'])
    return x, dict(success=certified, native_success=bool(native_success), status=str(solution.status),
        status_value=1 if native_success else 0, iterations=int(solution.iterations), solver_version=clarabel.__version__,
        normalized_dual_stationarity=dual, constraint_violation=primal,
        inequality_dual_sign_violation=dual_sign, maximum_complementarity=complementarity,
        normalized_duality_gap=gap, original_objective_dual_stationarity=dual*scale,
        objective_scale=scale, native_primal_residual=float(solution.r_prim),
        native_dual_residual=float(solution.r_dual), objective=float(.5*x@gram@x+gradient@x),
        maximum_projection_iterations=0, solve_seconds=float(solution.solve_time),
        external_hessian_regularization=False, linear_constraints=matrix.shape[0],
        inequality_constraints=len(bounds), primal_solution=x.tolist(),
        dual_solution=ranged_dual.tolist(), inequality_dual=z.tolist())


def solve(gram, gradient, region, settings):
    return solve_polytope(gram, gradient, *linear_system(region), settings)
