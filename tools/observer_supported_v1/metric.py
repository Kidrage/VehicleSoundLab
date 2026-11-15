"""Shared L/R band weights derived only from fully supported analysis rows."""
import numpy as np
from observer_complete_v1.frame import CompleteHann
from observer_frequency_v1.metric import EDGES, FLOOR_FRACTION


class SupportedMetric:
    def __init__(self, audio, root_hz):
        audio=np.asarray(audio)
        if audio.ndim!=2 or audio.shape[1] not in (1,2) or len(audio)<4096:
            raise ValueError('Supported spectrum requires >=4096 real mono/stereo samples')
        if not np.isfinite(root_hz) or root_hz<=0:
            raise ValueError('Invalid acoustic frequency scale')
        self.frame=CompleteHann(len(audio),audio.shape[1])
        self.keep=(self.frame.starts>=0)&(self.frame.starts+4096<=len(audio))
        self.full_rows=int(self.keep.sum())
        self.amplitude_scale=float(np.sqrt(len(audio)/(256*self.full_rows)))
        self.shape=(self.full_rows,2049,audio.shape[1])
        self.global_power=float(np.mean(audio**2))
        self.wave_scale=float(np.sqrt(self.global_power)) if self.global_power else 1.
        self.floor_fraction=FLOOR_FRACTION
        self.root_hz=float(root_hz)
        frequencies=np.arange(2049)*root_hz/4
        self.bands=np.searchsorted(EDGES[1:],frequencies,side='right')
        rows=self.frame.forward(audio)[self.keep]*self.amplitude_scale
        self.band_power=np.array([float(np.sum(abs(rows[:,self.bands==b])**2)/audio.size) for b in range(6)])
        self.floor_active=self.band_power<self.global_power*self.floor_fraction
        self.weights=(np.ones(2049) if not self.global_power else
            1/np.sqrt(np.maximum(self.band_power[self.bands],self.global_power*self.floor_fraction)))
        if not np.isfinite(self.weights).all() or np.any(self.weights<=0):
            raise ValueError('Invalid supported spectral weights')
        coverage=np.zeros(len(audio))
        for first,last,offset in (s for s,k in zip(self.frame.support,self.keep) if k):
            coverage[first:last]+=self.frame.window[offset:offset+last-first]**2
        self.time_coverage=self.amplitude_scale**2*coverage/self.frame.coverage

    def forward(self,audio):
        return self.frame.forward(audio)[self.keep]*self.amplitude_scale*self.weights[None,:,None]

    def adjoint(self,rows):
        rows=np.asarray(rows,complex)
        if rows.shape!=self.shape or not np.isfinite(rows).all():
            raise ValueError('Invalid supported rows')
        full=np.zeros(self.frame.shape,complex)
        full[self.keep]=rows*self.amplitude_scale*self.weights[None,:,None]
        return self.frame.adjoint(full)
