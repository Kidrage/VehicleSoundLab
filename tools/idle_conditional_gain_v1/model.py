"""Small bounded conditional-mean fit; uncertainty remains observation-level."""
import numpy as np
from scipy.optimize import least_squares
from .forward import response,gains,global_bounds

INTERCEPTS=np.array([0,5])


def fit(prepared,target,constant=None):
    scale=abs(prepared['coefficients'][[1,2]])
    if np.any(scale<=0):raise ValueError('Undefined fixed TRAIN coefficient scale')
    active=INTERCEPTS if constant is None else np.arange(10)
    initial=np.zeros(10)
    if constant is not None:initial[INTERCEPTS]=np.asarray(constant['parameters'])[INTERCEPTS]
    low=np.full(10,-.5);high=-low;low[INTERCEPTS]=-np.log(2);high[INTERCEPTS]=np.log(2)
    trace=[]
    def expand(v):
        p=np.zeros(10);p[active]=v;return p
    def residual(v):
        p=expand(v);error=(response(prepared,p)[:,:2]-target[:,:2])/scale
        result=np.r_[error.real.ravel(),error.imag.ravel()]
        trace.append(dict(parameters=p.tolist(),squared_error=float(result@result)))
        return result
    def derivative(v):
        _,jac=response(prepared,expand(v),True);j=jac[:,:2,:][:,:,active]/scale[None,:,None]
        return np.vstack((j.real.reshape(-1,len(active)),j.imag.reshape(-1,len(active))))
    result=least_squares(residual,initial[active],jac=derivative,bounds=(low[active],high[active]),
        max_nfev=40,xtol=1e-10,ftol=1e-10,gtol=1e-10)
    p=expand(result.x);singular=np.linalg.svd(derivative(result.x),compute_uv=False)
    rank=int(np.count_nonzero(singular>np.finfo(float).eps*max(derivative(result.x).shape)*singular[0]))
    condition=float(singular[0]/singular[-1])
    available=bool(result.success and rank==len(active) and condition<=1e4 and not np.any(result.active_mask))
    g=gains(p,prepared['x'])[:,:2]
    return dict(available=available,parameters=p.tolist(),constant=bool(constant is None),success=bool(result.success),
        status=result.status,nfev=result.nfev,njev=result.njev,active_mask=result.active_mask.tolist(),
        rank=rank,condition=condition,singular_values=singular.tolist(),cost=float(2*result.cost),trace=trace,
        TRAIN_scale=scale.tolist(),center=prepared['center'].tolist(),
        native_TRAIN_gain_range=np.column_stack((g.min(axis=0),g.max(axis=0))).tolist(),
        global_circular_gain_bounds=global_bounds(p,prepared['center']).tolist(),
        latent_amplitude_variance_identified=False)


def metrics(target,prediction):
    e=prediction-target;bias=abs(e.mean(axis=0))**2;variance=np.mean(abs(e-e.mean(axis=0))**2,axis=0)
    mse=np.mean(abs(e)**2,axis=0)
    if np.any(abs(target)<=0) or np.any(abs(prediction)<=0):raise ValueError('Undefined log magnitude')
    loge=np.log(abs(prediction))-np.log(abs(target))
    return dict(complex_MSE=mse.tolist(),complex_bias_squared=bias.tolist(),complex_error_variance=variance.tolist(),
        log_magnitude_MSE=np.mean(loge**2,axis=0).tolist(),
        log_magnitude_error_variance=np.var(loge,axis=0).tolist(),
        bias_variance_identity_error=float(abs(mse-bias-variance).max()))


def uncertainty(error):
    e=np.column_stack((error[:,:2].real,error[:,:2].imag));e-=e.mean(axis=0)
    curves=[]
    for lag in range(-25,26):
        l,r=(e[:len(e)-lag or None],e[lag:]) if lag>=0 else (e[-lag:],e[:len(e)+lag])
        curves.append(l.T@r/len(l))
    return np.array(curves)
