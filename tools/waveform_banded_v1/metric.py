"""Exact lower-band storage of the finite all-bin supported-Hann metric.

Hann windows of length S couple only sample pairs separated by at most S-1.
No frequency bins, time rows, small diagonals or original samples are removed.
"""
import numpy as np
from scipy import linalg
from .root import BandedRoot


class BandedMetric:
    def __init__(self,bands):
        if bands.dtype!=np.dtype('float64') or not bands.flags.f_contiguous:
            raise ValueError('FP64 Fortran lower bands required')
        self.bands=bands;self.frames=bands.shape[1];self.bandwidth=bands.shape[0]-1
        if not 0<=self.bandwidth<self.frames or not np.isfinite(bands).all():
            raise ValueError('Invalid finite band dimensions/entries')
        self.shape=(self.frames,self.frames);self.consumed=False

    def __len__(self):return self.frames

    @classmethod
    def control_from_dense(cls,matrix):
        matrix=np.asarray(matrix,float);N=len(matrix)
        if matrix.shape!=(N,N) or N>256:
            raise ValueError('Dense adapter is restricted to SMALL controls')
        bands=np.zeros((N,N),order='F')
        for d in range(N):bands[d,:N-d]=np.diag(matrix,-d)
        return cls(bands)

    def __matmul__(self,x):
        if self.consumed:raise ValueError('Metric bands have already been consumed by Cholesky')
        x=np.asarray(x,float);vector=x.ndim==1
        if x.ndim not in (1,2) or x.shape[0]!=self.frames:raise ValueError('Metric operand differs')
        columns=x[:,None] if vector else x
        sbmv=linalg.get_blas_funcs('sbmv',(self.bands,))
        result=np.column_stack([sbmv(self.bandwidth,1.,self.bands,np.array(c,copy=True),lower=1) for c in columns.T])
        return result[:,0] if vector else result

    def factor(self,ledger):
        if self.consumed:raise ValueError('Metric bands cannot be factored twice')
        ledger.add('wave_metric.input',self.bands);ledger.snapshot('metric.before_root')
        root=BandedRoot(self.bands,ledger);self.consumed=True
        return root


def finite_banded(frames,starts,window,coverage,amplitude,weights,sigma):
    N=int(frames);window,coverage,weights=(np.asarray(x,float) for x in (window,coverage,weights))
    size=len(window)
    if (N<size or size%2 or coverage.shape!=(N,) or weights.shape!=(size//2+1,)
        or np.any(coverage<=0) or np.any(weights<=0) or not amplitude>0 or not sigma>0):
        raise ValueError('Invalid finite metric dimensions/scales')
    if not all(np.isfinite(x).all() for x in (window,coverage,weights,np.asarray([amplitude,sigma]))):
        raise ValueError('Nonfinite finite metric')
    starts=np.asarray(starts)
    if starts.ndim!=1 or np.any(starts!=starts.astype(int)) or np.any(starts<0) or np.any(starts+size>N):
        raise ValueError('Only original fully supported rows are allowed')
    kernel=np.fft.irfft(weights**2,n=size)
    bands=np.zeros((size,N),order='F');bands[0]=1/sigma**2
    for start in starts.astype(int):
        gain=amplitude*window/np.sqrt(coverage[start:start+size])
        for d in range(size):
            # Same lower-triangle multiplication order as finite_gram.
            bands[d,start:start+size-d]+=gain[d:]*kernel[d]*gain[:size-d]
    return BandedMetric(bands)


def supported_banded(metric):
    f=metric.frame
    return finite_banded(f.frames,f.starts[metric.keep],f.window,f.coverage,
        metric.amplitude_scale,metric.weights,metric.wave_scale)
