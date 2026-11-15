"""A new composite objective; every finite sample still has a waveform row."""
import numpy as np
from scipy import linalg
from scipy.sparse.linalg import LinearOperator,lsmr
from observer_complete_v1.fit import CompleteSystem
from observer_inverse_v1.fit import real_vector,complex_array


class SupportedSystem(CompleteSystem):
    def __init__(self,synthesis,scale,metric,alpha=1e-3,beta=1e-6):
        super().__init__(synthesis,scale,metric.wave_scale,alpha,beta)
        if (metric.frame.frames,metric.frame.channels)!=(synthesis.frames,synthesis.channels):
            raise ValueError('Waveform and supported metric dimensions differ')
        self.metric=metric
        self.wave_size=synthesis.frames*synthesis.channels
        self.spectral_size=2*int(np.prod(metric.shape))
        self.ysize=self.wave_size+self.spectral_size
        LinearOperator.__init__(self,dtype=np.dtype(float),shape=(self.ysize+self.dsize+self.nsize,self.nsize))

    def _matvec(self,x):
        q=complex_array(x,self.nshape)
        wave=self.synthesis.synthesize(q*self.scale[None])
        d=(self.D@q.reshape(len(q),-1)).reshape(self.dshape)
        return np.r_[wave.ravel()/self.wave_scale,real_vector(self.metric.forward(wave)),
            np.sqrt(self.alpha)*real_vector(d),np.sqrt(self.beta)*x]

    def _rmatvec(self,x):
        wave=x[:self.wave_size].reshape(self.synthesis.frames,self.synthesis.channels)/self.wave_scale
        rows=complex_array(x[self.wave_size:self.ysize],self.metric.shape)
        wave=wave+self.metric.adjoint(rows)
        g=self.synthesis.adjoint(wave)*self.scale[None]
        d=complex_array(x[self.ysize:self.ysize+self.dsize],self.dshape)
        g+=np.sqrt(self.alpha)*(self.D.T@d.reshape(len(d),-1)).reshape(self.nshape)
        return real_vector(g)+np.sqrt(self.beta)*x[-self.nsize:]

    def rhs(self,audio):
        if audio.shape!=(self.synthesis.frames,self.synthesis.channels) or not np.isfinite(audio).all():
            raise ValueError('Invalid composite target')
        return np.r_[audio.ravel()/self.wave_scale,real_vector(self.metric.forward(audio)),np.zeros(self.dsize+self.nsize)]


class SupportedBlockRight:
    """Approximate within-order Gram includes actual supported time coverage.

    The exact operator retains all cross-order/sideband coupling. This map does
    not change source nodes, frequency weights, regularization or the objective.
    """
    def __init__(self,system):
        s=system.synthesis;self.shape=s.shape;M,H,C=s.shape;n=np.arange(s.frames)
        hats=np.array([np.interp(n,s.positions,row) for row in np.eye(M)])
        mass=np.zeros((2,M,M));twice=np.zeros((2,H,M,M),complex)
        for i in range(M):
            for j in range(i,min(M,i+2)):
                product=hats[i]*hats[j]
                for k,weight in enumerate((np.ones(s.frames),system.metric.time_coverage)):
                    bins=np.bincount(n%1024,weights=product*weight,minlength=1024)
                    mass[k,i,j]=mass[k,j,i]=bins.sum()
                    z=np.fft.fft(bins)[(2*s.orders)%1024].conj()
                    twice[k,:,i,j]=twice[k,:,j,i]=z
        D=system.D.toarray();R=system.alpha*D.T@D+system.beta*np.eye(M)
        regularizer=linalg.block_diag(R,R);factors=[]
        for h,order in enumerate(s.orders):
            gains=system.scale[h,0]**2*np.array([1/system.wave_scale**2,system.metric.weights[4*order]**2])
            a=np.sum(gains[:,None,None]*mass,axis=0)
            b=np.sum(gains[:,None,None]*twice[:,h],axis=0)
            K=regularizer+np.block([[.5*(a+b.real),-.5*b.imag],[-.5*b.imag,.5*(a-b.real)]])
            factors.append(linalg.solve_triangular(np.linalg.cholesky(K).T,np.eye(2*M),lower=False))
        self.matrix=np.array(factors)

    def _map(self,x,transpose):
        q=complex_array(x,self.shape);M=self.shape[0]
        pair=np.concatenate((q.real,q.imag),axis=0).transpose(1,0,2)
        matrix=self.matrix.transpose(0,2,1) if transpose else self.matrix
        result=(matrix@pair).transpose(1,0,2)
        return real_vector(result[:M]+1j*result[M:])

    def apply(self,x):return self._map(x,False)

    def transpose(self,x):return self._map(x,True)


def infer_target(system,audio,maxiter=4000):
    right=SupportedBlockRight(system)
    op=LinearOperator(system.shape,matvec=lambda x:system@right.apply(x),
        rmatvec=lambda y:right.transpose(system.rmatvec(y)),dtype=float)
    b=system.rhs(audio);result=lsmr(op,b,atol=1e-11,btol=1e-11,conlim=1e12,maxiter=maxiter)
    x=right.apply(result[0]);residual=system@x-b
    stationarity=float(np.linalg.norm(system.rmatvec(residual))/max(np.linalg.norm(system.rmatvec(b)),1e-24))
    info=dict(stop=int(result[1]),iterations=int(result[2]),objective=float(residual@residual),
        relative_stationarity=stationarity,converged=bool(result[1] in (1,2,4,5) and stationarity<2e-7),
        alpha=system.alpha,beta=system.beta,atol=1e-11,btol=1e-11,
        approximate_coverage_and_carrier_preconditioner=True,estimated_preconditioned_condition=float(result[6]),
        new_composite_objective=True,not_physical_or_stochastic_source=True)
    return complex_array(x,system.nshape)*system.scale[None],info,right
