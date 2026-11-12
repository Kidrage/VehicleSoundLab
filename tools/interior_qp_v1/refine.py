"""A single certificate-guided precision correction of the identical lifted QP."""
from .square_root import ObservedQRSolver


class RefinedObservedSolver:
    def __init__(self, target, soft_scale):
        self.original = ObservedQRSolver(target, soft_scale)

    def __call__(self, gram, gradient, region, settings):
        step, coarse = self.original(gram, gradient, region, settings)
        if coarse['success']:
            coarse['precision_refinement'] = dict(attempted=False, original_tolerance=settings['ipm_tolerance'])
            return step, coarse
        assert settings['precision_refinement_attempts'] == 1
        excess = max(1., coarse['normalized_dual_stationarity']/settings['maximum_normalized_stationarity'],
            coarse['constraint_violation']/settings['maximum_primal_violation'],
            coarse['maximum_complementarity']/settings['maximum_complementarity'])
        tolerance = max(settings['precision_minimum_tolerance'],
            settings['ipm_tolerance']/(settings['precision_safety_divisor']*excess))
        refined_settings = {**settings, 'ipm_tolerance': tolerance}
        refined_step, result = self.original(gram, gradient, region, refined_settings)
        result['coarse_attempt'] = coarse
        result['precision_refinement'] = dict(attempted=True, attempts=1, original_tolerance=settings['ipm_tolerance'],
            certificate_excess_ratio=excess, safety_divisor=settings['precision_safety_divisor'],
            minimum_tolerance=settings['precision_minimum_tolerance'], refined_tolerance=tolerance,
            original_problem_and_certification_limits_unchanged=True)
        return refined_step, result
