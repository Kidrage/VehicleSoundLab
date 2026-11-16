"""Owned realification of the existing full OSC bank, no dense source matrix."""
import numpy as np
from scipy import fft
from observer_complete_v1.synthesis import WaveSynthesis


class Source:
    def __init__(self,frames,positions,orders,scale):
        positions,orders,scale=map(np.asarray,(positions,orders,scale))
        if (not isinstance(frames,int) or frames<8192 or positions.ndim!=1 or len(positions)<3
            or positions.dtype.kind not in 'iu' or positions[0]!=0 or positions[-1]!=frames-1
            or np.any(np.diff(positions.astype(np.int64))<=0)
            or orders.ndim!=1 or orders.dtype.kind not in 'iu' or not len(orders)
            or np.any((orders<1)|(orders>511)) or len(np.unique(orders))!=len(orders)
            or scale.shape!=(len(orders),1) or np.iscomplexobj(scale)
            or not np.isfinite(scale).all() or np.any(scale<=0)):
            raise ValueError('Complete integer OSC geometry and positive shared scales required')
        self.frames=frames;self.positions=positions.copy();self.orders=orders.copy();self.scale=scale.copy()
        for value in (self.positions,self.orders,self.scale):value.flags.writeable=False
        self.shape=(len(positions),len(orders),2);self.half=int(np.prod(self.shape));self.size=2*self.half
        self.operator=WaveSynthesis(frames,self.positions,self.orders,2)

    def nodes(self,x):
        x=np.asarray(x)
        if x.shape!=(self.size,) or np.iscomplexobj(x) or not np.isfinite(x).all():raise ValueError('Finite real node vector required')
        return x[:self.half].reshape(self.shape)+1j*x[self.half:].reshape(self.shape)

    @staticmethod
    def vector(nodes):return np.r_[nodes.real.ravel(),nodes.imag.ravel()]

    def forward(self,x):return self.operator.synthesize(self.nodes(x)*self.scale[None])

    def adjoint(self,wave):
        wave=np.asarray(wave)
        if wave.shape!=(self.frames,2) or np.iscomplexobj(wave) or not np.isfinite(wave).all():raise ValueError('Complete finite real waveform gradient required')
        result=np.empty(self.shape,np.clongdouble)
        for j,(first,last,phase,hat) in enumerate(self.operator.operator.support):
            cycle=np.zeros((1024,2),np.longdouble)
            np.add.at(cycle,phase,wave[first:last].astype(np.longdouble)*hat.astype(np.longdouble)[:,None])
            result[j]=fft.fft(cycle,axis=0)[self.orders]
        return self.vector(result*self.scale[None]).astype(float)
