"""A real-linear, all-bin Hann frame with exact finite-record coverage."""
import numpy as np


class CompleteHann:
    def __init__(self, frames, channels=2, size=4096, hop=256):
        if frames < 1 or channels not in (1,2) or size < 4 or size%2 or hop < 1 or size%hop or hop >= size:
            raise ValueError('Invalid complete-frame dimensions')
        self.frames,self.channels,self.size,self.hop=map(int,(frames,channels,size,hop))
        self.starts=np.arange(-(size-hop),frames,hop)
        self.window=.5-.5*np.cos(2*np.pi*np.arange(size)/size)
        self.coverage=np.zeros(frames)
        self.support=[]
        for start in self.starts:
            first,last=max(0,start),min(frames,start+size)
            offset=first-start
            w=self.window[offset:offset+last-first]
            self.coverage[first:last]+=w*w
            self.support.append((first,last,offset))
        if not np.isfinite(self.coverage).all() or np.any(self.coverage<=0):
            raise ValueError('Uncovered finite-record sample')
        self.normalizer=1/np.sqrt(self.coverage)
        self.weights=np.full(size//2+1,np.sqrt(2.));self.weights[[0,-1]]=1.
        self.shape=(len(self.starts),size//2+1,channels)

    def forward(self,audio):
        audio=np.asarray(audio)
        if audio.shape!=(self.frames,self.channels) or np.iscomplexobj(audio) or not np.isfinite(audio).all():
            raise ValueError('Invalid real waveform')
        windows=np.zeros((len(self.starts),self.size,self.channels))
        for j,(first,last,offset) in enumerate(self.support):
            windows[j,offset:offset+last-first]=audio[first:last]*self.normalizer[first:last,None]
        windows*=self.window[None,:,None]
        return np.fft.rfft(windows,axis=1)*self.weights[None,:,None]/np.sqrt(self.size)

    def adjoint(self,rows):
        rows=np.asarray(rows,complex)
        if rows.shape!=self.shape or not np.isfinite(rows).all():raise ValueError('Invalid complete rows')
        windows=np.fft.irfft(rows/self.weights[None,:,None],n=self.size,axis=1)*np.sqrt(self.size)
        audio=np.zeros((self.frames,self.channels))
        for j,(first,last,offset) in enumerate(self.support):
            audio[first:last]+=windows[j,offset:offset+last-first]*self.window[offset:offset+last-first,None]*self.normalizer[first:last,None]
        return audio
