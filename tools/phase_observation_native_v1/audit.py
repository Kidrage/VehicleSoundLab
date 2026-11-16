"""Independent continuous tones, native polyphase operator and STFT checks."""
import numpy as np
from scipy import signal
from scipy.special import jv


def tones(spec,ch):
    result=[];kind=spec['kind']
    if kind=='silence':return result
    for j,order in enumerate(spec['orders']):
        coefficient=spec['amplitudes'][j,ch]*np.exp(1j*spec['phases'][j,ch])
        local=[(float(order),coefficient)]
        sign=1 if ch==0 or kind in ('common_AM','common_PM') else -1
        if j==1 and kind in ('common_AM','differential_AM'):
            local += [(order-1/7,coefficient*sign*.15),(order+1/7,coefficient*sign*.15)]
        if j==1 and kind in ('common_PM','relative_PM'):
            local=[(order+m/7,coefficient*jv(m,sign*.4)) for m in range(-12,13)]
        if j==1 and kind=='sideband':local += [(64+1/7,.013*np.exp(.3j))] if ch==0 else [(64-1/7,.017*np.exp(-.2j))]
        result.extend(local)
    return result


def continuous(spec,q):
    result=np.zeros((len(q),2))
    for ch in (0,1):
        for order,coefficient in tones(spec,ch):
            result[:,ch]+=(coefficient*np.exp(2j*np.pi*order*q/1024)).real
    return result


def envelope64(spec,source_coordinate,observer_centers):
    """Independent sideband sum; never use the producer's envelope evaluator."""
    result=np.zeros((len(source_coordinate),2),complex)
    for ch in (0,1):
        for order,coefficient in tones(spec,ch):
            # All analytic carrier64 AM/PM sidebands lie within two orders;
            # the other fixture carriers start at order17/112, well outside.
            if abs(order-64)<2:
                turns=((order-64)*source_coordinate+64*(source_coordinate-observer_centers))/1024
                result[:,ch]+=coefficient*np.exp(2j*np.pi*turns)
    return result


def phase(seconds,g,depth):
    start=g['normalized_start'];omega=2*np.pi*g['clock_frequency_Hz']
    return 1024*g['root_hz']*(seconds-start+depth*(np.cos(omega*start)-np.cos(omega*seconds))/omega)


def native_bridge(native,positions,cutoff):
    first=int(np.floor(positions[0]*48000+1e-6))-4800
    stop=int(np.ceil(positions[-1]*48000-1e-6))+4801
    grid=np.arange(-512,513)
    taps=np.sinc(grid*cutoff/24000)*(cutoff/24000)*np.kaiser(1025,12)
    taps/=taps.sum()
    filtered=signal.convolve(native[first:stop],taps[:,None],mode='same',method='direct')
    u=np.arange(-160,161)
    poly=np.sinc(u/16)*np.kaiser(321,8.6);poly*=16/poly.sum()
    at=(positions-first/48000)*48000*16
    low=np.floor(at).astype(int);fraction=at-low
    def dense(k):
        ix=k[:,None]//16+np.arange(-10,11)
        ki=160+k[:,None]-16*ix
        weights=poly[np.clip(ki,0,320)]*((ki>=0)&(ki<=320))
        assert ix.min()>=0 and ix.max()<len(filtered)
        return np.einsum('ni,nic->nc',weights,filtered[ix],optimize=False)
    left,right=dense(low),dense(low+1)
    return left+fraction[:,None]*(right-left)


def stft_coefficients(audio,cycles):
    size=1024*cycles;h=np.arange(1,289)
    _,_,spectrum=signal.stft(audio.T,fs=65536,window='hann',nperseg=size,
        noverlap=size-256,boundary=None,padded=False)
    z=np.moveaxis(spectrum[:,h*cycles],(0,1,2),(2,1,0))*2
    starts=np.arange(0,len(audio)-size+1,256)
    return z*np.exp(-2j*np.pi*np.remainder(starts[:,None]*h/1024,1))[:,:,None]


def hann_coefficients(spec,frames,cycles):
    size=1024*cycles;h=np.arange(1,289);starts=np.arange(0,frames-size+1,256)
    result=np.zeros((len(starts),288,2),complex)
    def geometric(x):
        x=np.remainder(x+.5,1)-.5
        return size*np.exp(1j*np.pi*(size-1)*x)*np.sinc(size*x)/np.sinc(x)
    def kernel(turn):
        return (.5*geometric(turn)-.25*geometric(turn+1/size)-.25*geometric(turn-1/size))/(size/2)
    for ch in (0,1):
        for order,c in tones(spec,ch):
            delta=(order-h)/1024;image=(-order-h)/1024
            result[:,:,ch]+=c*np.exp(2j*np.pi*np.remainder(starts[:,None]*delta,1))*kernel(delta)
            result[:,:,ch]+=c.conjugate()*np.exp(2j*np.pi*np.remainder(starts[:,None]*image,1))*kernel(image)
    return result
