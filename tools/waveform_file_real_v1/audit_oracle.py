"""Independent locked-target equations; NO production adapter/fitter imports."""
import numpy as np
from scipy import linalg
from observer_complete_v1.audit_oracle import full_frame,hats,curvature
from observer_frequency_v1.reduced_oracle import carrier_table
from observer_supported_v1.audit_oracle import metric
from observer_supported_v1.full_oracle import FullOracle


def profile(audio,target):
    old=metric(target,64.)
    rows,coverage=full_frame(audio)
    starts=np.arange(-3840,len(audio),256)
    keep=(starts>=0)&(starts+4096<=len(audio))
    window=.5-.5*np.cos(2*np.pi*np.arange(4096)/4096)
    supported_cover=np.zeros(len(audio))
    for start in starts[keep]: supported_cover[start:start+4096]+=window**2
    result=dict(old,rows=rows[keep]*old['amplitude'],keep=keep,full_coverage=coverage,
        time_coverage=old['amplitude']**2*supported_cover/coverage)
    return result,old


def make(audio,target,positions,orders,scale):
    result=object.__new__(FullOracle)
    result.audio,result.positions,result.orders,result.scale=audio,positions,orders,scale
    result.shape=(len(positions),len(orders),audio.shape[1])
    result.profile,old=profile(audio,target)
    result.D=curvature(positions)
    result.R=.001*result.D.T@result.D+.000001*np.eye(len(positions))
    result.wave_size=audio.size
    result.row_shape=result.profile['rows'].shape
    result.data_size=audio.size+2*int(np.prod(result.row_shape))
    return result,old


def mono_matrix(oracle):
    """Explicit ALL-bin mono matrix and two RHS, known controls only."""
    N,C=oracle.audio.shape
    M,H,_=oracle.shape
    n=2*M*H
    if n>512: raise ValueError('Known-only dense oracle must not fit real sources')
    basis=hats(oracle.positions,N)
    carriers=carrier_table(tuple(int(k) for k in oracle.orders))[np.arange(N)%1024]
    phi=np.empty((N,n))
    for m in range(M):
        for h in range(H):
            j=m*H+h
            phi[:,j]=basis[m]*carriers[:,h].real*oracle.scale[h,0]
            phi[:,M*H+j]=-basis[m]*carriers[:,h].imag*oracle.scale[h,0]
    window=.5-.5*np.cos(2*np.pi*np.arange(4096)/4096)
    endpoint=np.r_[1.,np.full(2047,np.sqrt(2.)),1.]
    rows=[]
    for start in range(0,N-4096+1,256):
        segment=phi[start:start+4096]*window[:,None]/np.sqrt(oracle.profile['full_coverage'][start:start+4096,None])
        rows.append(np.fft.rfft(segment,axis=0)*endpoint[:,None]/64)
    rows=np.asarray(rows)*oracle.profile['amplitude']*oracle.profile['weights'][None,:,None]
    B=np.vstack((phi/oracle.profile['sigma'],rows.real.reshape(-1,n),rows.imag.reshape(-1,n)))
    tail=np.vstack((np.sqrt(.001)*linalg.block_diag(np.kron(oracle.D,np.eye(H)),np.kron(oracle.D,np.eye(H))),.001*np.eye(n)))
    target=oracle.target().reshape(-1,C)
    return B,tail,phi,target


def qr_solve(B,tail,target):
    """Unpivoted complete QR with implicit reflectors; no explicit Q or Gram."""
    A=np.array(np.vstack((B,tail)),order='F')
    rhs=np.array(np.vstack((target,np.zeros((len(tail),target.shape[1])))),order='F')
    geqrf,ormqr,trtrs=linalg.lapack.get_lapack_funcs(('geqrf','ormqr','trtrs'),(A,))
    _,_,work,info=geqrf(A,lwork=-1)
    assert info==0
    raw,tau,work,info=geqrf(A,lwork=int(work[0]),overwrite_a=True)
    assert info==0 and np.shares_memory(A,raw)
    _,work,info=ormqr('L','T',raw,tau,rhs,lwork=-1)
    assert info==0
    transformed,work,info=ormqr('L','T',raw,tau,rhs,lwork=int(work[0]),overwrite_c=True)
    assert info==0
    answer,info=trtrs(raw[:B.shape[1]],transformed[:B.shape[1]],lower=0)
    assert info==0
    return answer
