"""Original soft-L1 amplitude objective, solved by convex IRLS subproblems."""
import numpy as np
from .cone import project
from .quadratic import solve


def cost(residual, scale):
    # Rationalized expression avoids cancellation for small residuals.
    ratio = residual/scale
    return float(np.sum(residual**2/(np.sqrt(1+ratio**2)+1)))


def solve_amplitudes(design, target, initial, bound, caps, scale, settings):
    controls = project(initial, bound, caps)
    residual = design@controls.ravel()-target
    previous_cost = cost(residual, scale)
    history = []
    gradient_certificate = np.inf
    success = False
    for iteration in range(settings['irls_iterations']):
        weight = 1/np.sqrt(1+(residual/scale)**2)
        gram = design.T@(weight[:, None]*design)
        linear = design.T@(weight*target)
        candidate, qp = solve(gram, linear, controls, bound, caps, settings)
        new_residual = design@candidate.ravel()-target
        objective = cost(new_residual, scale)
        if objective > previous_cost+settings['objective_decrease_tolerance']:
            raise ArithmeticError('Convex amplitude update increased original robust objective')
        controls, residual = candidate, new_residual
        psi = residual/np.sqrt(1+(residual/scale)**2)
        gradient = design.T@psi
        largest = qp['largest_eigenvalue']
        moved = project((controls.ravel()-gradient/largest).reshape(controls.shape), bound, caps)
        gradient_certificate = float(abs(controls-moved).max()*largest/max(1., abs(linear).max()))
        history.append(dict(iteration=iteration+1, cost=objective, robust_projected_kkt=gradient_certificate, qp=qp))
        previous_cost = objective
        if qp['success'] and gradient_certificate <= settings['irls_gradient_tolerance']:
            success = True
            break
    return controls, dict(success=success, iterations=len(history), cost=previous_cost,
        robust_projected_kkt=gradient_certificate, history=history,
        normalized_projection_residual=float(np.linalg.norm(residual)/np.linalg.norm(target)))
