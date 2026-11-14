"""Qualify multistream covariance, explicit finite observations and the unchanged full inverse."""
import numpy as np
from scipy import signal
from accel_upper_am_v1.model import POSITIONS,predict,fit,unpack,generate
from .model import compile_matrix_observer,generate_carrier


def direct_prediction(h,tile,size,lags,x):
    _,G,tau=unpack(x);power=np.sum(h*h,axis=(0,2));n=len(h);out=np.zeros((len(lags),4,4));counts=np.zeros(len(lags),int)
    for tag in np.unique(tile):
        m=int(sum(tile==tag));C=np.zeros((m,m,4,4));P=np.eye(m)-np.ones((m,m))/m
        for u in range(m):
            for v in range(m):
                for a in range(size):
                    for b in range(size):
                        t=(v-u)*size+b-a;R=np.zeros((4,4))
                        for k in range(max(0,-t),min(n,n-t)):R+=h[k]@h[k+t].T
                        C[u,v]+=(np.exp(4*G*np.exp(-abs(t)/(48000*tau)))*(1+2*R*R/np.outer(power,power))-1)/size**2
        C=np.einsum('ab,bcij,dc->adij',P,C,P)
        for q,lag in enumerate(lags):
            pairs=[(u,u+lag) for u in range(m) if 0<=u+lag<m]
            out[q]+=sum(C[u,v] for u,v in pairs);counts[q]+=len(pairs)
    return out/counts[:,None,None]


def known():
    L=np.array([[.18,0,0,0],[.06,.2,0,0],[-.04,.03,.16,0],[.02,-.05,.04,.14]])
    x=np.array([L[i,j] for i,j in POSITIONS]+[.023]);h=np.random.default_rng(129193).normal(size=(3,4,4))
    tile=np.repeat([0,1,2],[3,7,6]);lags=np.arange(-2,3);op=compile_matrix_observer(h,tile,3,lags)
    direct=direct_prediction(h,tile,3,lags,x);error=float(abs(predict(op,x)-direct).max());assert error<1e-12
    zero=np.r_[np.zeros(10),.023];zero_error=float(abs(predict(op,zero)-direct_prediction(h,tile,3,lags,zero)).max());assert zero_error<1e-12
    scale_error=float(abs(predict(compile_matrix_observer(h*3,tile,3,lags),x)-direct).max());assert scale_error<1e-12
    permutation=[2,0,3,1];permuted=h[:,permutation]*np.array([-1,1,-1,1])[None,:,None]
    P=np.eye(4)[permutation];G=P@(L@L.T)@P.T;LL=np.linalg.cholesky(G);xx=np.array([LL[i,j] for i,j in POSITIONS]+[.023])
    permutation_error=float(abs(predict(compile_matrix_observer(permuted,tile,3,lags),xx)-direct[:,permutation][:,:,permutation]).max());assert permutation_error<1e-12
    delayed=np.zeros((5,4,4))
    for i in range(4):delayed[i,i,i]=(-1.)**i
    independent_error=float(abs(predict(compile_matrix_observer(delayed,tile,3,lags),x)-direct_prediction(delayed,tile,3,lags,x)).max());assert independent_error<1e-12
    rejected=False
    try:compile_matrix_observer(np.zeros((3,4,4)),tile,3,lags)
    except ValueError:rejected=True
    assert rejected
    # Fixed independently designed frequency shapes; no source statistics read here.
    unit=np.zeros(8192);unit[0]=1;filters=np.array([signal.sosfilt(signal.butter(4,b,fs=48000,btype='bandpass',output='sos'),unit) for b in [[4000,8000],[8000,14000]]])
    mixture=np.array([[1,.2,0,.1],[.3,.8,-.1,0],[-.2,.1,.9,.2],[0,-.3,.2,.7]])
    delays=np.array([[0,7,3,11],[5,0,9,2],[4,8,0,13],[1,6,10,0]])
    native_h=np.zeros((8192,4,4))
    for i in range(4):
        shaped=signal.lfilter([1.,[.2,-.1,-.25,.15][i]],[1.],filters[i//2])
        for q in range(4):
            d=delays[i,q];native_h[d:,i,q]=mixture[i,q]*shaped[:8192-d]
    native_tile=np.repeat(np.arange(12),25);native=compile_matrix_observer(native_h,native_tile)
    target=predict(native,x);result,estimate,J=fit(native,target);recovery=float(abs(np.array(result['parameters'])-x).max())
    assert recovery<1e-6 and result['available'] and result['rank']==11 and result['condition']<1e8
    sequence=generate(L,.023,144000,149921);white,carrier=generate_carrier(native_h,144000,277139);output=carrier*sequence['gain']
    arrays=dict(parameters=x,L=L,small_impulse=h,small_tile=tile,small_lags=lags,small_W=op['W'],small_expected=direct,
        small_prediction=predict(op,x),independent_delayed=delayed,impulse=native_h,tile=native_tile,W=native['W'],
        native_lags=native['native_lags'],carrier_squared=native['carrier_squared_normalized'],target=target,prediction=estimate,J=J,
        carrier_white=white,carrier=carrier,output=output,**sequence)
    return dict(finite_multistream_error=error,zero_gain_error=zero_error,scale_error=scale_error,permutation_sign_error=permutation_error,
        independent_delayed_error=independent_error,zero_power_rejected=rejected,known_fit=result,known_recovery_error=recovery,
        known_generation_frames=144000,known_seed=149921,carrier_seed=277139,finite_moments_not_exact_expectations=True),arrays
