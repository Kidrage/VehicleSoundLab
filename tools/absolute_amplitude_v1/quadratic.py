"""Convex constrained amplitude QP, with an explicit projected-KKT certificate."""
import numpy as np
from scipy.linalg import cho_factor, cho_solve
from .cone import project, violation


def solve(gram, linear, initial, bound, caps, settings):
    shape = initial.shape
    largest = float(np.linalg.eigvalsh(gram)[-1])
    if largest <= 0:
        raise ValueError('No observed amplitude sensitivity')
    rho = .01*largest
    z = project(initial, bound, caps).ravel()
    dual = np.zeros_like(z)
    scale = max(1., float(abs(linear).max()))
    factored = None
    success = False
    for iteration in range(1, settings['qp_iterations']+1):
        if factored is None:
            factored = cho_factor(gram+rho*np.eye(len(z)), check_finite=False)
        x = cho_solve(factored, linear+rho*(z-dual), check_finite=False)
        previous = z.copy()
        z = project((x+dual).reshape(shape), bound, caps).ravel()
        dual += x-z
        if iteration % 25 == 0 or iteration == settings['qp_iterations']:
            gradient = gram@z-linear
            projected = project((z-gradient/largest).reshape(shape), bound, caps).ravel()
            kkt = float(abs(z-projected).max()*largest/scale)
            primal = float(abs(x-z).max())
            dual_residual = float(rho*abs(z-previous).max())
            if kkt <= settings['qp_kkt_tolerance'] and primal <= settings['qp_kkt_tolerance']:
                success = True
                break
            if primal > 10*dual_residual and rho < largest*1e3:
                rho *= 2
                dual /= 2
                factored = None
            elif dual_residual > 10*primal and rho > largest*1e-8:
                rho /= 2
                dual *= 2
                factored = None
    result = z.reshape(shape)
    return result, dict(success=success, iterations=iteration, projected_kkt=kkt,
        primal_residual=primal, dual_residual=dual_residual,
        constraint_violation=violation(result, bound, caps), largest_eigenvalue=largest,
        rho=rho, objective=float(.5*z@gram@z-linear@z))
