"""Analytic stationary AR1 covariance and finite saved-row error decomposition."""
import numpy as np


def lag_covariance(rows, lag):
    rows = np.asarray(rows)
    if rows.ndim != 2 or not np.isfinite(rows).all() or not 0 <= lag < len(rows):
        raise ValueError('Finite rows and supported nonnegative lag required')
    x = rows-rows.mean(axis=0)
    return x[lag:].T@x[:len(x)-lag]/(len(x)-lag)


def stationary(model, lag):
    b = model['basis']
    shared = (b*model['rho']**lag)@b.T
    residual = np.diag(model['residual_std']**2*model['residual_rho']**lag)
    return shared+residual, shared, residual


def groups(width):
    if width % 4: raise ValueError('Amplitude-L/R, common/relative feature layout required')
    h = width//4
    return dict(amplitude_L=np.arange(0, 2*h, 2), amplitude_R=np.arange(1, 2*h, 2),
        common_phase=np.arange(2*h, 3*h), relative_phase=np.arange(3*h, 4*h))


def assess(model, training, lags):
    x, pc, residual = (training[key] for key in ('scores', 'pc', 'residual'))
    if x.shape != residual.shape or len(x) != len(pc) or model['basis'].shape != (x.shape[1], pc.shape[1]):
        raise ValueError('Saved complete feature/PCA/residual dimensions disagree')
    shared = pc@model['basis'].T
    if not np.allclose(x, shared+residual, rtol=0, atol=2e-12):
        raise ValueError('Saved shared+residual do not reconstruct scores')
    x0 = lag_covariance(x, 0)
    scale = float(np.linalg.norm(x0))
    denom = scale if scale else 1.
    group = groups(x.shape[1])
    arrays = dict(scores=x, pc=pc, residual=residual, basis=model['basis'], rho=model['rho'],
        residual_std=model['residual_std'], residual_rho=model['residual_rho'], lags=np.array(lags))
    rows, group_rows = [], []
    for lag in lags:
        empirical = lag_covariance(x, lag)
        pp = lag_covariance(shared, lag)
        rr = lag_covariance(residual, lag)
        total, mp, mr = stationary(model, lag)
        # Global means are kept identical to the empirical score convention.
        p = shared-shared.mean(axis=0); r = residual-residual.mean(axis=0)
        cross = (p[lag:].T@r[:len(x)-lag]+r[lag:].T@p[:len(x)-lag])/(len(x)-lag)
        components = np.stack((mp-pp, mr-rr, -cross))
        difference = total-empirical
        gram = components.reshape(3, -1)@components.reshape(3, -1).T
        skew = (empirical-empirical.T)/2
        err2 = float(np.sum(difference**2))
        def rms(value): return float(np.linalg.norm(value)/denom)
        row = dict(lag_steps=lag, observed_norm_over_C0=rms(empirical), model_norm_over_C0=rms(total),
            model_error_over_C0=rms(difference), observed_skew_over_C0=rms(skew),
            skew_fraction_of_observed_error_squared=float(np.sum(skew**2)/err2) if err2 else None,
            shared_error_over_C0=rms(components[0]), residual_error_over_C0=rms(components[1]),
            omitted_cross_error_over_C0=rms(components[2]), component_signed_Gram_over_C0_squared=(gram/denom**2).tolist())
        rows.append(row)
        for name,value in (('observed',empirical), ('model',total), ('shared_observed',pp),
            ('residual_observed',rr), ('shared_residual_cross_observed',cross),
            ('error_components',components), ('signed_Gram',gram)):
            arrays[f'lag{lag}_{name}'] = value
        for left, li in group.items():
            for right, ri in group.items():
                selector = np.ix_(li, ri)
                group_rows.append(dict(lag_steps=lag, left=left, right=right,
                    observed_RMS_per_entry=float(np.linalg.norm(empirical[selector])/np.sqrt(len(li)*len(ri))),
                    model_error_RMS_per_entry=float(np.linalg.norm(difference[selector])/np.sqrt(len(li)*len(ri)))))
    trace = float(np.trace(x0))
    meta = dict(rows=len(x), features=x.shape[1], shared_components=pc.shape[1],
        empirical_C0_Frobenius=scale, empirical_feature_variance_trace=trace,
        shared_feature_variance_fraction=float(np.trace(lag_covariance(shared, 0))/trace) if trace else None,
        maximum_feature_variance_error=float(abs(np.diag(stationary(model, 0)[0]-x0)).max()),
        no_acoustic_or_perceptual_or_physical_cause_claim=True)
    return arrays, rows, group_rows, meta
