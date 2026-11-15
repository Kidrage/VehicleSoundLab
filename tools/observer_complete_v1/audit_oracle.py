"""Independent scalar bases and SciPy full-frame/old-observer audit formulas."""
import numpy as np
from scipy import signal


def hats(positions,frames):
    return np.array([np.interp(np.arange(frames),positions,row) for row in np.eye(len(positions))])


def synthesize(nodes,positions,orders,frames):
    n=np.arange(frames);audio=np.zeros((frames,nodes.shape[-1]))
    for h,order in enumerate(orders):
        carrier=np.exp(2j*np.pi*order*n/1024)
        for c in range(nodes.shape[-1]):
            env=np.interp(n,positions,nodes[:,h,c].real)+1j*np.interp(n,positions,nodes[:,h,c].imag)
            audio[:,c]+=(env*carrier).real
    return audio


def wave_adjoint(wave,positions,orders):
    n=np.arange(len(wave));basis=hats(positions,len(wave))
    carrier=np.exp(-2j*np.pi*n[:,None]*orders[None,:]/1024)
    product=(wave[:,None,:]*carrier[:,:,None]).reshape(len(wave),-1)
    return (basis@product).reshape(len(positions),len(orders),wave.shape[-1])


def full_frame(audio,size=4096,hop=256):
    frames=len(audio);starts=list(range(-(size-hop),frames,hop))
    w=signal.windows.hann(size,sym=False);cover=np.zeros(frames)
    for start in starts:
        first,last=max(0,start),min(frames,start+size)
        cover[first:last]+=w[first-start:last-start]**2
    assert (cover>0).all()
    padded=np.zeros(((len(starts)-1)*hop+size,audio.shape[-1]))
    padded[size-hop:size-hop+frames]=audio/np.sqrt(cover[:,None])
    _,_,z=signal.stft(padded.T,window=w,nperseg=size,noverlap=size-hop,boundary=None,padded=False)
    weights=np.r_[1.,np.full(size//2-1,np.sqrt(2.)),1.]
    return z.transpose(2,1,0)*w.sum()/np.sqrt(size)*weights[None,:,None],cover


def curvature(positions):
    D=np.zeros((len(positions)-2,len(positions)))
    for j in range(len(D)):
        left,right=np.diff(positions[j:j+3]);factor=2*256**2/(left+right)
        D[j,j:j+3]=[factor/left,-factor/left-factor/right,factor/right]
    return D


def objective_gradient(nodes,positions,scale,wave_scale,reference):
    orders=np.arange(1,nodes.shape[1]+1)
    audio=synthesize(nodes,positions,orders,len(reference))
    q=nodes/scale[None];D=curvature(positions)
    d=(D@q.reshape(len(q),-1)).reshape((len(D),)+q.shape[1:])
    residue=(audio-reference)/wave_scale
    g=wave_adjoint((audio-reference)/wave_scale**2,positions,orders)*scale[None]
    g+=.001*(D.T@d.reshape(len(D),-1)).reshape(q.shape)+.000001*q
    initial=wave_adjoint(reference/wave_scale**2,positions,orders)*scale[None]
    objective=float(np.vdot(residue,residue).real+.001*np.vdot(d,d).real+.000001*np.vdot(q,q).real)
    return objective,float(np.linalg.norm(g)/max(np.linalg.norm(initial),1e-24))
