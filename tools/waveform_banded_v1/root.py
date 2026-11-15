"""Native band Cholesky and BLAS triangular band actions, no dense expansion."""
import numpy as np
from scipy import linalg


class BandedRoot:
    kind='exact_lower_band_cholesky'
    def __init__(self,bands,ledger):
        self.L=linalg.cholesky_banded(bands,lower=True,overwrite_ab=True,check_finite=False)
        self.bandwidth=self.L.shape[0]-1;self.frames=self.L.shape[1]
        self.shares_input=bool(np.shares_memory(self.L,bands));self.ledger=ledger
        ledger.add('wave_metric.L_banded',self.L);ledger.snapshot('metric.band_root_built')
        self.tbmv=linalg.get_blas_funcs('tbmv',(self.L,));self.tbsv=linalg.get_blas_funcs('tbsv',(self.L,))

    def _action(self,x,transpose=False,inverse=False):
        x=np.asarray(x,float);vector=x.ndim==1
        if x.ndim not in (1,2) or x.shape[0]!=self.frames or not np.isfinite(x).all():
            raise ValueError('Invalid band-root operand')
        result=np.array(x[:,None] if vector else x,order='F',copy=True)
        self.ledger.add('metric.band_action_rhs',result)
        fn=self.tbsv if inverse else self.tbmv
        for j in range(result.shape[1]):
            out=fn(self.bandwidth,self.L,result[:,j],lower=1,trans=int(transpose),overwrite_x=1)
            if not np.shares_memory(out,result):result[:,j]=out
        return result[:,0] if vector else result

    def apply(self,x):return self._action(x)
    def transpose(self,x):return self._action(x,transpose=True)
    def solve_transpose(self,x):return self._action(x,transpose=True,inverse=True)
    def solve(self,x):return self._action(x,inverse=True)
