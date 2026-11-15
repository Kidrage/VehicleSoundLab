"""One declared regularized inverse; fitted trajectories are not source audio.

J = ||F(s*q)/s - y/s||^2 + alpha||Dq||^2 + beta||q||^2.
The positive ridge makes this particular inference unique, not physical truth.
"""
import numpy as np
from scipy.sparse.linalg import LinearOperator,lsmr
from .regularizer import curvature


def real_vector(z):return np.r_[z.real.ravel(),z.imag.ravel()]


def complex_array(x,shape):
    size=int(np.prod(shape));return (x[:size]+1j*x[size:]).reshape(shape)


class RegularizedObserver(LinearOperator):
    def __init__(self,observer,scale,alpha=1e-3,beta=1e-6):
        self.observer=observer;self.scale=np.asarray(scale,float)
        if not np.array_equal(observer.orders,observer.observed) or self.scale.shape!=(len(observer.orders),1) or np.any(self.scale<=0):raise ValueError('Scale must cover identical input/output orders')
        if not np.isfinite(self.scale).all() or alpha<=0 or beta<=0:raise ValueError('Invalid regularization')
        self.alpha=float(alpha);self.beta=float(beta);self.D=curvature(observer.positions)
        self.nshape=observer.shape;self.yshape=observer.output_shape;self.dshape=(len(observer.positions)-2,)+observer.shape[1:]
        self.nsize=2*int(np.prod(self.nshape));self.ysize=2*int(np.prod(self.yshape));self.dsize=2*int(np.prod(self.dshape))
        super().__init__(dtype=np.dtype('float64'),shape=(self.ysize+self.dsize+self.nsize,self.nsize))

    def _matvec(self,x):
        q=complex_array(x,self.nshape);nodes=q*self.scale[None]
        y=self.observer.forward(nodes)/self.scale[None]
        d=(self.D@q.reshape(len(q),-1)).reshape(self.dshape)
        return np.r_[real_vector(y),np.sqrt(self.alpha)*real_vector(d),np.sqrt(self.beta)*x]

    def _rmatvec(self,x):
        y=complex_array(x[:self.ysize],self.yshape)
        d=complex_array(x[self.ysize:self.ysize+self.dsize],self.dshape)
        g=self.observer.adjoint(y/self.scale[None])*self.scale[None]
        g+=np.sqrt(self.alpha)*(self.D.T@d.reshape(len(d),-1)).reshape(self.nshape)
        return real_vector(g)+np.sqrt(self.beta)*x[-self.nsize:]

    def rhs(self,target):return np.r_[real_vector(target/self.scale[None]),np.zeros(self.dsize+self.nsize)]


def infer(observer,target,scale,alpha=1e-3,beta=1e-6,maxiter=2000):
    system=RegularizedObserver(observer,scale,alpha,beta);b=system.rhs(target)
    result=lsmr(system,b,atol=1e-11,btol=1e-11,conlim=1e12,maxiter=maxiter)
    x=result[0];residual=system@x-b;gradient=system.rmatvec(residual);initial_gradient=system.rmatvec(b)
    q=complex_array(x,observer.shape);nodes=q*scale[None]
    relative=float(np.linalg.norm(gradient)/max(np.linalg.norm(initial_gradient),1e-24))
    desc=dict(stop=int(result[1]),iterations=int(result[2]),residual_norm=float(result[3]),normal_residual_norm=float(result[4]),
              estimated_operator_norm=float(result[5]),estimated_condition=float(result[6]),solution_norm=float(result[7]),
              objective=float(residual@residual),relative_stationarity=relative,alpha=alpha,beta=beta,
              converged=bool(result[1] in (1,2,4,5) and relative<2e-7),not_unique_physical_trajectory=True)
    return nodes,desc
