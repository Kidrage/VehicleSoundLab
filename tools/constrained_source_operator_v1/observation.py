"""Declared FP64 finite Hann observer, with explicit real-linear adjoint.

Only supported rows are stored. Coverage includes partial edge windows, as in
the original declaration. No calibration is estimated from the input wave.
"""
import numpy as np
from scipy import fft


class Observation:
    def __init__(self,frames,weights,amplitude,sigma):
        weights=np.asarray(weights)
        if (not isinstance(frames,int) or frames<8192 or weights.shape!=(2049,)
            or np.iscomplexobj(weights) or not np.isfinite(weights).all() or np.any(weights<=0)
            or np.iscomplexobj(amplitude) or np.iscomplexobj(sigma)
            or not np.isfinite([amplitude,sigma]).all() or min(amplitude,sigma)<=0):
            raise ValueError('Complete geometry and explicit positive unchanged calibration required')
        self.frames=frames;self.weights=weights.copy();self.amplitude=float(amplitude);self.sigma=float(sigma)
        self.weights.flags.writeable=False
        self.window=.5-.5*np.cos(2*np.pi*np.arange(4096)/4096)
        self.endpoint=np.r_[1.,np.full(2047,np.sqrt(2.)),1.]
        self.coverage=self.cover(frames);self.normalizer=1/np.sqrt(self.coverage)
        self.starts=np.arange(0,frames-4096+1,256)
        target_starts=np.arange(0,frames-8192+1,256)
        self.target_slots=np.searchsorted(self.starts,target_starts+2048)
        assert np.array_equal(self.starts[self.target_slots],target_starts+2048)
        assert np.array_equal(self.coverage[2048:-2048],self.cover(frames-4096))
        self.bands=np.searchsorted([3000,6000,8000,10000,14000],np.arange(2049)*16,side='right')
        self.shape=(len(self.starts),2049,2);self.target_shape=(len(self.target_slots),2049,2)

    def cover(self,frames):
        result=np.zeros(frames)
        for start in range(-3840,frames,256):
            lo,hi=max(0,start),min(frames,start+4096)
            w=self.window[lo-start:hi-start];result[lo:hi]+=w*w
        return result

    def spectral(self,wave):
        wave=np.asarray(wave)
        if wave.shape!=(self.frames,2) or np.iscomplexobj(wave) or not np.isfinite(wave).all():raise ValueError('Complete finite real stereo wave required')
        output=np.empty(self.shape,complex)
        for j,first in enumerate(self.starts):
            # Preserve the declared pre-FFT multiply order and per-channel FFT.
            samples=wave[first:first+4096]*self.normalizer[first:first+4096,None]
            samples*=self.window[:,None]
            for c in (0,1):output[j,:,c]=np.fft.rfft(samples[:,c])*self.endpoint/64
        output*=self.amplitude
        output*=self.weights[None,:,None]
        return output

    def spectral_adjoint(self,rows):
        rows=np.asarray(rows)
        if rows.shape!=self.shape or not np.isfinite(rows).all():raise ValueError('Complete finite spectral gradient required')
        result=np.zeros((self.frames,2),np.longdouble)
        weighted=rows.astype(np.clongdouble)*np.longdouble(self.amplitude)*self.weights.astype(np.longdouble)[None,:,None]
        for j,first in enumerate(self.starts):
            for c in (0,1):
                samples=fft.irfft(weighted[j,:,c]/self.endpoint.astype(np.longdouble),n=4096)*64
                result[first:first+4096,c]+=samples*self.window.astype(np.longdouble)*self.normalizer[first:first+4096].astype(np.longdouble)
        return result

    @staticmethod
    def vector(rows):return np.r_[rows.real.ravel(),rows.imag.ravel()]

    @staticmethod
    def complex_rows(vector,shape):
        size=int(np.prod(shape));vector=np.asarray(vector)
        if vector.shape!=(2*size,) or np.iscomplexobj(vector) or not np.isfinite(vector).all():raise ValueError('Finite real spectral vector required')
        return vector[:size].reshape(shape)+1j*vector[size:].reshape(shape)

    def full(self,wave):return np.r_[wave.ravel()/self.sigma,self.vector(self.spectral(wave))]

    def full_adjoint(self,vector):
        vector=np.asarray(vector);n=2*self.frames
        if vector.shape!=(n+2*int(np.prod(self.shape)),) or np.iscomplexobj(vector) or not np.isfinite(vector).all():raise ValueError('Complete real full-data vector required')
        return vector[:n].reshape(self.frames,2)/self.sigma+self.spectral_adjoint(self.complex_rows(vector[n:],self.shape))

    def target(self,wave):
        rows=self.spectral(wave)[self.target_slots]
        return (wave[2048:-2048].ravel()/self.sigma,)+tuple(self.vector(rows[:,self.bands==g]) for g in range(6))

    def target_adjoint(self,groups):
        if len(groups)!=7:raise ValueError('Original target waveform and all six bands required')
        wave=np.asarray(groups[0]);frames=self.frames-4096
        if wave.shape!=(frames*2,) or np.iscomplexobj(wave) or not np.isfinite(wave).all():raise ValueError('Real target wave gradient required')
        result=np.zeros((self.frames,2),np.longdouble);result[2048:-2048]=wave.reshape(frames,2)/self.sigma
        rows=np.zeros(self.shape,complex)
        for g in range(6):
            selected=np.flatnonzero(self.bands==g)
            value=self.complex_rows(groups[g+1],(len(self.target_slots),len(selected),2))
            rows[self.target_slots[:,None],selected[None,:]]=value
        return result+self.spectral_adjoint(rows)
