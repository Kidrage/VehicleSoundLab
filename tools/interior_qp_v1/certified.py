"""Observed QR interior QP with finite, independently certified primal polish."""
import numpy as np
from joint_trust_v1.osqp_backend import linear_system
from .backend import inequalities
from .square_root import ObservedQRSolver
from .active_set import polish


class CertifiedObservedSolver:
    def __init__(self, target, soft_scale):
        self.target, self.soft_scale = target, soft_scale
        self.original = ObservedQRSolver(target, soft_scale)

    def __call__(self, gram, gradient, region, settings):
        initial, coarse = self.original(gram, gradient, region, settings)
        if coarse['success']:
            coarse['active_set_polish'] = dict(attempted=False)
            return initial, coarse
        model = region.model
        predicted, derivative = model.prediction(region.outer, region.controls, True)
        matrix = np.column_stack((derivative, model.design(region.outer)))*region.scales[None, :]
        residual = predicted-self.target
        ratio = residual/self.soft_scale
        curvature = (1+ratio**2)**(-1.5)
        assert np.array_equal(matrix.T@(curvature[:, None]*matrix), gram)
        assert np.array_equal(matrix.T@(residual/np.sqrt(1+ratio**2)), gradient)
        weighted = np.sqrt(curvature)[:, None]*matrix
        rhs = -(residual/np.sqrt(1+ratio**2))/np.sqrt(curvature)
        ranged, lower, upper = linear_system(region)
        rows, bounds, high, low = inequalities(ranged, lower, upper)
        step, z, evidence = polish(gram, gradient, weighted, rhs, rows, bounds, initial, settings)
        y = np.zeros(ranged.shape[0])
        y[high] += z[:len(high)]
        y[low] -= z[len(high):]
        scale = coarse['objective_scale']
        normal = (gram+gram.T)/(2*scale)
        observed = ranged@step
        primal = float(max(0., np.max(lower-observed), np.max(observed-upper)))
        dual = float(abs(normal@step+gradient/scale+ranged.T@y).max())
        sign = float(max(0., -z.min()))
        comp = float(abs(z*(bounds-rows@step)).max())
        success = bool(evidence['success'] and primal <= settings['maximum_primal_violation']
            and dual <= settings['maximum_normalized_stationarity']
            and sign <= settings['maximum_primal_violation'] and comp <= settings['maximum_complementarity'])
        result = dict(success=success, status='SolvedActiveSet' if success else 'ActiveSetUncertified',
            status_value=1 if success else 0, native_success=success,
            external_native_status=coarse['status'], termination='independent_original_KKT_certificate',
            iterations=evidence['iterations'], solver_version=coarse['solver_version'],
            normalized_dual_stationarity=dual, constraint_violation=primal,
            inequality_dual_sign_violation=sign, maximum_complementarity=comp,
            normalized_duality_gap=float(z@(bounds-rows@step)),
            original_objective_dual_stationarity=dual*scale, objective_scale=scale,
            objective=float(.5*step@gram@step+gradient@step), external_hessian_regularization=False,
            linear_constraints=ranged.shape[0], inequality_constraints=len(bounds),
            primal_solution=step.tolist(), dual_solution=y.tolist(), inequality_dual=z.tolist(),
            coarse_attempt=coarse, active_set_polish=dict(attempted=True, **evidence),
            factor_source='original_observed_weighted_Jacobian', truth_used=False, heldout_used=False)
        return step, result
