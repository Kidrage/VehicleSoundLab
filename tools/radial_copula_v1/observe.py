"""Coefficient moments and stereo/time diagnostics, distinct from acoustic power."""
import numpy as np


def powers(amplitude,root,bands):
    hz=np.arange(1,amplitude.shape[1]+1)*root
    return np.stack([np.sum(amplitude[:,(hz>=lo)&(hz<hi),c]**2,axis=1)/2
                     for lo,hi in bands for c in (0,1)],axis=1)


def describe(amplitude,phase,root,bands):
    q=powers(amplitude,root,bands)
    mean=q.mean(axis=0);centered=q-mean
    cov=centered.T@centered/len(q)
    cv=np.sqrt(np.maximum(0,np.diag(cov)))/mean
    hz=np.arange(1,amplitude.shape[1]+1)*root
    z=amplitude*np.exp(1j*phase)
    coherence=[]
    for lo,hi in bands:
        mask=(hz>=lo)&(hz<hi)
        cross=np.mean(np.sum(z[:,mask,0]*z[:,mask,1].conj(),axis=1))
        energy=np.mean(np.sum(amplitude[:,mask,:]**2,axis=1),axis=0)
        coherence.append(cross/np.sqrt(energy.prod()) if energy.prod()>0 else 0j)
    return dict(power=q,mean=mean,covariance=cov,CV=cv,complex_coherence=np.array(coherence))


def json_summary(d):
    return {key:(np.column_stack([value.real,value.imag]).tolist() if np.iscomplexobj(value) else value.tolist())
            for key,value in d.items() if key!='power'}


def lag_covariance(q):
    centered=q-q.mean(axis=0)
    return centered[:-1].T@centered[1:]/(len(q)-1)
