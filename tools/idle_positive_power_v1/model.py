"""Convex exponential conditional power, fit only to explicitly supplied TRAIN samples."""
import numpy as np

GRADIENT_TOLERANCE = 1e-9


def objective(design, target, coefficient):
    eta = design @ coefficient
    with np.errstate(over='ignore', invalid='ignore'):
        q = np.exp(eta)
        loss = np.mean(np.expm1(eta)-target*eta)
    if not np.isfinite(q).all() or not np.isfinite(loss):
        return None
    gradient = design.T @ (q-target)/len(design)
    hessian = design.T @ (q[:, None]*design)/len(design)
    return float(loss), gradient, hessian, q


def bounds(coefficient):
    count = (len(coefficient)-1)//2
    radius = np.hypot(coefficient[1:1+count], coefficient[1+count:]).sum(axis=0)
    low, high = coefficient[0]-radius, coefficient[0]+radius
    safe = bool(np.all(low > np.log(np.finfo(float).tiny)) and np.all(high < np.log(np.finfo(float).max)))
    with np.errstate(over='ignore', under='ignore'):
        minimum, maximum = np.exp(low), np.exp(high)
    return dict(exponent_lower=low.tolist(), exponent_upper=high.tolist(),
                power_lower=minimum.tolist(), power_upper=maximum.tolist(), finite_normal_bounds=safe)


def fit(feature, power):
    if not np.isfinite(feature).all() or not np.isfinite(power).all() or np.any(power < 0):
        raise ValueError('Finite features and nonnegative sample powers required')
    reference = power.mean(axis=0)
    if np.any(reference <= 0):
        raise ValueError('Positive TRAIN band means required')
    design = np.column_stack((np.ones(len(feature)), feature))
    singular = np.linalg.svd(design, compute_uv=False)
    rank = int(np.linalg.matrix_rank(design))
    columns, traces, gradients, hessians = [], [], [], []
    fits = []
    for band in range(power.shape[1]):
        target = power[:, band]/reference[band]
        coefficient = np.zeros(design.shape[1]); trace = []; status = 'iteration_limit'
        for iteration in range(60):
            state = objective(design, target, coefficient)
            if state is None:
                status = 'nonfinite_state'; break
            loss, gradient, hessian, _ = state
            row = dict(iteration=iteration, loss=loss, gradient_infinity=float(abs(gradient).max()))
            if row['gradient_infinity'] <= GRADIENT_TOLERANCE:
                row['step'] = 0.; trace.append(row); status = 'converged'; break
            try:
                direction = np.linalg.solve(hessian, -gradient)
            except np.linalg.LinAlgError:
                row['step'] = 0.; trace.append(row); status = 'singular_hessian'; break
            slope = float(gradient @ direction)
            if not np.isfinite(direction).all() or slope >= 0:
                row['step'] = 0.; trace.append(row); status = 'invalid_newton_direction'; break
            step = 1.; accepted = False
            for backtrack in range(30):
                trial = objective(design, target, coefficient+step*direction)
                if trial is not None and trial[0] <= loss+1e-4*step*slope:
                    accepted = True; break
                step *= .5
            row.update(step=step if accepted else 0., backtracks=backtrack, directional_derivative=slope)
            trace.append(row)
            if not accepted:
                status = 'line_search_failed'; break
            coefficient += step*direction
        final = objective(design, target, coefficient)
        if final is None:
            raise ValueError('No finite final power law; retain failed source attempt')
        loss, gradient, hessian, _ = final
        columns.append(coefficient); traces.append(trace); gradients.append(gradient); hessians.append(hessian)
        eigenvalues = np.linalg.eigvalsh(hessian)
        fits.append(dict(status=status, loss=loss, gradient_infinity=float(abs(gradient).max()),
                         hessian_eigenvalues=eigenvalues.tolist()))
    coefficient = np.asarray(columns).T
    return dict(reference_power=reference.tolist(), coefficients=coefficient.tolist(),
                rank=rank, full_rank=bool(rank == design.shape[1]), singular_values=singular.tolist(),
                condition=float(singular[0]/singular[-1]), fits=fits, traces=traces,
                final_gradients=np.asarray(gradients).tolist(), final_hessians=np.asarray(hessians).tolist(),
                converged=all(v['status'] == 'converged' for v in fits), bounds=bounds(coefficient))


def predict(model, feature):
    coefficient = np.asarray(model['coefficients'])
    with np.errstate(over='ignore', under='ignore'):
        q = np.exp(coefficient[0]+feature @ coefficient[1:])
    if not np.isfinite(q).all() or np.any(q <= 0):
        raise ValueError('Nonrepresentable power; no clipping')
    return q


def average(values, hop=48):
    if len(values) % hop:
        raise ValueError('Whole observation blocks required')
    return values.reshape(-1, hop, values.shape[1]).mean(axis=1)


def assess(target, prediction):
    residual = target-prediction
    constant = np.ones_like(target)
    mse = np.mean(residual**2, axis=0)
    before = np.mean((target-constant)**2, axis=0)
    correlations = []
    for a, b in zip(target.T, prediction.T):
        u, v = a-a.mean(), b-b.mean()
        norm = np.linalg.norm(u)*np.linalg.norm(v)
        correlations.append(float(u@v/norm) if norm else None)
    return dict(mse=mse.tolist(), constant_mse=before.tolist(),
                improvement_over_train_constant=(1-mse/before).tolist(), correlation=correlations,
                mean_target=target.mean(axis=0).tolist(), mean_prediction=prediction.mean(axis=0).tolist(),
                mean_residual=residual.mean(axis=0).tolist(), minimum_prediction=prediction.min(axis=0).tolist())
