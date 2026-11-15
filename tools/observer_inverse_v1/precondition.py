"""Invertible right preconditioning; objective, nodes and gates stay fixed."""
import numpy as np
from scipy import linalg
from scipy.sparse.linalg import LinearOperator,lsmr
from .fit import RegularizedObserver,real_vector,complex_array


class RightMap:
    def __init__(self,system):
        op=system.observer;D=system.D.toarray();K=system.alpha*D.T@D+system.beta*np.eye(len(op.positions))
        lower=np.linalg.cholesky(K)
        self.time=linalg.solve_triangular(lower.T,np.eye(len(K)),lower=False)
        self.shape=op.shape;M,H,C=self.shape;self.size=2*M*H*C
        minus=(op.observed[:,None]-op.orders[None,:])%1024
        plus=(op.observed[:,None]+op.orders[None,:])%1024
        inverse_scale2=1/system.scale[:,0]**2
        counts=np.empty((M,H,2));n=np.arange(op.frames)
        # For a real node-hat g: observed real/imag coordinate columns are
        # s_h/s_k * (H_g(k-h)+H_g(k+h)) and i*s_h/s_k*(H_g(k-h)-H_g(k+h)).
        # H_g includes the original global demodulation and Hann normalization.
        for j in range(M):
            hat=np.interp(n,op.positions,self.time[:,j]);norms=np.zeros((H,2))
            for start in op.starts:
                phase=np.arange(start,start+4096)%1024
                cycle=np.bincount(phase,weights=op.window*hat[start:start+4096]/op.window.sum(),minlength=1024)
                transform=np.fft.fft(cycle);a,b=transform[minus],transform[plus]
                norms[:,0]+=np.sum(abs(a+b)**2*inverse_scale2[:,None],axis=0)*system.scale[:,0]**2
                norms[:,1]+=np.sum(abs(a-b)**2*inverse_scale2[:,None],axis=0)*system.scale[:,0]**2
            counts[j]=1+norms
        self.real_scale=1/np.sqrt(counts[:,:,0,None]);self.imag_scale=1/np.sqrt(counts[:,:,1,None])
        if not np.isfinite(self.time).all() or not np.isfinite(counts).all() or np.any(counts<=0):raise ValueError('Invalid preconditioner')
        self.K=K

    def apply(self,vector):
        u=complex_array(vector,self.shape)
        mixed=u.real*self.real_scale+1j*u.imag*self.imag_scale
        q=(self.time@mixed.reshape(len(u),-1)).reshape(self.shape)
        return real_vector(q)

    def transpose(self,vector):
        g=complex_array(vector,self.shape);mixed=(self.time.T@g.reshape(len(g),-1)).reshape(self.shape)
        return real_vector(mixed.real*self.real_scale+1j*mixed.imag*self.imag_scale)


def infer_preconditioned(observer,target,scale,alpha=1e-3,beta=1e-6,maxiter=4000):
    system=RegularizedObserver(observer,scale,alpha,beta);right=RightMap(system)
    operator=LinearOperator(system.shape,matvec=lambda u:system@right.apply(u),
                            rmatvec=lambda v:right.transpose(system.rmatvec(v)),dtype=float)
    b=system.rhs(target)
    result=lsmr(operator,b,atol=1e-13,btol=1e-13,conlim=1e12,maxiter=maxiter)
    x=right.apply(result[0]);residual=system@x-b;g=system.rmatvec(residual);initial=system.rmatvec(b)
    relative=float(np.linalg.norm(g)/max(np.linalg.norm(initial),1e-24));nodes=complex_array(x,observer.shape)*scale[None]
    info=dict(stop=int(result[1]),iterations=int(result[2]),residual_norm=float(result[3]),normal_residual_norm=float(result[4]),
              estimated_preconditioned_operator_norm=float(result[5]),estimated_preconditioned_condition=float(result[6]),solution_norm=float(np.linalg.norm(x)),
              objective=float(residual@residual),relative_stationarity=relative,alpha=alpha,beta=beta,
              converged=bool(result[1] in (1,2,4,5) and relative<2e-7),not_unique_physical_trajectory=True,
              equivalent_right_preconditioner=True,preconditioned_atol=1e-13,preconditioned_btol=1e-13,
              time_K_condition=float(np.linalg.cond(right.K)),coordinate_scale_extrema=[float(min(right.real_scale.min(),right.imag_scale.min())),float(max(right.real_scale.max(),right.imag_scale.max()))])
    return nodes,info,right
