"""Known positive gain moments, finite observation and full parameter recovery before real targets."""
import numpy as np
from numpy.polynomial.hermite import hermgauss
from scipy import signal
from .model import POSITIONS,compile_observer,predict,fit,unpack,generate


def reference_prediction(h,tile,size,lags,parameters):
    L,Gamma,tau=unpack(parameters);power=np.sum(h*h,axis=0);n=len(h);out=np.zeros((len(lags),4,4));count=np.zeros(len(lags),int)
    for tag in np.unique(tile):
        m=int(sum(tile==tag));P=np.eye(m)-np.ones((m,m))/m;T=np.zeros((m,m,4,4))
        for u in range(m):
            for v in range(m):
                for a in range(size):
                    for b in range(size):
                        offset=(v-u)*size+b-a;rho=np.exp(-abs(offset)/(48000*tau));R=np.zeros((4,4))
                        for i in range(4):
                            for j in range(4):
                                R[i,j]=sum(h[k,i]*h[k+offset,j] for k in range(n) if 0<=k+offset<n)
                        T[u,v]+=(np.exp(4*Gamma*rho)*(1+2*R**2/np.outer(power,power))-1)/size**2
        centered=np.einsum('ab,bcij,dc->adij',P,T,P)
        for q,lag in enumerate(lags):
            pairs=[(u,u+lag) for u in range(m) if 0<=u+lag<m]
            out[q]+=sum(centered[u,v] for u,v in pairs);count[q]+=len(pairs)
    return out/count[:,None,None]


def known():
    L=np.array([[.18,0,0,0],[.06,.2,0,0],[-.04,.03,.16,0],[.02,-.05,.04,.14]])
    parameters=np.array([L[i,j] for i,j in POSITIONS]+[.023]);Gamma=L@L.T
    node,w=hermgauss(21);z=np.stack(np.meshgrid(node*np.sqrt(2),node*np.sqrt(2),indexing='ij'),axis=-1).reshape(-1,2);weights=np.outer(w,w).ravel()/np.pi
    errors=[]
    for i in range(4):
        for j in range(4):
            for lag in [0,480,2400]:
                cov=Gamma[i,j]*np.exp(-abs(lag)/(48000*.023));a=np.sqrt(Gamma[i,i]);u=a*z[:,0]
                v=cov/a*z[:,0]+np.sqrt(max(0.,Gamma[j,j]-cov**2/Gamma[i,i]))*z[:,1]
                gi=np.exp(u-Gamma[i,i]);gj=np.exp(v-Gamma[j,j])
                errors.extend([abs(np.dot(weights,gi*gi*gj*gj)-np.exp(4*cov)),
                               abs(np.dot(weights,gi*gj)-np.exp(cov-(Gamma[i,i]+Gamma[j,j])/2)),
                               abs(np.dot(weights,gi*gi)-1)])
    assert max(errors)<1e-12
    h=np.array([[1,.4,-.3,.5],[.2,-.1,.8,-.2]]);tile=np.repeat([0,1,2],[3,7,6]);lags=np.arange(-2,3)
    operator=compile_observer(h,tile,3,lags);expected=reference_prediction(h,tile,3,lags,parameters)
    error=float(abs(predict(operator,parameters)-expected).max());assert error<1e-12
    zero=predict(operator,np.r_[np.zeros(10),.023]);base=reference_prediction(h,tile,3,lags,np.r_[np.zeros(10),.023]);assert abs(zero-base).max()<1e-12
    # Independent bivariate Gaussian carrier quadrature, including opposite signs and rank-one cases.
    carrier_error=0.;node5,w5=hermgauss(5);z5=np.stack(np.meshgrid(node5*np.sqrt(2),node5*np.sqrt(2),indexing='ij'),axis=-1).reshape(-1,2);weight5=np.outer(w5,w5).ravel()/np.pi
    power=np.sum(h*h,axis=0)
    for i in range(4):
        for j in range(4):
            for lag in [-1,0,1]:
                R=sum(h[k,i]*h[k+lag,j] for k in range(2) if 0<=k+lag<2)
                x=np.sqrt(power[i])*z5[:,0];y=R/np.sqrt(power[i])*z5[:,0]+np.sqrt(max(0.,power[j]-R**2/power[i]))*z5[:,1]
                carrier_error=max(carrier_error,abs(np.dot(weight5,x*x*y*y)-(power[i]*power[j]+2*R**2)))
    assert carrier_error<1e-12
    # The prediction only depends on tau through rho; at zero Gamma use a positive clock to avoid undefined 0/0.
    unit=np.zeros(8192);unit[0]=1
    sos=np.array([signal.butter(4,band,fs=48000,btype='bandpass',output='sos') for band in [[4000,8000],[8000,14000]]])
    impulse=np.column_stack([signal.sosfilt(s,unit) for s in sos for ch in range(2)])
    long_tile=np.repeat(np.arange(12),25);native=compile_observer(impulse,long_tile)
    target=predict(native,parameters);result,prediction,J=fit(native,target)
    recovery=float(abs(np.array(result['parameters'])-parameters).max())
    assert recovery<1e-6 and result['available'] and result['rank']==11 and result['condition']<1e8
    sequence=generate(L,.023,384000,149921)
    carrier_white=np.random.default_rng(277139).standard_normal(384000+8192)
    carrier=np.column_stack([signal.sosfilt(s,carrier_white)[8192:] for s in sos for ch in range(2)])
    output=carrier*sequence['gain']
    arrays=dict(parameters=parameters,L=L,Gamma=Gamma,small_impulse=h,small_tile=tile,small_lags=lags,
        small_W=operator['W'],small_expected=expected,small_prediction=predict(operator,parameters),
        sos=sos,impulse=impulse,tile=long_tile,native_W=native['W'],native_lags=native['native_lags'],
        carrier_squared=native['carrier_squared_normalized'],target=target,prediction=prediction,J=J,
        carrier_white=carrier_white,carrier=carrier,output=output,**sequence)
    return dict(gain_quadrature_error=float(max(errors)),finite_observer_error=error,known_recovery_error=recovery,
                carrier_quadrature_error=float(carrier_error),known_fit=result,known_generation_frames=384000,known_seed=149921,
                finite8s_gain_squared_mean=np.mean(sequence['gain']**2,axis=0).tolist(),
                finite8s_output_power=np.mean(output**2,axis=0).tolist(),finite_moments_not_exact_expectations=True),arrays
