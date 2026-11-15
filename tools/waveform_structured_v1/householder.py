"""Implicit full-Q applications with observed LAPACK overwrite/alias behavior."""
import numpy as np
from scipy import linalg


class Householder:
    def __init__(self,matrix,ledger,name):
        if matrix.dtype!=np.dtype('float64') or not matrix.flags.f_contiguous:
            raise ValueError('Owned FP64 Fortran matrix required')
        self.rows,self.columns=matrix.shape;self.k=min(matrix.shape)
        (raw,self.tau),self.R=linalg.qr(matrix,mode='raw',overwrite_a=True,check_finite=False)
        self.reflectors=raw[:,:self.k]
        self.alias=dict(input_and_raw_share=bool(np.shares_memory(matrix,raw)),
            raw_and_R_share=bool(np.shares_memory(raw,self.R)),input_owns_data=bool(matrix.flags.owndata))
        ledger.add(name+'.raw',raw);ledger.add(name+'.reflectors',self.reflectors)
        ledger.add(name+'.tau',self.tau);ledger.add(name+'.R',self.R)
        ledger.snapshot(name+'.factored')
        self.ormqr=linalg.get_lapack_funcs('ormqr',(self.reflectors,))

    def apply(self,value,transpose=False):
        value=np.asarray(value,float);vector=value.ndim==1
        if value.ndim not in (1,2) or value.shape[0]!=self.rows:
            raise ValueError('Householder target dimensions differ')
        rhs=value[:,None] if vector else value
        op='T' if transpose else 'N'
        _,work,flag=self.ormqr('L',op,self.reflectors,self.tau,rhs,lwork=-1)
        if flag:raise ArithmeticError(('ormqr workspace',flag))
        result,_,flag=self.ormqr('L',op,self.reflectors,self.tau,rhs,lwork=int(work[0]))
        if flag:raise ArithmeticError(('ormqr application',flag))
        return result[:,0] if vector else result
