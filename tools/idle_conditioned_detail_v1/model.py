"""Conditional band POWER parameters, not recorded trajectories or source identity."""
import numpy as np


def fit(features, power):
    reference=power.mean(axis=0)
    if np.any(reference<=0) or not np.isfinite(power).all():
        raise ValueError('Positive finite training powers required')
    design=np.column_stack((np.ones(len(features)), features))
    coef,_,rank,singular=np.linalg.lstsq(design,power/reference,rcond=None)
    k=features.shape[1]//2
    lower=coef[0]-np.hypot(coef[1:1+k],coef[1+k:]).sum(axis=0)
    return dict(reference_power=reference.tolist(),coefficients=coef.tolist(),lower_power_bound=lower.tolist(),
        positive=bool(np.all(lower>0)),rank=int(rank),condition=float(singular[0]/singular[-1]))


def assess(model,features,power):
    target=power/np.asarray(model['reference_power'])
    prediction=np.column_stack((np.ones(len(features)),features))@np.asarray(model['coefficients'])
    constant=np.asarray(model['coefficients'])[0]
    before=np.mean((target-constant)**2,axis=0);after=np.mean((target-prediction)**2,axis=0)
    corr=[]
    for j in range(power.shape[1]):
        a=target[:,j]-target[:,j].mean();b=prediction[:,j]-prediction[:,j].mean()
        denominator=np.linalg.norm(a)*np.linalg.norm(b)
        corr.append(float(a@b/denominator) if denominator>0 else None)
    return dict(constant_mse=before.tolist(),conditional_mse=after.tolist(),
        relative_mse_improvement=(1-after/before).tolist(),correlation=corr,
        minimum_observed_predicted_power=prediction.min(axis=0).tolist())


def gain(model,phasors,amount):
    if not model['positive'] or not np.isfinite(amount) or not 0<=amount<=1:
        raise ValueError('Positive power law and finite0..1amount required')
    coef=np.asarray(model['coefficients'])
    feature=np.column_stack((phasors.real,phasors.imag))
    power=1+amount*(feature@coef[1:])/coef[0]
    if not np.isfinite(power).all() or np.any(power<=0):
        raise ValueError('Nonpositive generated power; no clipping')
    return np.sqrt(power)

