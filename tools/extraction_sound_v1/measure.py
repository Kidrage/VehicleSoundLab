"""All-bin stereo, direct M/S and temporal diagnostics without energy floors."""
import numpy as np
from .numerics import sensitivity


EDGES=np.array([0.,3000.,6000.,8000.,10000.,14000.,np.inf])


def statistics(power,cross,mid_side,max_lag=8):
    power,cross,mid_side=map(np.asarray,(power,cross,mid_side))
    if power.ndim!=3 or power.shape[1:]!=(6,2) or cross.shape!=power.shape[:2] or mid_side.shape!=power.shape:
        raise ValueError('Expected six-band independent stereo frame powers')
    mean=power.mean(axis=0)
    centered=power.reshape(len(power),-1)-mean.ravel()
    covariance=centered.T@centered/len(power)
    defined=mean>0
    cv=np.zeros_like(mean)
    np.divide(np.sqrt(np.diag(covariance)).reshape(6,2),mean,out=cv,where=defined)
    den=np.sqrt(mean[:,0])*np.sqrt(mean[:,1])
    stereo_defined=den>0
    coherence=np.zeros(6,complex)
    np.divide(cross.mean(axis=0),den,out=coherence,where=stereo_defined)
    lags=np.array([centered[:-lag].T@centered[lag:]/(len(power)-lag)
        for lag in range(1,min(max_lag+1,len(power)))])
    if not len(lags):lags=np.empty((0,12,12))
    return dict(mean_power=mean,power_defined=defined,CV=cv,covariance=covariance,
        lag_covariance=lags,complex_coherence=coherence,coherence_defined=stereo_defined,
        mean_mid_side=mid_side.mean(axis=0))


def measure(audio,rate,*,size=4096,hop=256,orders=None,root=None):
    audio=np.asarray(audio)
    if (audio.ndim!=2 or audio.shape[1]!=2 or np.iscomplexobj(audio) or not np.isfinite(audio).all()
            or size<4 or size%2 or not 0<hop<=size or len(audio)<size or not np.isfinite(rate) or rate<=28000):
        raise ValueError('Finite stereo, sufficient complete windows and declared sample rate required')
    starts=np.arange(0,len(audio)-size+1,hop)
    window=.5-.5*np.cos(2*np.pi*np.arange(size)/size)
    frames=audio[starts[:,None]+np.arange(size)[None,:]]*window[None,:,None]
    spectrum=np.fft.rfft(frames,axis=1)
    frequency=np.arange(size//2+1)*rate/size
    bands=np.searchsorted(EDGES[1:],frequency,side='right')
    weights=np.full(len(frequency),2/(size*np.dot(window,window)))
    weights[[0,-1]]/=2
    def gram(z,w):
        return np.einsum('wkc,wkd,k->wcd',z,z.conj(),w,optimize=True)
    full=gram(spectrum,weights)
    total_time=np.einsum('wnc,wnd->wcd',frames,frames,optimize=True)/np.dot(window,window)
    broad=[];mid_side=[]
    for b in range(6):
        mask=bands==b;z=spectrum[:,mask];w=weights[mask]
        broad.append(gram(z,w))
        ms=np.stack(((z[:,:,0]+z[:,:,1])/2,(z[:,:,0]-z[:,:,1])/2),axis=-1)
        mid_side.append(np.sum(abs(ms)**2*w[None,:,None],axis=1))
    broad=np.stack(broad,axis=1);mid_side=np.stack(mid_side,axis=1)
    power=np.diagonal(broad,axis1=-2,axis2=-1).real.copy()
    result=dict(starts=starts,frequency=frequency,bin_bands=bands,full_Gram=full,
        windowed_time_Gram=total_time,broad_Gram=broad,broad_power=power,
        broad_mid_side=mid_side,**{'broad_'+k:v for k,v in statistics(power,broad[:,:,0,1],mid_side).items()})
    result.update({'broad_'+k:v for k,v in sensitivity(spectrum,frames,weights,bands,power,broad[:,:,0,1]).items()})
    if orders is not None:
        orders=np.asarray(orders)
        if (root is None or rate!=1024*root or size%1024 or orders.ndim!=1 or not np.isfinite(orders).all()
                or np.any(orders!=orders.astype(int)) or np.any((orders<1)|(orders>511))):
            raise ValueError('Line diagnostic requires original integer1024-cycle carrier geometry')
        bins=(orders*(size//1024)).astype(int)
        line_bands=np.searchsorted(EDGES[1:],orders*root,side='right')
        line=[];line_ms=[]
        for b in range(6):
            z=spectrum[:,bins[line_bands==b]];w=np.full(z.shape[1],2/window.sum()**2)
            line.append(gram(z,w))
            ms=np.stack(((z[:,:,0]+z[:,:,1])/2,(z[:,:,0]-z[:,:,1])/2),axis=-1)
            line_ms.append(np.sum(abs(ms)**2*w[None,:,None],axis=1))
        line=np.stack(line,axis=1);line_ms=np.stack(line_ms,axis=1)
        power=np.diagonal(line,axis1=-2,axis2=-1).real.copy()
        result.update(line_Gram=line,line_power=power,line_mid_side=line_ms,
            **{'line_'+k:v for k,v in statistics(power,line[:,:,0,1],line_ms).items()})
        result.update({'line_'+k:v for k,v in sensitivity(spectrum[:,bins],frames,
            np.full(len(bins),2/window.sum()**2),line_bands,power,line[:,:,0,1]).items()})
    return result
