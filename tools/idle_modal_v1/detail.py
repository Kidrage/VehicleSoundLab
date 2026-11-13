"""Bounded native-Hz resonant spectral debt, independent of engine clock."""
import numpy as np
from scipy.optimize import nnls
from resonant_detail_v1.filters import fit as fit_filters, theory
from resonant_detail_v1.voice import render as render_filters


def fit(reference, target_power, modal_power, plan):
    bands=plan['detail_bands_hz']; local=dict(plan,bands_hz=bands)
    envelopes=[dict(coefficients=[0.]*16,enabled=False) for _ in bands]
    models=fit_filters(reference,local,envelopes)
    # Exact stationary response on a fixed two-sided grid, integrated with
    # the same half-open physical bands as the material measurement.
    hz=np.fft.fftfreq(plan['spectral_grid_frames'],1/plan['sample_rate'])
    response=[]
    for model in models:
        density,sigma=theory(model['a'],np.asarray(model['sos']),model['envelope']['coefficients'],local)
        assert abs(sigma-model['sigma']) < 1e-12
        response.append([density[(abs(hz)>=lo)&(abs(hz)<hi)].sum()*plan['sample_rate']/len(hz)
            for lo,hi in plan['bands_hz']])
    response=np.asarray(response).T
    debt=target_power-modal_power
    # Main modes have already been limited without changing their L/R or
    # relative phases. Nonnegative LS never subtracts a negative debt.
    weight=1/np.maximum(target_power[:,0],1e-15)
    powers,_=nnls(response*weight[:,None],debt[:,0]*weight)
    for model,p in zip(models,powers): model['gain']=float(np.sqrt(p))
    stereo=np.sqrt(target_power[:,1]/np.maximum(target_power[:,0],1e-30))
    for model,(lo,hi) in zip(models,bands):
        ix=plan['bands_hz'].index([lo,hi]); model['right_over_left']=float(stereo[ix])
    return models,dict(target_debt_LR=debt.tolist(),stationary_response_matrix=response.tolist(),
        predicted_power_L=(modal_power[:,0]+response@powers).tolist())


def render(models, frames, seed, plan):
    streams=render_filters(models,frames,seed,plan)
    result=np.zeros((frames,2))
    for i,model in enumerate(models):
        y=streams[:,i]*model['gain']
        result[:,0]+=y; result[:,1]+=y*model['right_over_left']
    return result
