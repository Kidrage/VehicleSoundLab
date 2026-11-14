"""Continuous empirical quantiles with analytic integer-power integrals."""
import numpy as np
from scipy.special import ndtr


def integral(table, power):
    n = len(table)
    a,b = table[:-1],table[1:]
    interior = sum(a**(power-j)*b**j for j in range(power+1))/(power+1)
    return (.5*table[0]**power+.5*table[-1]**power+interior.sum(axis=0))/n


def lookup(table, normal):
    position = np.clip(ndtr(normal)*len(table)-.5,0,len(table)-1)
    first = np.floor(position).astype(int)
    fraction = position-first
    features = np.arange(table.shape[1])
    return table[first,features]*(1-fraction)+table[np.minimum(first+1,len(table)-1),features]*fraction


def decode(model, normal, variable_phase):
    h = len(model['fixed_phase'])
    amplitude = lookup(model['amplitude'],normal[...,:2*h])
    phase = lookup(model['phase'],normal[...,2*h:]) if variable_phase else model['fixed_phase'].ravel()
    return amplitude.reshape(normal.shape[:-1]+(h,2)),np.broadcast_to(phase,amplitude.shape).reshape(normal.shape[:-1]+(h,2))
