"""Transfer sole source ownership, release X before inner allocation."""
import gc
import hashlib
import weakref
import numpy as np
from waveform_stream_v1.householder import Householder
from waveform_correction_v1.native_inverse import NativeNormalInverse
from waveform_correction_v1.native_triangular import NativeUpperTriangular


class OwnedNativeInverse(NativeNormalInverse):
    def __init__(self,holder,ledger,block=16):
        if not isinstance(holder,list) or len(holder)!=1:
            raise ValueError('Transfer one owned source QR through a single-item holder')
        raw=holder.pop()
        if (not isinstance(raw,np.ndarray) or raw.dtype!=np.dtype('float64')
                or raw.ndim!=2 or min(raw.shape)<1 or not raw.flags.f_contiguous
                or not raw.flags.owndata or block<1 or not np.isfinite(raw).all()):
            raise ValueError('Sole-owned finite FP64 Fortran source QR required')
        source_ref=weakref.ref(raw)
        self.source_shape=list(raw.shape)
        self.source_sha=hashlib.sha256(memoryview(raw.ravel(order='F'))).hexdigest()
        k=min(raw.shape);n=raw.shape[1]
        self.size,self.k,self.ledger=n,k,ledger
        right=np.empty((n,k),order='F');ledger.add('correction.right_input',right)
        # Exactly the original complete R transpose, with reflector entries
        # explicitly excluded. The bounded buffer never aliases source X.
        for first in range(0,n,block):
            last=min(first+block,n)
            buf=np.array(raw[:k,first:last].T,copy=True)
            for j in range(first,min(last,k)):buf[j-first,j+1:]=0.
            right[first:last]=buf
        del buf
        self.right=Householder(right,ledger,'correction.right_QR')
        del raw
        gc.collect()
        if source_ref() is not None:
            raise RuntimeError('Source X still owned elsewhere; inner factor was NOT allocated')
        self.source_released_before_inner=True
        ledger.snapshot('owned_inverse.source_released_before_inner')
        inner=np.empty((2*k,k),order='F');ledger.add('correction.inner_input',inner)
        self.right.graph_into(inner,block)
        self.inner=Householder(inner,ledger,'correction.inner_QR')
        self.native_T=NativeUpperTriangular(self.inner.raw,k)
        ledger.snapshot('correction.inverse_factors_complete')

    def info(self):
        result=super().info()
        result.update(source_QR_released_before_inner=self.source_released_before_inner,
                      source_QR_sha256=self.source_sha,source_shape=self.source_shape,
                      ownership_contract='single-use sole-owned source holder')
        return result
