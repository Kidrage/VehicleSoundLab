"""Positive local spectral probabilities with a fixed reference cell."""
import numpy as np
from scipy import optimize, special


def probabilities(coefficient, design, prior):
    logits = np.log(prior) + design @ coefficient
    return np.exp(logits-special.logsumexp(logits, axis=1, keepdims=True))


def fit(feature, target):
    design = np.column_stack([np.ones(len(feature)), feature])
    prior = target.mean(axis=0)
    if np.any(prior <= 0) or not np.isfinite(target).all():
        raise ValueError('Positive finite local spectral probabilities required')
    shape = (design.shape[1], len(prior)-1)

    def objective(flat):
        coefficient = np.zeros((design.shape[1], len(prior)))
        coefficient[:, 1:] = flat.reshape(shape)
        logits = np.log(prior) + design @ coefficient
        normalizer = special.logsumexp(logits, axis=1, keepdims=True)
        predicted = np.exp(logits-normalizer)
        loss = float(np.mean(np.sum(target*(normalizer-logits), axis=1)))
        gradient = (design.T @ (predicted-target)/len(design))[:, 1:]
        return loss, gradient.ravel()

    result = optimize.minimize(objective, np.zeros(np.prod(shape)), jac=True, method='L-BFGS-B',
                               options=dict(maxiter=400, gtol=1e-8, ftol=1e-12))
    coefficient = np.zeros((design.shape[1], len(prior)))
    coefficient[:, 1:] = result.x.reshape(shape)
    loss, gradient = objective(result.x)
    return dict(prior=prior.tolist(), coefficient=coefficient.tolist(), optimizer_success=bool(result.success),
                status=str(result.message), iterations=int(result.nit), loss=loss,
                gradient_infinity=float(abs(gradient).max()), design_rank=int(np.linalg.matrix_rank(design)),
                condition=float(np.linalg.cond(design)), recorded_trajectory=False)


def predict(model, feature):
    return probabilities(np.asarray(model['coefficient']), np.column_stack([np.ones(len(feature)), feature]),
                         np.asarray(model['prior']))


def assessment(model, feature, target):
    p = predict(model, feature)
    # Targets are continuously valued frame spectra; this is mean conditional KL, not likelihood confidence.
    entropy = np.sum(special.xlogy(target, target), axis=1)
    fitted = entropy-np.sum(target*np.log(p), axis=1)
    constant = entropy-np.sum(target*np.log(model['prior']), axis=1)
    return dict(mean_KL=float(fitted.mean()), constant_mean_KL=float(constant.mean()),
                improvement=float(1-fitted.mean()/constant.mean()),
                predicted_minimum=float(p.min()), maximum_row_sum_error=float(abs(p.sum(axis=1)-1).max()))


def known():
    rng = np.random.default_rng(48271)
    phase = rng.uniform(-np.pi, np.pi, (4096, 3))
    z = np.exp(1j*phase)
    z = np.column_stack([z, z[:,1]*z[:,0].conj(), z[:,2]*z[:,0].conj(), z[:,2]*z[:,1].conj()])
    feature = np.column_stack([z.real, z.imag])
    design = np.column_stack([np.ones(len(feature)), feature])
    truth = rng.normal(0, .08, (13, 5));truth[:,0] = 0
    target = probabilities(truth, design, np.ones(5)/5)
    model = fit(feature, target)
    error = float(abs(predict(model, feature)-target).max())
    assert model['optimizer_success'] and error < 1e-5
    constant = fit(feature, np.tile([.1,.2,.3,.4], (len(feature),1)))
    constant_error = float(abs(predict(constant, feature)-[.1,.2,.3,.4]).max())
    assert constant['optimizer_success'] and constant_error < 1e-12
    return dict(positive_law_probability_error=error,constant_probability_error=constant_error,
                all_probabilities_positive=True,reference_cell_fixed=True)
