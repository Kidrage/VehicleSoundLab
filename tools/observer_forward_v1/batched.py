"""Batch FFTs of the SAME offline envelope/observer/adjoint operator."""
import numpy as np
from .polyphase import PolyphaseObserver


class BatchedObserver(PolyphaseObserver):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.support_node=np.concatenate([np.full(last-first,j) for j,(first,last,_,_) in enumerate(self.support)])
        self.support_time=np.concatenate([np.arange(first,last) for first,last,_,_ in self.support])
        self.support_phase=self.support_time%1024
        self.support_hat=np.concatenate([hat for _,_,_,hat in self.support])
        self.window_times=(self.starts[:,None]+np.arange(4096)[None,:]).ravel()
        self.demodulation=np.exp(-2j*np.pi*self.starts[:,None]*self.observed[None,:]/1024)

    def synthesize(self,nodes,block=1024):
        nodes=np.asarray(nodes,complex)
        if nodes.shape!=self.shape or not np.isfinite(nodes).all() or int(block)!=block or block<1:raise ValueError('Invalid nodes/block')
        spectrum=np.zeros((len(nodes),513,self.channels),complex);spectrum[:,self.orders]=nodes
        cycles=np.fft.irfft(spectrum,n=1024,axis=1)*512
        audio=np.zeros((self.frames,self.channels))
        values=cycles[self.support_node,self.support_phase]*self.support_hat[:,None]
        np.add.at(audio,self.support_time,values)
        return audio

    def observe(self,audio):
        audio=np.asarray(audio)
        if audio.shape!=(self.frames,self.channels) or not np.isfinite(audio).all():raise ValueError('Invalid audio')
        windows=audio[self.window_times].reshape(len(self.starts),4096,self.channels)*self.window[None,:,None]
        transform=np.fft.rfft(windows,axis=1)[:,4*self.observed]
        return transform*(2/self.window.sum())*self.demodulation[:,:,None]

    def adjoint(self,rows):
        rows=np.asarray(rows,complex)
        if rows.shape!=self.output_shape or not np.isfinite(rows).all():raise ValueError('Invalid observed rows')
        spectrum=np.zeros((len(self.starts),2049,self.channels),complex)
        spectrum[:,4*self.observed]=rows*self.demodulation.conj()[:,:,None]
        windows=np.fft.irfft(spectrum,n=4096,axis=1)*(4096/self.window.sum())*self.window[None,:,None]
        wave_gradient=np.zeros((self.frames,self.channels));np.add.at(wave_gradient,self.window_times,windows.reshape(-1,self.channels))
        cycles=np.zeros((len(self.positions),1024,self.channels))
        values=wave_gradient[self.support_time]*self.support_hat[:,None]
        np.add.at(cycles,(self.support_node,self.support_phase),values)
        return np.fft.fft(cycles,axis=1)[:,self.orders]
