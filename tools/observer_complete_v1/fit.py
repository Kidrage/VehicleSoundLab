"""A NEW complete-waveform objective, not an equivalent old inverse solve.

The all-bin coverage-normalized Hann frame is an isometry. Its squared data
residual is evaluated as the identical waveform residual, including endcaps.
"""
import numpy as np
from scipy import linalg
from scipy.sparse.linalg import LinearOperator,lsmr
from observer_inverse_v1.fit import real_vector,complex_array
from observer_inverse_v1.regularizer import curvature
from observer_inverse_v1.refinement import SavedRightMap


class CompleteSystem(LinearOperator):
    def __init__(self,synthesis,scale,wave_scale,alpha=1e-3,beta=1e-6):
        self.synthesis=synthesis;self.scale=np.asarray(scale,float)
        self.wave_scale=float(wave_scale);self.alpha=float(alpha);self.beta=float(beta)
        if self.scale.shape!=(len(synthesis.orders),1) or np.any(self.scale<=0) or not np.isfinite(self.scale).all():
            raise ValueError('Invalid order scales')
        if not np.isfinite([wave_scale,alpha,beta]).all() or min(wave_scale,alpha,beta)<=0:
            raise ValueError('Invalid waveform/regularization scales')
        self.D=curvature(synthesis.positions);self.nshape=synthesis.shape
        self.nsize=2*int(np.prod(self.nshape));self.ysize=synthesis.frames*synthesis.channels
        self.dshape=(len(synthesis.positions)-2,)+synthesis.shape[1:]
        self.dsize=2*int(np.prod(self.dshape))
        super().__init__(dtype=np.dtype(float),shape=(self.ysize+self.dsize+self.nsize,self.nsize))

    def _matvec(self,x):
        q=complex_array(x,self.nshape)
        wave=self.synthesis.synthesize(q*self.scale[None])/self.wave_scale
        d=(self.D@q.reshape(len(q),-1)).reshape(self.dshape)
        return np.r_[wave.ravel(),np.sqrt(self.alpha)*real_vector(d),np.sqrt(self.beta)*x]

    def _rmatvec(self,x):
        wave=x[:self.ysize].reshape(self.synthesis.frames,self.synthesis.channels)/self.wave_scale
        d=complex_array(x[self.ysize:self.ysize+self.dsize],self.dshape)
        g=self.synthesis.adjoint(wave)*self.scale[None]
        g+=np.sqrt(self.alpha)*(self.D.T@d.reshape(len(d),-1)).reshape(self.nshape)
        return real_vector(g)+np.sqrt(self.beta)*x[-self.nsize:]

    def rhs(self,audio):
        if audio.shape!=(self.synthesis.frames,self.synthesis.channels) or not np.isfinite(audio).all():
            raise ValueError('Invalid complete target')
        return np.r_[audio.ravel()/self.wave_scale,np.zeros(self.dsize+self.nsize)]


class CompleteRight(SavedRightMap):
    def __init__(self,system):
        s=system.synthesis;D=system.D.toarray();M=len(s.positions)
        K=system.alpha*D.T@D+system.beta*np.eye(M)
        T=linalg.solve_triangular(np.linalg.cholesky(K).T,np.eye(M),lower=False)
        n=np.arange(s.frames);real=[];imag=[]
        for j in range(M):
            hat=np.interp(n,s.positions,T[:,j])
            bins=np.bincount(n%1024,weights=hat**2,minlength=1024)
            twice=np.fft.fft(bins)[(2*s.orders)%1024].real
            a=.5*(bins.sum()+twice)*(system.scale[:,0]/system.wave_scale)**2
            b=.5*(bins.sum()-twice)*(system.scale[:,0]/system.wave_scale)**2
            if min(a.min(),b.min()) < -1e-8:raise ArithmeticError('Negative waveform column norm')
            real.append(1/np.sqrt(1+np.maximum(a,0)))
            imag.append(1/np.sqrt(1+np.maximum(b,0)))
        super().__init__(s.shape,T,np.array(real)[:,:,None],np.array(imag)[:,:,None])


def infer(synthesis,audio,scale,wave_scale,alpha=1e-3,beta=1e-6,maxiter=4000):
    system=CompleteSystem(synthesis,scale,wave_scale,alpha,beta);right=CompleteRight(system)
    operator=LinearOperator(system.shape,matvec=lambda u:system@right.apply(u),
        rmatvec=lambda v:right.transpose(system.rmatvec(v)),dtype=float)
    b=system.rhs(audio)
    result=lsmr(operator,b,atol=1e-11,btol=1e-11,conlim=1e12,maxiter=maxiter)
    x=right.apply(result[0]);residual=system@x-b
    g=system.rmatvec(residual);initial=system.rmatvec(b)
    stationarity=float(np.linalg.norm(g)/max(np.linalg.norm(initial),1e-24))
    info=dict(stop=int(result[1]),iterations=int(result[2]),objective=float(residual@residual),
        relative_stationarity=stationarity,converged=bool(result[1] in (1,2,4,5) and stationarity<2e-7),
        alpha=alpha,beta=beta,wave_scale=wave_scale,atol=1e-11,btol=1e-11,
        data_residual_norm=float(np.linalg.norm(residual[:system.ysize])),
        estimated_preconditioned_condition=float(result[6]),
        new_complete_objective=True,not_unique_physical_trajectory=True)
    return complex_array(x,synthesis.shape)*scale[None],info,right
