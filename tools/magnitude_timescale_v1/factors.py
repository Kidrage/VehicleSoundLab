"""Stationary scalar Gaussian AR factors, separate from magnitude and carriers."""
import numpy as np
from scipy.linalg import toeplitz,solve_toeplitz


def fit(scores,order=8):
    profiles=[];rows=[]
    for values in scores.T:
        values=values-values.mean();n=len(values)
        r=np.array([values[lag:]@values[:n-lag]/n for lag in range(order+1)])
        r/=r[0]
        coefficients=solve_toeplitz(r[:order],r[1:])
        poles=np.roots(np.r_[1.,-coefficients])
        innovation=1-float(coefficients@r[1:])
        if max(abs(poles))>=1 or innovation<=0:
            raise ValueError('Nonstationary factor; no hidden pole clamp or fallback')
        covariance=toeplitz(r[:order])
        conditional=covariance[1:,1:]-np.outer(r[1:order],r[1:order])
        cholesky=np.linalg.cholesky(conditional)
        profiles.append(dict(coefficients=coefficients,covariance=covariance,
            innovation_variance=innovation,conditional_cholesky=cholesky))
        rows.append(dict(coefficients=coefficients.tolist(),innovation_variance=innovation,
            lag1_covariance=float(r[1]),maximum_pole_radius=float(max(abs(poles))),
            covariance_condition_number=float(np.linalg.cond(covariance))))
    return profiles,rows


class Factors:
    """Own factor history; caller supplies ordinary and initialization RNGs."""
    def __init__(self,profiles,current,initial_rng):
        self.profiles=profiles
        self.history=np.zeros((len(profiles),len(profiles[0]['coefficients'])))
        self.history[:,0]=current
        for k,p in enumerate(profiles):
            if len(p['coefficients'])>1:
                self.history[k,1:]=p['covariance'][1:,0]*current[k]+p['conditional_cholesky']@initial_rng.normal(size=len(p['coefficients'])-1)

    def advance(self,innovation):
        values=np.array([p['coefficients']@self.history[k]+
            np.sqrt(p['innovation_variance'])*innovation[k] for k,p in enumerate(self.profiles)])
        self.history[:,1:]=self.history[:,:-1]
        self.history[:,0]=values
        return values


def ar1_profiles(rhos):
    return [dict(coefficients=np.array([r]),covariance=np.ones((1,1)),
        innovation_variance=1-r*r,conditional_cholesky=np.zeros((0,0))) for r in rhos]
