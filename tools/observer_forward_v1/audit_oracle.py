"""Independent scalar interpolation/OSC, direct DFT and real adjoint."""
from bisect import bisect_right
import math
import numpy as np


def synthesize(nodes,positions,orders,frames):
    audio=np.empty((frames,nodes.shape[-1]))
    for n in range(frames):
        j=min(max(bisect_right(positions,n)-1,0),len(positions)-2);w=(n-positions[j])/(positions[j+1]-positions[j])
        for c in range(nodes.shape[-1]):
            terms=[]
            for h,k in enumerate(orders):
                z=nodes[j,h,c]+w*(nodes[j+1,h,c]-nodes[j,h,c]);theta=math.tau*k*n/1024
                terms.append(z.real*math.cos(theta)-z.imag*math.sin(theta))
            audio[n,c]=math.fsum(terms)
    return audio


def observe(audio,orders):
    window=np.hanning(4097)[:-1];rows=[]
    for start in range(0,len(audio)-4096+1,256):
        time=np.arange(start,start+4096)
        kernel=np.exp(-2j*np.pi*np.asarray(orders)[:,None]*time[None,:]/1024)*window[None,:]
        rows.append(np.einsum('kn,nc->kc',kernel,audio[start:start+4096],optimize=False)*2/math.fsum(window))
    return np.array(rows)


def adjoint(rows,positions,orders,observed,frames):
    window=np.hanning(4097)[:-1];g=np.zeros((frames,rows.shape[-1]))
    for m,start in enumerate(range(0,frames-4096+1,256)):
        time=np.arange(start,start+4096)
        for h,k in enumerate(observed):
            basis=np.exp(2j*np.pi*k*time/1024)
            g[start:start+4096]+=2/math.fsum(window)*window[:,None]*(basis[:,None]*rows[m,h]).real
    phase=np.exp(-2j*np.pi*np.arange(frames)[:,None]*np.asarray(orders)[None,:]/1024)
    result=np.zeros((len(positions),len(orders),rows.shape[-1]),complex)
    for j in range(len(positions)):
        values=np.zeros(len(positions));values[j]=1;hat=np.interp(np.arange(frames),positions,values)
        result[j]=np.einsum('n,nh,nc->hc',hat,phase,g,optimize=False)
    return result
