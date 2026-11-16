"""Complete stereo actions on shared mono column blocks, without dense global A."""
import numpy as np
from .geometry import Geometry
from .compiler import Compiler
from constrained_source_operator_v1.prior import Prior


class Accumulator:
    def __init__(self,shape):self.value=np.zeros(shape);self.error=np.zeros(shape)
    def add(self,ids,part):
        old=self.value[ids];new=old+part
        self.error[ids]+=np.where(abs(old)>=abs(part),(old-new)+part,(part-new)+old)
        self.value[ids]=new
    def result(self):return self.value+self.error


class Operator:
    schema='vsl.shared-rounded-source-observation/1'
    def __init__(self,*args,cache_bytes=64*1024**2,column_batch=32):
        self.g=Geometry(*args);self.compiler=Compiler(self.g,cache_bytes=cache_bytes,column_batch=column_batch)
        self.prior=Prior(self.g);self.size=self.g.size

    def source(self,x):
        coeff=self.g.coefficients(x);wave=np.empty((self.g.frames,2))
        for first in range(0,self.g.frames,256):
            last=min(first+256,self.g.frames);ids,matrix=self.compiler.wave(first,last)
            wave[first:last]=matrix@coeff[ids]
        return wave

    def full_forward(self,x):
        coeff=self.g.coefficients(x);wave=np.empty((self.g.frames,2));rows=np.empty(self.g.row_shape,complex)
        for first in range(0,self.g.frames,256):
            last=min(first+256,self.g.frames);ids,matrix=self.compiler.wave(first,last)
            wave[first:last]=(matrix/self.g.sigma)@coeff[ids]
        for index in range(len(self.g.starts)):
            ids,matrix=self.compiler.spectral(index);part=matrix@coeff[ids]
            rows[index]=part[:2049]+1j*part[2049:]
        return np.r_[wave.ravel(),rows.real.ravel(),rows.imag.ravel()]

    def full_adjoint(self,vector):
        g=self.g;vector=np.asarray(vector)
        if vector.shape!=(g.full_rows,) or np.iscomplexobj(vector) or not np.isfinite(vector).all():raise ValueError('Full finite real data vector required')
        nw=g.frames*2;nz=int(np.prod(g.row_shape));wave=vector[:nw].reshape(g.frames,2)
        real=vector[nw:nw+nz].reshape(g.row_shape);imag=vector[nw+nz:].reshape(g.row_shape)
        out=Accumulator((g.mono_size,2))
        for first in range(0,g.frames,256):
            last=min(first+256,g.frames);ids,matrix=self.compiler.wave(first,last);out.add(ids,(matrix/g.sigma).T@wave[first:last])
        for index in range(len(g.starts)):
            ids,matrix=self.compiler.spectral(index);out.add(ids,matrix.T@np.vstack((real[index],imag[index])))
        return g.coefficient_vector(out.result())

    def target_forward(self,x):
        # Reuse the SAME compiled rows; no second analysis or source clock.
        g=self.g;coeff=g.coefficients(x);wave=np.empty((g.frames-4096,2))
        for first in range(2048,g.frames-2048,256):
            last=min(first+256,g.frames-2048);ids,matrix=self.compiler.wave(first,last)
            wave[first-2048:last-2048]=(matrix/g.sigma)@coeff[ids]
        rows=np.empty((len(g.target_slots),2049,2),complex)
        for target_index,index in enumerate(g.target_slots):
            ids,matrix=self.compiler.spectral(int(index));part=matrix@coeff[ids]
            rows[target_index]=part[:2049]+1j*part[2049:]
        return (wave.ravel(),)+tuple(np.r_[rows[:,g.bands==b].real.ravel(),rows[:,g.bands==b].imag.ravel()] for b in range(6))

    def target_adjoint(self,groups):
        g=self.g
        if len(groups)!=7:raise ValueError('Original waveform plus six complete target bands required')
        wave=np.asarray(groups[0]);n=g.frames-4096
        if wave.shape!=(n*2,) or np.iscomplexobj(wave) or not np.isfinite(wave).all():raise ValueError('Complete real target gradient required')
        fullwave=np.zeros((g.frames,2));fullwave[2048:-2048]=wave.reshape(n,2)
        rows=np.zeros(g.row_shape,complex)
        for b in range(6):
            selected=np.flatnonzero(g.bands==b);shape=(len(g.target_slots),len(selected),2);half=int(np.prod(shape))
            part=np.asarray(groups[b+1])
            if part.shape!=(2*half,) or np.iscomplexobj(part) or not np.isfinite(part).all():raise ValueError('Complete real band gradient required')
            rows[g.target_slots[:,None],selected[None,:]]=part[:half].reshape(shape)+1j*part[half:].reshape(shape)
        out=Accumulator((g.mono_size,2))
        for first in range(2048,g.frames-2048,256):
            last=min(first+256,g.frames-2048);ids,matrix=self.compiler.wave(first,last)
            out.add(ids,(matrix/g.sigma).T@fullwave[first:last])
        for index in g.target_slots:
            ids,matrix=self.compiler.spectral(int(index));out.add(ids,matrix.T@np.vstack((rows[index].real,rows[index].imag)))
        return g.coefficient_vector(out.result())

    def gradient(self,x,rhs):return self.full_adjoint(self.full_forward(x)-rhs)+self.prior.apply(x)
