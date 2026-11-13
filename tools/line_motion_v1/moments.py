"""Local Hann frequency reassignment; no clock integration or phase unwrapping."""
import numpy as np


def observe(audio, rate, nominal):
    assert len(audio)==rate and audio.shape[1]==2
    time=np.arange(rate)/rate
    window=np.sin(np.pi*time)**2
    derivative=np.pi*np.sin(2*np.pi*time)
    kernel=np.exp(-2j*np.pi*np.asarray(nominal)[:,None]*time)
    value=kernel@(window[:,None]*audio)
    slope=kernel@(derivative[:,None]*audio)
    magnitude=2*abs(value)/window.sum()
    relative=20*np.log10(np.maximum(magnitude,1e-300)/np.maximum(magnitude.max(axis=0),1e-300))
    frequency=np.asarray(nominal)[:,None]-np.imag(slope/value)/(2*np.pi)
    return dict(moment=value,derivative_moment=slope,amplitude=magnitude,
                relative_db=relative,supported=relative>=-30,frequency_Hz=frequency)


def group_observation(frequency):
    roots=frequency[:3]/np.array([2,3,5])[:,None]
    mean=roots.mean(axis=0)
    loo=np.stack([roots[i]-np.delete(roots,i,axis=0).mean(axis=0) for i in range(3)])
    return dict(anchor_divided_frequencies_Hz=roots,mean_anchor_base_Hz=mean,
                leave_one_out_base_error_Hz=loo,heldout_order1_error_Hz=frequency[4]-mean,
                extra_11_over_5_error_Hz=frequency[3]-11/5*mean)
