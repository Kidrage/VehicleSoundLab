"""Observed band-power modulation; stationary beating is not physical source AM."""
import numpy as np
from scipy import signal


def measure(audio,bands):
    n=2048;hop=256;window=signal.windows.hann(n,sym=False)
    _,t,z=signal.stft(audio,48000,window=window,nperseg=n,noverlap=n-hop,
        boundary=None,padded=False,axis=0,scaling='psd',detrend=False)
    hz=np.fft.rfftfreq(n,1/48000)
    power=np.array([(abs(z[(hz>=a)&(hz<b)])**2).sum(axis=0)*2*48000/n for a,b in bands]).transpose(2,0,1)
    # z shape frequency,channel,time; result is time,band,channel.
    relative=power/np.maximum(power.mean(axis=0),1e-30)-1
    relative=signal.detrend(relative,axis=0,type='linear')
    mod=abs(np.fft.rfft(relative,axis=0))**2
    mod_hz=np.fft.rfftfreq(len(relative),hop/48000)
    selected=(mod_hz>=.5)&(mod_hz<=40)
    part=mod[selected];peak_index=np.argmax(part,axis=0)
    peak_power=np.max(part,axis=0);total=part.sum(axis=0)
    return dict(power_cv_LR=np.sqrt(np.mean(relative**2,axis=0)).tolist(),
        envelope_peak_hz_LR=mod_hz[selected][peak_index].tolist(),
        envelope_peak_bin_fraction_LR=(peak_power/np.maximum(total,1e-30)).tolist(),
        meaning='Single-run detrended STFT band-power modulation; window smoothing, finite realization and ordinary carrier beating contribute; not identified engine AM or a realism gate')
