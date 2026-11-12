"""Only independently defined fixture components, never blind source separation."""
import numpy as np
from scipy import signal
from fractional_clock_v1.fixtures import make


def split(case, seconds):
    full, time, phase, frequency = make(case, seconds)
    fixed = np.zeros_like(full)
    if case['kind'] not in ('single_carrier', 'noise_only', 'all_carriers_gap'):
        for hz, offset in ((10811,.2),(12503,-.8),(13411,1.2)):
            fixed[:,0] += .006*np.cos(2*np.pi*hz*time+offset)
            fixed[:,1] += .004*np.cos(2*np.pi*hz*(time-.0007)+offset+.2)
    rng = np.random.default_rng(910246)
    noise = .0025*signal.sosfilt(signal.butter(2,9000,fs=48000,output='sos'), rng.normal(size=full.shape))
    mask = np.zeros_like(full)
    if case['kind']=='masking':
        mask = .09*np.cos(2*np.pi*(case['masked_order']*case['root_hz']+7.3)*time)[:,None]*np.array([1,.63])
    family = full-fixed-noise-mask
    parts = dict(common_phase_family=family,fixed_hz_detail=fixed,known_noise=noise,independent_mask=mask)
    reconstruction = float(np.max(abs(sum(parts.values())-full)))
    return full, parts, time, phase, frequency, reconstruction


def high_carriers(phase, frequency):
    """The original fixture's known extra HF carriers, without other signals."""
    result = {}
    for order in sorted(set(int(hz/max(frequency)) for hz in (12000,13500))):
        if order>288:
            angle=2*np.pi*order*phase+.19*order
            result[order]=np.column_stack((.008*np.cos(angle),.006*np.cos(angle+.3)))
    return result
