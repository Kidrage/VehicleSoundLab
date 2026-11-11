"""Nonoverlapping source blocks; stereo Welch observations keep L/R separate."""
import numpy as np


def measure(audio, rate, size, hop, bands):
    count = len(audio)//rate
    if count < 2:
        raise ValueError('Need at least two whole one-second blocks')
    hz = np.fft.rfftfreq(size,1/rate)
    starts = np.arange(0,rate-size+1,hop)
    window = .5-.5*np.cos(2*np.pi*np.arange(size)/size)
    scale = np.ones(len(hz))/(size*np.sum(window*window))
    scale[1:-1] *= 2
    left,right,cross,cv = [],[],[],[]
    for block in range(count):
        x = audio[block*rate:(block+1)*rate]
        z = np.fft.rfft(x[starts[:,None]+np.arange(size)]*window[None,:,None],axis=1)
        power = abs(z)**2*scale[None,:,None]
        left.append(power[:,:,0].mean(axis=0));right.append(power[:,:,1].mean(axis=0))
        cross.append((z[:,:,0].conj()*z[:,:,1]*scale[None,:]).mean(axis=0))
        p = np.array([power[:,(hz>=lo)&(hz<hi)].sum(axis=1) for lo,hi in bands]).transpose(1,0,2)
        amplitude = np.sqrt(np.maximum(p,0))
        design = np.column_stack((np.ones(len(starts)),np.linspace(-1,1,len(starts))))
        flat = amplitude.reshape(len(starts),-1)
        detrended = flat-design@np.linalg.lstsq(design,flat,rcond=None)[0]
        cv.append((np.sqrt(np.mean(detrended*detrended,axis=0))/np.maximum(flat.mean(axis=0),1e-30)).reshape(len(bands),2))
    return dict(hz=hz,left=np.array(left),right=np.array(right),cross=np.array(cross),
                detrended_envelope_cv=np.array(cv),windows_per_block=len(starts))


def scalar_check(audio,observed,rate,size,hop):
    """Direct sin/cos DFT, independent of the FFT indexing/transform."""
    starts = list(range(0,rate-size+1,hop))
    at = np.arange(size)
    window = .5-.5*np.cos(2*np.pi*at/size)
    bins = np.array([57,129,241,319])
    kernel = np.cos(2*np.pi*bins[:,None]*at/size)-1j*np.sin(2*np.pi*bins[:,None]*at/size)
    left,right,cross = [],[],[]
    for start in starts:
        z = kernel@(audio[start:start+size]*window[:,None])
        left.append(abs(z[:,0])**2);right.append(abs(z[:,1])**2);cross.append(z[:,0].conj()*z[:,1])
    scale = 2/(size*np.sum(window*window))
    relative = []
    for key,values in (('left',left),('right',right),('cross',cross)):
        actual = np.mean(values,axis=0)*scale
        expected = observed[key][0,bins]
        denominator = np.maximum(np.sqrt(observed['left'][0,bins]*observed['right'][0,bins]),1e-30)
        relative.append(float(np.max(abs(actual-expected)/denominator)))
    return max(relative)
