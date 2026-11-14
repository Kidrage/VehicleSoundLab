"""Positive joint OU gains after Gaussian carrier filters, with a native finite observer."""
import numpy as np
from scipy import signal,optimize
from accel_upper_forward_v1.kernel import native_basis

POSITIONS=list(zip(*np.tril_indices(4)))
INITIAL=np.array([.15 if i==j else 0. for i,j in POSITIONS]+[.025])
LOWER=np.array([.001 if i==j else -.5 for i,j in POSITIONS]+[.003])
UPPER=np.array([.75 if i==j else .5 for i,j in POSITIONS]+[.2])


def unpack(parameters):
    L=np.zeros((4,4))
    for value,(i,j) in zip(parameters,POSITIONS):L[i,j]=value
    return L,L@L.T,float(parameters[-1])


def compile_observer(impulse,tile,size=480,lags=None):
    if lags is None:lags=np.arange(-5,6)
    maximum=max(int(sum(tile==tag))-1 for tag in np.unique(tile));window_lags=np.arange(-maximum,maximum+1)
    D=np.zeros((len(lags),len(window_lags)));counts=np.zeros(len(lags),int)
    for tag in np.unique(tile):
        n=int(sum(tile==tag));P=np.eye(n)-np.ones((n,n))/n;offset=np.arange(n)[None,:]-np.arange(n)[:,None]
        for column,q in enumerate(window_lags):
            T=(offset==q).astype(float);C=P@T@P.T
            for row,lag in enumerate(lags):
                left=np.arange(max(0,-lag),min(n,n-lag));right=left+lag
                D[row,column]+=C[left,right].sum()
        for row,lag in enumerate(lags):counts[row]+=max(0,n-abs(lag))
    if min(counts)<=0:raise ValueError('Unsupported lag')
    D/=counts[:,None];delta=np.arange(1-size,size);weights=(size-abs(delta))/size**2
    extent=maximum*size+size-1;native_lags=np.arange(-extent,extent+1);W=np.zeros((len(lags),len(native_lags)))
    for column,q in enumerate(window_lags):W[:,q*size+delta+extent]+=D[:,column,None]*weights[None,:]
    base=native_basis(impulse);squared=np.zeros((len(native_lags),4,4));index=native_lags-int(base['lags'][0]);valid=(index>=0)&(index<len(base['lags']))
    squared[valid]=base['second'][index[valid]]**2/np.outer(base['power'],base['power'])
    return dict(W=W,native_lags=native_lags,carrier_squared_normalized=squared,power=base['power'],counts=counts,
                window_lags=window_lags,window_to_within=D,lags=np.asarray(lags),sample_rate=48000)


def predict(operator,parameters,jacobian=False):
    L,Gamma,tau=unpack(parameters);seconds=abs(operator['native_lags'])/operator['sample_rate'];rho=np.exp(-seconds/tau)
    carrier=1+2*operator['carrier_squared_normalized'];moment=np.exp(4*rho[:,None,None]*Gamma[None,:,:])*carrier
    prediction=(operator['W']@(moment-1).reshape(len(rho),16)).reshape(-1,4,4)
    if not jacobian:return prediction
    dGamma=(operator['W']@(4*rho[:,None,None]*moment).reshape(len(rho),16)).reshape(-1,4,4)
    dtau=(operator['W']@(4*Gamma[None,:,:]*rho[:,None,None]*seconds[:,None,None]/tau**2*moment).reshape(len(rho),16)).reshape(-1,4,4)
    columns=[]
    for i,j in POSITIONS:
        dG=np.zeros((4,4));dG[i,:]+=L[:,j];dG[:,i]+=L[:,j];columns.append((dGamma*dG).ravel())
    return prediction,np.column_stack([*columns,dtau.ravel()])


def fit(operator,target):
    trace=[];cache={}
    def calculate(x):
        key=x.tobytes()
        if key not in cache:
            prediction,J=predict(operator,x,True);residual=(prediction-target).ravel();cache[key]=(prediction,J,residual)
            trace.append(dict(parameters=x.tolist(),cost=float(np.dot(residual,residual)/2)))
        return cache[key]
    result=optimize.least_squares(lambda x:calculate(x)[2],INITIAL,jac=lambda x:calculate(x)[1],bounds=(LOWER,UPPER),
        method='trf',max_nfev=60,ftol=1e-10,xtol=1e-10,gtol=1e-10)
    prediction,J,residual=calculate(result.x);singular=np.linalg.svd(J,compute_uv=False);rank=int(np.linalg.matrix_rank(J));condition=float(singular[0]/singular[-1])
    distance=np.minimum(result.x-LOWER,UPPER-result.x);bound=distance<=1e-6
    available=bool(result.success and not bound.any() and rank==11 and condition<1e8)
    return dict(parameters=result.x.tolist(),available=available,success=bool(result.success),status=int(result.status),message=result.message,
                nfev=int(result.nfev),njev=int(result.njev),rank=rank,condition=condition,bound_mask=bound.tolist(),
                cost=float(np.dot(residual,residual)/2),initial_cost=trace[0]['cost'],trace=trace),prediction,J


def generate(L,tau,frames,seed):
    rng=np.random.default_rng(seed);initial=L@rng.standard_normal(4);white=rng.standard_normal((frames,4));rho=np.exp(-1/(48000*tau))
    innovations=white@L.T*np.sqrt(-np.expm1(-2/(48000*tau)))
    latent=signal.lfilter([1.],[1.,-rho],innovations,axis=0,zi=(rho*initial)[None,:])[0]
    gain=np.exp(latent-np.diag(L@L.T)[None,:])
    return dict(initial=initial,white=white,latent=latent,gain=gain)
