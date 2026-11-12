"""Constant/translated/chirped harmonic lines and stationary diffuse controls."""
import numpy as np
from scipy import signal


def cases(rms,phase,frames,plan):
    t=np.arange(frames)/plan['sample_rate']
    def synth(detune=0,chirp=0):
        out=np.zeros((frames,2));clock=(1+detune)*t+.5*chirp*t*t
        for h in range(len(rms)):
            f=(h+1)*plan['sample_rate']/plan['cycle_frames']
            out+=rms[h]*np.cos(2*np.pi*f*clock[:,None]+phase[h])
        return out
    fixed=synth()
    rng=np.random.default_rng(plan['known_noise_seed'])
    sos=signal.butter(4,10000,fs=plan['sample_rate'],output='sos')
    noise=signal.sosfilt(sos,rng.normal(size=(frames+12000,2)),axis=0)[12000:]
    mixed_noise=noise*np.sqrt(np.mean(fixed**2)/np.mean(noise**2))*10**(plan['known_noise_relative_rms_db']/20)
    return [('known_fixed_OSC',fixed),('known_detuned_OSC',synth(detune=plan['known_detune'])),
            ('known_chirp_OSC',synth(chirp=plan['known_chirp_relative_per_second'])),
            ('known_stationary_noise',noise),('known_OSC_plus_noise',fixed+mixed_noise)]
