"""Owned finite source basis with explicit frozen carrier values and row layout."""
import numpy as np
from observer_complete_v1.frame import CompleteHann


class Geometry:
    def __init__(self,frames,positions,orders,scale,carriers,weights,amplitude,sigma):
        p,h,s,c,w=map(np.asarray,(positions,orders,scale,carriers,weights))
        if (type(frames) is not int or frames<8192 or p.ndim!=1 or len(p)<3 or p.dtype.kind not in 'iu'
            or p[0]!=0 or p[-1]!=frames-1 or np.any(np.diff(p.astype(np.int64))<=0)
            or h.ndim!=1 or h.dtype.kind not in 'iu' or not len(h) or np.any((h<1)|(h>511)) or len(np.unique(h))!=len(h)
            or s.shape!=(len(h),1) or np.iscomplexobj(s) or not np.isfinite(s).all() or np.any(s<=0)
            or c.shape!=(1024,len(h)) or not np.iscomplexobj(c) or not np.isfinite(c).all()
            or w.shape!=(2049,) or np.iscomplexobj(w) or not np.isfinite(w).all() or np.any(w<=0)
            or not np.isfinite([amplitude,sigma]).all() or min(amplitude,sigma)<=0):
            raise ValueError('Complete finite geometry and explicit basis/calibration required')
        self.frames=frames;self.positions=p.copy();self.orders=h.copy();self.scale=s.copy();self.carriers=c.copy()
        self.weights=w.copy();self.amplitude=float(amplitude);self.sigma=float(sigma)
        self.shape=(len(p),len(h),2);self.half=int(np.prod(self.shape));self.size=2*self.half;self.mono_size=self.size//2
        n=np.arange(frames);self.hats=np.array([np.interp(n,p,row) for row in np.eye(len(p))])
        frame=CompleteHann(frames,2)
        self.window=frame.window.copy();self.normalizer=frame.normalizer.copy();self.endpoint=frame.weights.copy()
        self.starts=frame.starts[(frame.starts>=0)&(frame.starts+4096<=frames)]
        self.target_slots=np.flatnonzero((self.starts>=2048)&(self.starts+4096<=frames-2048))
        self.bands=np.searchsorted([3000,6000,8000,10000,14000],np.arange(2049)*16,side='right')
        self.row_shape=(len(self.starts),2049,2);self.full_rows=2*frames+4*len(self.starts)*2049
        for value in (self.positions,self.orders,self.scale,self.carriers,self.weights,self.hats,self.window,self.normalizer,self.endpoint):value.flags.writeable=False

    def nodes(self,x):
        x=np.asarray(x)
        if x.shape!=(self.size,) or np.iscomplexobj(x) or not np.isfinite(x).all():raise ValueError('Complete real coefficient vector required')
        return x[:self.half].reshape(self.shape)+1j*x[self.half:].reshape(self.shape)

    @staticmethod
    def vector(value):return np.r_[value.real.ravel(),value.imag.ravel()]

    def coefficients(self,x):
        value=self.nodes(x)
        return np.vstack((value.real.reshape(-1,2),value.imag.reshape(-1,2)))

    def coefficient_vector(self,values):
        return np.r_[values[:self.mono_size//2].ravel(),values[self.mono_size//2:].ravel()]

    def active(self,first,last):
        nodes=np.flatnonzero(np.any(self.hats[:,first:last]!=0,axis=1));h=len(self.orders)
        real=(nodes[:,None]*h+np.arange(h)).ravel()
        return np.r_[real,real+len(self.positions)*h]

    def columns(self,first,last,ids):
        ids=np.asarray(ids);h=len(self.orders);half=self.mono_size//2
        index=ids%half;node=index//h;harmonic=index%h
        phase=np.arange(first,last)%1024;carrier=self.carriers[phase[:,None],harmonic[None,:]]
        value=np.where(ids[None,:]<half,carrier.real,-carrier.imag)
        value=self.hats[node,first:last].T*value
        value*=self.scale[harmonic,0][None,:]
        return value
