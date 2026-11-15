"""Independent scalar inverse, SciPy spectra and explicit signed Gram sums."""
import bisect
import math
import numpy as np
from scipy import signal


def scalar_phase(product,uniform,knots,cdf,low,high):
    i=min(max(bisect.bisect_right(knots,float(product))-1,0),len(knots)-2)
    a=min(max((product-knots[i])/(knots[i+1]-knots[i]),0.),1.)
    cumulative=[(1-a)*x+a*y for x,y in zip(cdf[i],cdf[i+1])]
    cumulative[0]=0.;cumulative[-1]=1.
    cell=min(bisect.bisect_right(cumulative[1:],float(uniform)),len(low)-1)
    b=(uniform-cumulative[cell])/(cumulative[cell+1]-cumulative[cell])
    return low[cell]+b*(high[cell]-low[cell])


def observe(grouped,root,bands):
    groups=grouped.shape[1];flat=grouped.reshape(len(grouped),-1)
    frequency,_,transform=signal.stft(flat.T,fs=1024*root,window='hann',nperseg=4096,
        noverlap=3840,boundary=None,padded=False)
    starts=np.arange(0,len(flat)-4096+1,256);orders=np.arange(1,289)
    total=transform.reshape(groups,2,len(frequency),len(starts)).sum(axis=0)
    z=np.moveaxis(total[:,4*orders],(0,1,2),(2,1,0))*2
    z*=np.exp(-2j*np.pi*np.remainder(starts[:,None]*orders/1024,1))[...,None]
    weights=np.full(len(frequency),4/3);weights[[0,-1]]=2/3
    result=dict(coefficients=z)
    for prefix in ('line','broad'):
        matrices=[];powers=[];crosses=[]
        for lo,hi in bands:
            mask=(orders*root>=lo)&(orders*root<hi)
            index=4*orders[mask] if prefix=='line' else np.flatnonzero((frequency>=lo)&(frequency<hi))
            scale=np.full(len(index),2.) if prefix=='line' else weights[index]
            matrices.append(np.einsum('ikt,jkt,k->tij',transform[:,index],transform[:,index].conj(),scale,optimize=False))
            powers.append((abs(total[:,index])**2*scale[None,:,None]).sum(axis=1).T)
            crosses.append((total[0,index]*total[1,index].conj()*scale[:,None]).sum(axis=0))
        result[prefix+'_Gram']=np.stack(matrices,axis=1)
        result['power' if prefix=='line' else 'broadband_power']=np.concatenate(powers,axis=1)
        result['cross' if prefix=='line' else 'broadband_cross']=np.stack(crosses,axis=1)
    result['all_frequency_Gram']=np.einsum('ikt,jkt,k->tij',transform,transform.conj(),weights,optimize=False)
    window=signal.windows.hann(4096,sym=False)
    result['time_energy_Gram']=np.array([(flat[s:s+4096]*window[:,None]).T@(flat[s:s+4096]*window[:,None])/np.dot(window,window) for s in starts])
    return result


def budget(matrix):
    mean=matrix.mean(axis=0);bands=len(mean)
    own=np.array([[[mean[b,2*i+c,2*i+c].real for c in (0,1)] for i in range(4)] for b in range(bands)])
    pairs=np.array([[[2*mean[b,2*i+c,2*j+c].real for c in (0,1)] for i in range(4) for j in range(i+1,4)] for b in range(bands)])
    total=np.array([[math.fsum(mean[b,2*i+c,2*j+c].real for i in range(4) for j in range(4)) for c in (0,1)] for b in range(bands)])
    lr=np.array([sum(mean[b,2*i,2*j+1] for i in range(4) for j in range(4)) for b in range(bands)])
    return dict(self_power=own,signed_pairs=pairs,total_power=total,complex_LR=lr)
