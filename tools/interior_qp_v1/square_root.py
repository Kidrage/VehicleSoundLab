"""Lift QR least-squares factors instead of factoring ill-conditioned Gram KKT."""
import numpy as np
import scipy.sparse as sp
import clarabel
from joint_trust_v1.osqp_backend import linear_system
from .backend import inequalities


def solve_factorized(gram, gradient, matrix, lower, upper, settings, factor):
    rows, bounds, high, low = inequalities(matrix, lower, upper)
    n, residuals = len(gradient), factor.shape[0]
    maximum_gradient = float(abs(gradient).max())
    scale = maximum_gradient if maximum_gradient > 0 else max(float(abs(gram).max()), 1.)
    normalized = (gram+gram.T)/(2*scale)
    root = factor/np.sqrt(scale)
    relative_factor_error = float(np.linalg.norm(factor.T@factor-gram)/max(np.linalg.norm(gram), 1e-30))
    assert relative_factor_error < 1e-12
    # min .5||u||^2 + q'x, subject to root*x-u=0 and the SAME inequalities.
    equality = sp.hstack((sp.csc_matrix(root), -sp.eye(residuals, format='csc')), format='csc')
    inequality = sp.hstack((rows, sp.csc_matrix((len(bounds), residuals))), format='csc')
    lifted = sp.vstack((equality, inequality), format='csc')
    lifted_bounds = np.r_[np.zeros(residuals), bounds]
    p = sp.diags(np.r_[np.zeros(n), np.ones(residuals)], format='csc')
    config = clarabel.DefaultSettings()
    config.verbose = False
    config.max_iter = settings['ipm_max_iterations']
    config.max_threads = settings['ipm_max_threads']
    config.tol_gap_abs = config.tol_gap_rel = config.tol_feas = settings['ipm_tolerance']
    problem = clarabel.DefaultSolver(p, np.r_[gradient/scale, np.zeros(residuals)], lifted,
        lifted_bounds, [clarabel.ZeroConeT(residuals), clarabel.NonnegativeConeT(len(bounds))], config)
    solution = problem.solve()
    x = np.asarray(solution.x[:n])
    auxiliary = np.asarray(solution.x[n:])
    equality_dual = np.asarray(solution.z[:residuals])
    z = np.asarray(solution.z[residuals:])
    assert np.isfinite(x).all() and np.isfinite(z).all()
    ranged_dual = np.zeros(matrix.shape[0])
    ranged_dual[high] += z[:len(high)]
    ranged_dual[low] -= z[len(high):]
    observed = matrix@x
    primal = float(max(0., np.max(lower-observed), np.max(observed-upper)))
    dual = float(abs(normalized@x+gradient/scale+matrix.T@ranged_dual).max())
    dual_sign = float(max(0., -z.min()))
    complementarity = float(abs(z*(bounds-rows@x)).max())
    native_success = solution.status == clarabel.SolverStatus.Solved
    success = bool(native_success and primal <= settings['maximum_primal_violation']
        and dual <= settings['maximum_normalized_stationarity']
        and dual_sign <= settings['maximum_primal_violation']
        and complementarity <= settings['maximum_complementarity'])
    return x, dict(success=success, native_success=bool(native_success), status=str(solution.status),
        status_value=1 if native_success else 0, iterations=int(solution.iterations), solver_version=clarabel.__version__,
        normalized_dual_stationarity=dual, constraint_violation=primal,
        inequality_dual_sign_violation=dual_sign, maximum_complementarity=complementarity,
        normalized_duality_gap=float(z@(bounds-rows@x)), original_objective_dual_stationarity=dual*scale,
        objective_scale=scale, native_primal_residual=float(solution.r_prim), native_dual_residual=float(solution.r_dual),
        objective=float(.5*x@gram@x+gradient@x), solve_seconds=float(solution.solve_time),
        external_hessian_regularization=False, factor_hessian_relative_error=relative_factor_error,
        maximum_lifted_equality_error=float(abs(root@x-auxiliary).max()),
        maximum_auxiliary_stationarity=float(abs(auxiliary-equality_dual).max()),
        maximum_original_vs_factor_stationarity_difference=float(abs((normalized-root.T@root)@x).max()),
        maximum_projection_iterations=0, linear_constraints=matrix.shape[0], inequality_constraints=len(bounds),
        auxiliary_variables=residuals, primal_solution=x.tolist(), dual_solution=ranged_dual.tolist(),
        inequality_dual=z.tolist(), auxiliary_solution=auxiliary.tolist(), equality_dual=equality_dual.tolist())


def solve_control(gram, gradient, region, settings):
    values, vectors = np.linalg.eigh(gram)
    assert values.min() >= -1e-12*max(abs(values).max(), 1.)
    root = np.sqrt(np.maximum(values, 0))[:, None]*vectors.T
    return solve_factorized(gram, gradient, *linear_system(region), settings, root)


class ObservedQRSolver:
    def __init__(self, target, soft_scale):
        self.target, self.soft_scale = target, soft_scale

    def __call__(self, gram, gradient, region, settings):
        model = region.model
        predicted, phase = model.prediction(region.outer, region.controls, True)
        matrix = np.column_stack((phase, model.design(region.outer)))*region.scales[None, :]
        ratio = (predicted-self.target)/self.soft_scale
        curvature = (1+ratio**2)**(-1.5)
        assert np.array_equal(matrix.T@(curvature[:, None]*matrix), gram)
        weighted = np.sqrt(curvature)[:, None]*matrix
        root = np.linalg.qr(weighted, mode='r')
        step, result = solve_factorized(gram, gradient, *linear_system(region), settings, root)
        result['factor_source'] = 'thin_QR_of_original_observed_weighted_Jacobian'
        result['truth_used'] = result['heldout_used'] = False
        return step, result
