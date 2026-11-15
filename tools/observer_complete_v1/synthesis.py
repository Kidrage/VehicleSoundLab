"""The existing node/OSC model with a waveform-domain real adjoint."""
import numpy as np
from observer_forward_v1.polyphase import PolyphaseObserver


class WaveSynthesis:
    def __init__(self,frames,positions,orders,channels=2):
        self.operator=PolyphaseObserver(frames,positions,orders,orders,channels)
        for name in ('frames','positions','orders','channels','shape'):
            setattr(self,name,getattr(self.operator,name))

    def synthesize(self,nodes,block=1024):
        return self.operator.synthesize(nodes,block)

    def adjoint(self,wave):
        wave=np.asarray(wave)
        if wave.shape!=(self.frames,self.channels) or np.iscomplexobj(wave) or not np.isfinite(wave).all():
            raise ValueError('Invalid real waveform gradient')
        result=np.empty(self.shape,complex)
        for j,(first,last,phase,hat) in enumerate(self.operator.support):
            cycle=np.zeros((1024,self.channels))
            np.add.at(cycle,phase,wave[first:last]*hat[:,None])
            result[j]=np.fft.fft(cycle,axis=0)[self.orders]
        return result
