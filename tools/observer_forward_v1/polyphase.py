"""Equivalent integer-cycle FFT implementation of the offline node operator.

This retains each hat, carrier, observation row and channel. It does not lower
the envelope node cadence or approximate the forward model.
"""
import numpy as np
from .operator import EnvelopeObserver


class PolyphaseObserver(EnvelopeObserver):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.support=[]
        for j,position in enumerate(self.positions):
            first=self.positions[j-1] if j else 0
            last=self.positions[j+1]+1 if j+1<len(self.positions) else self.frames
            n=np.arange(first,last);hat=np.ones(len(n))
            before=n<position;after=n>position
            if j:hat[before]=(n[before]-first)/(position-first)
            if j+1<len(self.positions):hat[after]=(last-1-n[after])/(last-1-position)
            self.support.append((first,last,n%1024,hat))

    def synthesize(self,nodes,block=1024):
        nodes=np.asarray(nodes,dtype=complex)
        if nodes.shape!=self.shape or not np.isfinite(nodes).all() or int(block)!=block or block<1:raise ValueError('Invalid nodes/block')
        audio=np.zeros((self.frames,self.channels))
        for j,(first,last,phase,hat) in enumerate(self.support):
            bins=np.zeros((513,self.channels),complex);bins[self.orders]=nodes[j]
            cycle=np.fft.irfft(bins,n=1024,axis=0)*512
            audio[first:last]+=hat[:,None]*cycle[phase]
        return audio

    def adjoint(self,rows):
        rows=np.asarray(rows,dtype=complex)
        if rows.shape!=self.output_shape or not np.isfinite(rows).all():raise ValueError('Invalid observed rows')
        wave_gradient=np.zeros((self.frames,self.channels))
        for j,start in enumerate(self.starts):
            bins=np.zeros((2049,self.channels),complex)
            bins[4*self.observed]=rows[j]*np.exp(2j*np.pi*self.observed*start/1024)[:,None]
            wave_gradient[start:start+4096]+=4096/self.window.sum()*self.window[:,None]*np.fft.irfft(bins,n=4096,axis=0)
        gradient=np.empty(self.shape,complex)
        for j,(first,last,phase,hat) in enumerate(self.support):
            cycle=np.zeros((1024,self.channels))
            np.add.at(cycle,phase,hat[:,None]*wave_gradient[first:last])
            gradient[j]=np.fft.fft(cycle,axis=0)[self.orders]
        return gradient
