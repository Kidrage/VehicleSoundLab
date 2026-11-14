"""Fresh Gaussian states with variance-correct continuous interpolation."""
import numpy as np


def endpoints(model, count, seed):
    k = len(model['rho'])
    rho = np.r_[model['rho'],model['residual_rho']]
    noise = np.random.Generator(np.random.PCG64(seed)).standard_normal((count,len(rho)))
    state = np.empty_like(noise)
    state[0] = noise[0]
    scale = np.sqrt(1-rho*rho)
    for j in range(1,count):
        state[j] = rho*state[j-1]+scale*noise[j]
    return state,noise


def features(model, state, indices, fraction):
    k = len(model['rho'])
    rho = np.r_[model['rho'],model['residual_rho']]
    u = fraction[:,None]
    value = ((1-u)*state[indices]+u*state[indices+1])/np.sqrt((1-u)**2+u*u+2*rho*u*(1-u))
    return value[:,:k]@model['basis'].T+value[:,k:]*model['residual_std']


def independent_draws(model, normal):
    k = len(model['rho'])
    return normal[:,:k]@model['basis'].T+normal[:,k:]*model['residual_std']
