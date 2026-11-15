"""QR-only inverse-normal action retaining the full source coordinate space.

F.T = Z [R;0], [I;-R.T] = U T, so
(I+F.T F)^-1 = Z diag(T^-1 T^-T,I) Z.T.
The implementation never subtracts a nearly equal Woodbury projection.
"""
import numpy as np
from scipy import linalg
from waveform_stream_v1.householder import Householder


class NormalInverse:
    def __init__(self,x_raw,ledger,block=16):
        raw=np.asarray(x_raw)
        if raw.ndim!=2 or raw.dtype!=np.dtype('float64') or min(raw.shape)<1 or block<1:
            raise ValueError('FP64 synthesis QR array and positive block required')
        if not np.isfinite(raw).all():raise ValueError('Nonfinite synthesis QR array')
        k=min(raw.shape);n=raw.shape[1]
        self.size,self.k,self.ledger=n,k,ledger
        right=np.empty((n,k),order='F');ledger.add('correction.right_input',right)
        for first in range(0,n,block):
            last=min(first+block,n)
            buf=np.array(raw[:k,first:last].T,copy=True)
            for j in range(first,min(last,k)):buf[j-first,j+1:]=0.
            right[first:last]=buf
        self.right=Householder(right,ledger,'correction.right_QR')
        inner=np.empty((2*k,k),order='F');ledger.add('correction.inner_input',inner)
        self.right.graph_into(inner,block)
        self.inner=Householder(inner,ledger,'correction.inner_QR')
        self.T=self.inner.square_triangular()
        ledger.snapshot('correction.inverse_factors_complete')

    def apply(self,value):
        value=np.asarray(value,float)
        if value.ndim not in (1,2) or value.shape[0]!=self.size or not np.isfinite(value).all():
            raise ValueError('Finite complete source RHS required')
        coordinates=self.right.apply(value,True)
        first=linalg.solve_triangular(self.T,coordinates[:self.k],trans='T',lower=False,check_finite=False)
        coordinates[:self.k]=linalg.solve_triangular(self.T,first,lower=False,check_finite=False)
        return self.right.apply(coordinates)

    def arrays(self):
        return dict(inverse_right_raw=self.right.raw,inverse_right_tau=self.right.tau,
            inverse_inner_raw=self.inner.raw,inverse_inner_tau=self.inner.tau,inverse_inner_T=self.T)

    def info(self):
        return dict(method='orthogonal_right_basis_and_inner_QR',source_columns=self.size,retained_inner_directions=self.k,
            identity_complement_directions=self.size-self.k,explicit_full_Q=False,
            normal_equation_factorization=False,subtractive_Woodbury=False,
            right_alias=self.right.alias,inner_alias=self.inner.alias,
            full_or_real_resource_qualification=False)
