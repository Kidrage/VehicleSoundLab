"""Original linear constraints and one exact observation-noise Lorentz cone."""
import numpy as np
import scipy.sparse as sp
import clarabel
from joint_trust_v1.osqp_backend import linear_system
from interior_qp_v1.backend import inequalities


def certificate(matrix, residual, roughness, phase, rows, bounds, step, z, alpha, beta, settings):
    slack = bounds-rows@step
    data = residual+matrix@step
    norm = float(np.linalg.norm(data))
    objective_gradient = roughness.T@(phase+roughness@step)
    stationarity = float(abs(objective_gradient+rows.T@z-matrix.T@beta).max())
    primal = float(max(0., -slack.min(), norm-1.))
    dual = float(max(0., -z.min(), np.linalg.norm(beta)-alpha))
    complementarity = float(max(abs(z*slack).max(), abs(alpha+beta@data)))
    success = bool(primal <= settings['maximum_primal_violation'] and dual <= settings['maximum_primal_violation']
        and stationarity <= settings['maximum_normalized_stationarity']
        and complementarity <= settings['maximum_complementarity'])
    return dict(success=success, primal=primal, dual_cone_violation=dual,
        original_stationarity=stationarity, complementarity=complementarity,
        original_noise_norm=norm, objective=float(.5*np.linalg.norm(phase+roughness@step)**2))


def solve(matrix, residual, roughness, phase, ranged, lower, upper, settings):
    rows, bounds, _, _ = inequalities(ranged, lower, upper)
    n, m = matrix.shape[1], len(phase)
    # Orthogonal reduction preserves ||r+Jz||, including the orthogonal
    # residual. It is not a nuisance profile or truncated singular inverse.
    q, root = np.linalg.qr(np.column_stack((matrix, residual)), mode='reduced')
    error = float(np.linalg.norm(q@root-np.column_stack((matrix, residual)))/
        max(np.linalg.norm(np.column_stack((matrix, residual))), 1e-30))
    assert error < 1e-12
    tail_matrix, tail_value = root[:, :n], root[:, n]
    equality = sp.hstack((sp.csc_matrix(roughness), -sp.eye(m, format='csc')), format='csc')
    inequality = sp.hstack((rows, sp.csc_matrix((len(bounds), m))), format='csc')
    cone = sp.hstack((sp.csc_matrix(np.vstack((np.zeros((1, n)), -tail_matrix))),
        sp.csc_matrix((len(tail_value)+1, m))), format='csc')
    a = sp.vstack((equality, inequality, cone), format='csc')
    b = np.r_[-phase, bounds, 1., tail_value]
    p = sp.diags(np.r_[np.zeros(n), np.ones(m)], format='csc')
    options = clarabel.DefaultSettings()
    options.verbose = False
    options.max_iter = settings['ipm_max_iterations']
    options.max_threads = settings['ipm_max_threads']
    options.tol_gap_abs = options.tol_gap_rel = options.tol_feas = settings['ipm_tolerance']
    result = clarabel.DefaultSolver(p, np.zeros(n+m), a, b,
        [clarabel.ZeroConeT(m), clarabel.NonnegativeConeT(len(bounds)), clarabel.SecondOrderConeT(len(tail_value)+1)], options).solve()
    step = np.asarray(result.x[:n])
    auxiliary = np.asarray(result.x[n:])
    dual = np.asarray(result.z)
    z = dual[m:m+len(bounds)]
    alpha = float(dual[m+len(bounds)])
    compact_beta = dual[m+len(bounds)+1:]
    beta = q@compact_beta
    checked = certificate(matrix, residual, roughness, phase, rows, bounds, step, z, alpha, beta, settings)
    native = result.status == clarabel.SolverStatus.Solved
    equality_error = float(abs(phase+roughness@step-auxiliary).max())
    auxiliary_error = float(abs(auxiliary-dual[:m]).max())
    return step, dict(success=bool(checked['success'] and equality_error <= settings['maximum_primal_violation']
        and auxiliary_error <= settings['maximum_normalized_stationarity']), native_status=str(result.status),
        native_success=bool(native), acceptance_certificate='original_conic_KKT_and_lifted_equalities',
        iterations=int(result.iterations), original_certificate=checked,
        qr_reconstruction_relative_error=error, original_and_QR_noise_norm_difference=float(abs(
            np.linalg.norm(residual+matrix@step)-np.linalg.norm(tail_value+tail_matrix@step))),
        equality_error=equality_error, auxiliary_stationarity=auxiliary_error,
        original_noise_dual_alpha=alpha, compact_noise_dual_beta=compact_beta.tolist(),
        inequality_dual=z.tolist(), equality_dual=dual[:m].tolist(), auxiliary_solution=auxiliary.tolist(),
        primal_solution=step.tolist(), objective=float(.5*np.linalg.norm(phase+roughness@step)**2),
        solve_seconds=float(result.solve_time), original_linear_constraints=ranged.shape[0],
        inequalities=len(bounds), original_noise_rows=len(residual), compact_noise_rows=len(tail_value),
        native_primal_residual=float(result.r_prim), native_dual_residual=float(result.r_dual),
        truth_used=False, heldout_used=False)


def solve_region(matrix, residual, roughness, phase, region, settings):
    return solve(matrix, residual, roughness, phase, *linear_system(region), settings)


def controls(settings):
    # min .5(x-2)^2 s.t. |x|<=1 has x=1. Independent scalar result.
    rows = []
    for name, center, budget, low, high, expected in (
        ('active_noise_ball', 2., 1., -4., 4., 1.),
        ('inactive_noise_ball', .25, 1., -4., 4., .25),
        ('active_original_bound', 2., 3., -4., .5, .5)):
        step, evidence = solve(np.array([[1/budget]]), np.array([0.]), np.array([[1.]]),
            np.array([-center]), sp.eye(1, format='csc'), np.array([low]), np.array([high]), settings)
        assert evidence['success'], evidence
        assert abs(step[0]-expected) < 1e-7
        rows.append(dict(id=name, maximum_solution_error=float(abs(step[0]-expected)), **evidence))
    return dict(passed=True, analytic_scalar=rows)
