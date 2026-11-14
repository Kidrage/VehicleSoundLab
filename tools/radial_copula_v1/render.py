"""Offline OSC adapter, same order/taper contract, no driving controller or room."""
import numpy as np
import soundfile as sf
from .latent import endpoints,features
from .quantiles import decode


def render(path,model,root,seconds,seed,variable_phase,block=1024):
    frames = round(seconds*48000)
    count = int(np.floor((frames-1)*root/12000))+2
    state,_ = endpoints(model,count,seed)
    orders = np.arange(1,len(model['fixed_phase'])+1)
    u = np.clip((orders*root-19200)/2400,0,1)
    taper = 1-3*u*u+2*u*u*u
    peak = 0.
    with sf.SoundFile(path,mode='x',samplerate=48000,channels=2,subtype='FLOAT',format='WAV') as out:
        for start in range(0,frames,block):
            n = np.arange(start,min(frames,start+block))
            position = n*root/12000
            at = np.floor(position).astype(int)
            normal = features(model,state,at,position-at)
            amplitude,phase = decode(model,normal,variable_phase)
            base = np.remainder(2*np.pi*n*root/48000,2*np.pi)
            audio = np.sum(amplitude*taper[None,:,None]*np.cos(base[:,None,None]*orders[None,:,None]+phase),axis=1)
            assert np.isfinite(audio).all()
            peak = max(peak,float(abs(audio).max()))
            out.write(audio.astype('float32'))
    return dict(frames=frames,root_hz=root,seed=seed,variable_phase=variable_phase,block=block,peak_FS=peak,
                texture_endpoints=count)
