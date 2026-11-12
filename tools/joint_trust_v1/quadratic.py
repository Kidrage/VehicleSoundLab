"""Inexact convex joint QP with original constraints and a projected-KKT audit."""
import numpy as np
from scipy.linalg import cho_factor, cho_solve


def solve(gram, gradient, region, settings):
    largest = float(np.linalg.eigvalsh(gram)[-1])
    rho = .01*max(largest, 1e-30)
    z = np.zeros_like(gradient)
    dual = z.copy()
    factor = None
    scale = max(1., float(abs(gradient).max()))
    maximum_projection_iterations = 0
    success = False
    for iteration in range(1, settings['qp_iterations']+1):
        if factor is None:
            factor = cho_factor(gram+rho*np.eye(len(z)), check_finite=False)
        x = cho_solve(factor, -gradient+rho*(z-dual), check_finite=False)
        previous = z.copy()
        z, projection = region.project(x+dual)
        maximum_projection_iterations = max(maximum_projection_iterations, projection['iterations'])
        if not projection['success']:
            return z, dict(success=False, iterations=iteration, reason='projection_not_certified',
                projection=projection, maximum_projection_iterations=maximum_projection_iterations)
        dual += x-z
        if iteration % 25 == 0 or iteration == settings['qp_iterations']:
            projected, certificate = region.project(z-(gram@z+gradient)/max(largest, 1e-30))
            kkt = float(abs(z-projected).max()*largest/scale)
            primal = float(abs(x-z).max())
            dual_residual = float(rho*abs(z-previous).max())
            if certificate['success'] and kkt <= settings['qp_kkt_tolerance'] and primal <= settings['qp_kkt_tolerance']:
                success = True
                break
            if primal > 10*dual_residual and rho < largest*1e3:
                rho *= 2; dual /= 2; factor = None
            elif dual_residual > 10*primal and rho > largest*1e-8:
                rho /= 2; dual *= 2; factor = None
    return z, dict(success=success, iterations=iteration, projected_kkt=kkt,
        primal_residual=primal, dual_residual=dual_residual,
        constraint_violation=region.violation(z), objective=float(.5*z@gram@z+gradient@z),
        largest_eigenvalue=largest, rho=rho, maximum_projection_iterations=maximum_projection_iterations,
        final_projection=projection, kkt_projection=certificate)
