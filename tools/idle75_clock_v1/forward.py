"""Exact75gain response and finite moment derivatives; phase-estimator check separate."""
import numpy as np
from scipy.optimize import least_squares
from idle75_clock_v1.row import gain

STARTS=np.arange(12000,122401,960)
LAGS=np.array([0,2,5,10])


def cache(frequencies,z,base,amplitude,old_gain):
    t=np.arange(len(z))/48000;carrier=np.exp(2j*np.pi*t[:,None]*frequencies);carrier[:,[1,2,4]]=z
    A=np.column_stack((carrier.real,carrier.imag,np.ones(len(z))))
    w=.5-.5*np.cos(2*np.pi*np.arange(9600)/9600);unit=np.eye(27)[:,[1,14]]
    h=[];constant=[]
    for first in STARTS:
        slab=A[first:first+9600];weighted=slab*w[:,None]
        rows=np.linalg.solve(slab.T@weighted,unit).T@weighted.T
        P=rows[0]-1j*rows[1];response=P*z[first:first+9600,0].real*amplitude
        h.append(response);constant.append(P@base[first:first+9600]-response@old_gain[first:first+9600])
    return dict(h=np.array(h),constant=np.array(constant),amplitude=amplitude)


def predict(response,g,jac=None):
    windows=np.array([g[first:first+9600] for first in STARTS])
    coefficient=response['constant']+np.einsum('wt,wt->w',response['h'],windows)
    if jac is None:return coefficient
    dw=np.array([jac[first:first+9600] for first in STARTS])
    derivative=np.einsum('wt,wtp->wp',response['h'],dw)
    return coefficient,derivative


def moments(coefficient,reference,derivative=None):
    u=(coefficient/reference).real;u-=u.mean();curves=[];grad=[]
    if derivative is not None:
        d=(derivative/reference).real;d-=d.mean(axis=0)
    for lag in LAGS:
        a,b=u[:len(u)-lag or None],u[lag:];curves.append(float(a@b/len(a)))
        if derivative is not None:
            da,db=d[:len(u)-lag or None],d[lag:];grad.append(np.mean(da*b[:,None]+a[:,None]*db,axis=0))
    return (np.array(curves),np.array(grad)) if derivative is not None else np.array(curves)


def ensemble(model,streams,responses,parameters):
    values=[];derivatives=[]
    for stream,response in zip(streams,responses):
        g,jac,_=gain(model,stream,144000,parameters)
        coefficient,dc=predict(response,g,jac)
        m,dm=moments(coefficient,response['amplitude'],dc);values.append(m);derivatives.append(dm)
    return np.mean(values,axis=0),np.mean(derivatives,axis=0)


def fit(model,streams,responses,target):
    trace=[];target=np.asarray(target);scale=target[0]
    if scale<=0:raise ValueError('Positive target variance required')
    def fun(parameters):
        value,jac=ensemble(model,streams,responses,parameters);residual=(value-target)/scale
        trace.append(dict(parameters=np.asarray(parameters).tolist(),moments=value.tolist(),squared_error=float(residual@residual)))
        return residual
    result=least_squares(fun,[1.,1.],jac=lambda p:ensemble(model,streams,responses,p)[1]/scale,
        bounds=([.5,.25],[4.,3.]),max_nfev=40,xtol=1e-10,ftol=1e-10,gtol=1e-10)
    final,jac=ensemble(model,streams,responses,result.x);singular=np.linalg.svd(jac/scale,compute_uv=False)
    condition=float(singular[0]/singular[-1]);rank=int(np.linalg.matrix_rank(jac))
    available=bool(result.success and not np.any(result.active_mask) and rank==2 and condition<=1e4)
    return dict(available=available,parameters=result.x.tolist(),success=bool(result.success),status=result.status,
        nfev=result.nfev,njev=result.njev,active_mask=result.active_mask.tolist(),rank=rank,condition=condition,
        singular_values=singular.tolist(),TRAIN_target=target.tolist(),TRAIN_prediction=final.tolist(),
        TRAIN_scaled_squared_error=float(np.sum(((final-target)/scale)**2)),trace=trace)
