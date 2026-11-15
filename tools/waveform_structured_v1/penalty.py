"""Exact node-axis penalty roots for packed real/imaginary OSC coefficients."""
import numpy as np
from scipy import linalg


class TemporalPenalty:
    def __init__(self,shape,difference,alpha=.001,beta=.000001):
        self.shape=tuple(int(x) for x in shape)
        if len(self.shape)!=3 or min(self.shape)<1:
            raise ValueError('Expected positive node/order/channel dimensions')
        M,H,C=self.shape
        difference=np.asarray(difference,float)
        if difference.ndim!=2 or difference.shape[1]!=M or not np.isfinite(difference).all():
            raise ValueError('Difference matrix does not match nodes')
        if not np.isfinite((alpha,beta)).all() or alpha<0 or beta<=0:
            raise ValueError('Invalid penalty strengths')
        self.K=alpha*difference.T@difference+beta*np.eye(M)
        self.L=np.linalg.cholesky(self.K)
        self.size=2*M*H*C

    def map(self,value,*,inverse=False,transpose=False):
        """Apply L_R, L_R^T or their inverses; RHS axes follow packed axis0."""
        value=np.asarray(value,float)
        if value.ndim not in (1,2) or value.shape[0]!=self.size:
            raise ValueError('Packed coefficient dimensions differ')
        if not np.isfinite(value).all():raise ValueError('Nonfinite coefficients')
        trailing=value.shape[1:];M,H,C=self.shape
        blocks=value.reshape((2,M,H*C)+trailing)
        result=np.empty_like(blocks)
        matrix=self.L.T if transpose else self.L
        for part in range(2):
            rhs=blocks[part].reshape(M,-1)
            mapped=(linalg.solve_triangular(matrix,rhs,lower=not transpose) if inverse else matrix@rhs)
            result[part]=mapped.reshape(blocks[part].shape)
        return result.reshape(value.shape)

    def inverse_transpose(self,value):return self.map(value,inverse=True,transpose=True)
    def inverse(self,value):return self.map(value,inverse=True)
    def root_transpose(self,value):return self.map(value,transpose=True)
    def root(self,value):return self.map(value)

    def apply(self,value):return self.root(self.root_transpose(value))
