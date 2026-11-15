"""Real-linear complex-envelope nodes -> OSC -> original finite-Hann rows.

Offline inference operator, not a runtime source or a new physical engine model.
All samples use normalized acoustic coordinates: 1024 samples per cycle.
"""
import numpy as np


class EnvelopeObserver:
    def __init__(self, frames, positions, orders, observed_orders, channels=2):
        self.frames=int(frames);self.positions=np.asarray(positions,dtype=int)
        self.orders=np.asarray(orders,dtype=int);self.observed=np.asarray(observed_orders,dtype=int);self.channels=int(channels)
        if self.frames<4352 or len(self.positions)<2 or self.positions[0]!=0 or self.positions[-1]!=self.frames-1 or np.any(np.diff(self.positions)<=0):raise ValueError('Invalid support')
        if self.channels not in (1,2) or any(len(x)==0 or len(np.unique(x))!=len(x) or np.any((x<1)|(x>=512)) for x in (self.orders,self.observed)):raise ValueError('Invalid carrier/channel count')
        self.shape=(len(self.positions),len(self.orders),self.channels)
        n=np.arange(self.frames);self.left=np.clip(np.searchsorted(self.positions,n,side='right')-1,0,len(self.positions)-2)
        self.weight=(n-self.positions[self.left])/(self.positions[self.left+1]-self.positions[self.left])
        self.starts=np.arange(0,self.frames-4096+1,256)
        self.window=.5-.5*np.cos(2*np.pi*np.arange(4096)/4096)
        self.output_shape=(len(self.starts),len(self.observed),self.channels)

    def synthesize(self,nodes,block=1024):
        nodes=np.asarray(nodes,dtype=complex)
        if nodes.shape!=self.shape or not np.isfinite(nodes).all() or int(block)!=block or block<1:raise ValueError('Invalid nodes/block')
        audio=np.empty((self.frames,self.channels))
        for start in range(0,self.frames,block):
            stop=min(start+block,self.frames);j=self.left[start:stop];w=self.weight[start:stop,None,None]
            env=(1-w)*nodes[j]+w*nodes[j+1]
            phase=2*np.pi*np.remainder(np.arange(start,stop)[:,None]*self.orders[None,:],1024)/1024
            audio[start:stop]=(env*np.exp(1j*phase)[:,:,None]).real.sum(axis=1)
        return audio

    def observe(self,audio):
        audio=np.asarray(audio)
        if audio.shape!=(self.frames,self.channels) or not np.isfinite(audio).all():raise ValueError('Invalid audio')
        rows=[]
        for start in self.starts:
            z=np.fft.rfft(audio[start:start+4096]*self.window[:,None],axis=0)[4*self.observed]
            z*=2/self.window.sum()*np.exp(-2j*np.pi*self.observed*start/1024)[:,None]
            rows.append(z)
        return np.asarray(rows)

    def forward(self,nodes):return self.observe(self.synthesize(nodes))

    def adjoint(self,rows):
        """Adjoint under REAL parts of the complex Euclidean inner products."""
        rows=np.asarray(rows,dtype=complex)
        if rows.shape!=self.output_shape or not np.isfinite(rows).all():raise ValueError('Invalid observed rows')
        wave_gradient=np.zeros((self.frames,self.channels))
        for j,start in enumerate(self.starts):
            bins=np.zeros((2049,self.channels),complex)
            bins[4*self.observed]=rows[j]*np.exp(2j*np.pi*self.observed*start/1024)[:,None]
            wave_gradient[start:start+4096]+=4096/self.window.sum()*self.window[:,None]*np.fft.irfft(bins,n=4096,axis=0)
        phase=2*np.pi*np.remainder(np.arange(self.frames)[:,None]*self.orders[None,:],1024)/1024
        derivative=wave_gradient[:,None,:]*np.exp(-1j*phase)[:,:,None]
        gradient=np.zeros(self.shape,complex)
        np.add.at(gradient,self.left,(1-self.weight[:,None,None])*derivative)
        np.add.at(gradient,self.left+1,self.weight[:,None,None]*derivative)
        return gradient
