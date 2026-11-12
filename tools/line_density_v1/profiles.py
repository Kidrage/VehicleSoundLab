"""Positive common harmonic gains preserve low rows, phases and AR dimensions."""
import numpy as np


def scale(model,amount,transition):
    hz=np.arange(1,len(model['mean'])+1)*48000/1024
    u=np.clip((hz-transition[0])/(transition[1]-transition[0]),0,1)
    mask=u*u*(3-2*u)
    gain=np.sqrt(1-amount*mask)
    result={k:v.copy() for k,v in model.items()}
    result['mean']*=gain[:,None]
    result['basis']*=gain[:,None,None]
    result['root']*=gain[:,None,None]
    low=hz<=transition[0]
    for name in ('mean','basis','root'):assert np.array_equal(result[name][low],model[name][low])
    for name in ('rho','residual_rho'):assert np.array_equal(result[name],model[name])
    assert np.all(gain>0)
    return result,gain
