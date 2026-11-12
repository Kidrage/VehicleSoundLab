"""Project full real waveforms and their sample derivatives through one aperture."""
import numpy as np


class Aperture:
    def __init__(self,frames,plan):
        cycle=plan['samples_per_cycle']
        self.size=round(plan['projection_cycles']*cycle)
        self.starts=np.arange(0,frames-self.size+1,round(plan['projection_hop_cycles']*cycle))
        self.orders=np.arange(round(plan['observed_order_range'][0]/plan['observed_order_step']),
            round(plan['observed_order_range'][1]/plan['observed_order_step'])+1)*plan['observed_order_step']
        bins=self.orders*plan['projection_cycles']
        if max(abs(bins-np.round(bins)))>1e-10:
            raise ValueError('Projection bins must lie on the declared FFT grid')
        self.bins=np.round(bins).astype(int)
        self.window=.5-.5*np.cos(2*np.pi*np.arange(self.size)/self.size)
        self.rotations=np.exp(-2j*np.pi*self.starts[:,None]*self.orders[None,:]/cycle)

    def apply(self,values):
        vector=values.ndim==1
        if vector:
            values=values[:,None]
        rows=np.array([np.fft.rfft(values[start:start+self.size]*self.window[:,None],axis=0)[self.bins]
            *2/self.window.sum() for start in self.starts])
        rows*=self.rotations[:,:,None]
        flat=rows.reshape(-1,values.shape[1])
        return flat[:,0] if vector else flat


def real_rows(values):
    return np.concatenate((values.real,values.imag),axis=0)
