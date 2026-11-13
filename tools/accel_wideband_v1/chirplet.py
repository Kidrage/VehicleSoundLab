"""Original-sample nonorthogonal spectral observations; never an engine clock."""
import numpy as np
from scipy.signal import find_peaks


def transform(audio,alpha,rate=48000):
    n=len(audio);t=(np.arange(n)-n/2)/rate;tau=t+.5*alpha*t*t
    frequency=np.arange(0,8000+rate/n/2,rate/n)
    window=.5-.5*np.cos(2*np.pi*np.arange(n)/n)
    weighted=audio*window[:,None];z=np.zeros((len(frequency),2),dtype=complex)
    for start in range(0,len(frequency),64):
        f=frequency[start:start+64]
        z[start:start+len(f)]=np.exp(-2j*np.pi*f[:,None]*tau)@weighted
    return frequency,z


def inventory(frequency,z):
    power=np.sum(abs(z)**2,axis=1);logged=10*np.log10(np.maximum(power,np.finfo(float).tiny))
    df=frequency[1]-frequency[0]
    indices,props=find_peaks(logged,prominence=8,distance=max(1,round(6/df)))
    mask=(frequency>=200)&(frequency<7000);maximum=power[mask].max(initial=0)
    keep=mask[indices]&(power[indices]>=maximum*10**(-42/10));indices=indices[keep]
    denom=logged[indices-1]-2*logged[indices]+logged[indices+1]
    delta=np.divide(.5*(logged[indices-1]-logged[indices+1]),denom,out=np.zeros(len(indices)),where=denom!=0)
    return dict(bin=indices.tolist(),frequency_hz=((indices+np.clip(delta,-.5,.5))*df).tolist(),
        prominence_db=props['prominences'][keep].tolist(),counts=dict(
            low_mid=int(np.sum(frequency[indices]<2200)),high=int(np.sum(frequency[indices]>=2200))))


def relative_rate(rows,i):
    if i==0:derivative=(rows[1]['ratio']-rows[0]['ratio'])/.25
    elif i==len(rows)-1:derivative=(rows[-1]['ratio']-rows[-2]['ratio'])/.25
    else:derivative=(rows[i+1]['ratio']-rows[i-1]['ratio'])/.5
    return derivative/rows[i]['ratio']
