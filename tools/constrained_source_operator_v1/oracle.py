"""Independent scalar OSC, declared-frame and small dense oracle.

Does not import the new source, observer, prior or system implementations.
"""
import numpy as np
from scipy import fft,linalg
from locked_source_guard_v1.measurement import frame
from observer_complete_v1.audit_oracle import curvature


def table(orders,extended=False):
    phase=(np.arange(1024)[:,None]*orders[None,:])%1024
    angle=phase.astype(np.longdouble)*(2*np.arccos(np.longdouble(-1))/1024)
    value=np.cos(angle)+1j*np.sin(angle)
    return value if extended else value.astype(complex)


def nodes(z,vector):
    shape=(len(z['positions']),len(z['orders']),2);half=int(np.prod(shape))
    return vector[:half].reshape(shape)+1j*vector[half:].reshape(shape)


def vector(value):return np.r_[value.real.ravel(),value.imag.ravel()]


def source(z,x):
    q=nodes(z,x)*z['scale'][None];n=np.arange(int(z['frames']));carriers=table(z['orders'])[n%1024]
    wave=np.zeros((len(n),2),np.longdouble)
    for h in range(len(z['orders'])):
        for c in (0,1):
            re=np.interp(n,z['positions'],q[:,h,c].real).astype(np.longdouble)
            im=np.interp(n,z['positions'],q[:,h,c].imag).astype(np.longdouble)
            wave[:,c]+=re*carriers[:,h].real-im*carriers[:,h].imag
    return wave.astype(float)


def source_adjoint(z,wave):
    n=np.arange(int(z['frames']));basis=np.eye(len(z['positions']));carriers=table(z['orders'],extended=True).conj()
    q=np.empty((len(basis),len(z['orders']),2),np.clongdouble)
    for m in range(len(basis)):
        hat=np.interp(n,z['positions'],basis[m]);active=hat!=0
        q[m]=carriers[n[active]%1024].T@(wave[active].astype(np.longdouble)*hat[active,None].astype(np.longdouble))
    return vector(q*z['scale'][None]).astype(float)


def spectral(z,wave):
    rows,_=frame(wave);starts=np.arange(-3840,len(wave),256)
    keep=(starts>=0)&(starts+4096<=len(wave))
    return rows[keep]*float(z['amplitude'])*z['weights'][None,:,None]


def full(z,wave):return np.r_[wave.ravel()/float(z['sigma']),vector(spectral(z,wave))]


def target(z,wave):
    wave=wave[2048:-2048];rows=spectral(z,wave)
    ids=np.searchsorted([3000,6000,8000,10000,14000],np.arange(2049)*16,side='right')
    return (wave.ravel()/float(z['sigma']),)+tuple(vector(rows[:,ids==g]) for g in range(6))


def spectral_adjoint(z,rows,frames):
    _,coverage=frame(np.zeros((frames,2)))
    endpoint=np.r_[1.,np.repeat(np.sqrt(2.),2047),1.]
    w=.5-.5*np.cos(2*np.pi*np.arange(4096)/4096)
    windows=fft.irfft(rows.astype(np.clongdouble)*np.longdouble(z['amplitude'])*z['weights'].astype(np.longdouble)[None,:,None]/endpoint.astype(np.longdouble)[None,:,None],n=4096,axis=1)*64
    result=np.zeros((frames,2),np.longdouble)
    for j,start in enumerate(range(0,frames-4096+1,256)):
        result[start:start+4096]+=windows[j]*w.astype(np.longdouble)[:,None]*(1/np.sqrt(coverage[start:start+4096])).astype(np.longdouble)[:,None]
    return result


def unpack(value,shape):
    size=int(np.prod(shape));return value[:size].reshape(shape)+1j*value[size:].reshape(shape)


def full_adjoint(z,y):
    frames=int(z['frames']);nw=frames*2;shape=(1+(frames-4096)//256,2049,2)
    wave=y[:nw].reshape(frames,2)/float(z['sigma'])+spectral_adjoint(z,unpack(y[nw:],shape),frames)
    return source_adjoint(z,wave)


def target_adjoint(z,groups):
    frames=int(z['frames'])-4096;shape=(1+(frames-4096)//256,2049,2)
    ids=np.searchsorted([3000,6000,8000,10000,14000],np.arange(2049)*16,side='right')
    rows=np.empty(shape,complex)
    for g in range(6):rows[:,ids==g]=unpack(groups[g+1],(shape[0],np.count_nonzero(ids==g),2))
    wave=np.zeros((frames+4096,2),np.longdouble)
    wave[2048:-2048]=groups[0].reshape(frames,2)/float(z['sigma'])+spectral_adjoint(z,rows,frames)
    return source_adjoint(z,wave)


def node_prior(z):
    # Use the previously independent declared rounded curvature law. A
    # different rounding law is not a valid inverse-coefficient oracle.
    p=z['positions'];d=curvature(p)
    return .001*d.T@d+1e-6*np.eye(len(p))


def prior(z,x,inverse=False):
    q=nodes(z,x);r=node_prior(z);rhs=q.reshape(len(q),-1)
    out=linalg.solve(r,rhs,assume_a='pos') if inverse else r@rhs
    return vector(out.reshape(q.shape))


def dense(z):
    frames=int(z['frames']);m,h=len(z['positions']),len(z['orders']);size=4*m*h
    if size>32:raise ValueError('Independent dense oracle is only for bounded known controls')
    n=np.arange(frames);basis=np.array([np.interp(n,z['positions'],row) for row in np.eye(m)])
    carrier=table(z['orders'])[n%1024];phi=np.zeros((frames*2,size));half=size//2
    for j in range(m):
        for k in range(h):
            for c in (0,1):
                index=(j*h+k)*2+c
                phi[c::2,index]=basis[j]*carrier[:,k].real*z['scale'][k,0]
                phi[c::2,index+half]=-basis[j]*carrier[:,k].imag*z['scale'][k,0]
    columns=[full(z,phi[:,k].reshape(frames,2)) for k in range(size)]
    b=np.column_stack(columns)
    targets=[target(z,phi[:,k].reshape(frames,2)) for k in range(size)]
    groups=tuple(np.column_stack([v[g] for v in targets]) for g in range(7))
    r=linalg.block_diag(*([np.kron(node_prior(z),np.eye(h*2))]*2))
    return phi,b,groups,r
