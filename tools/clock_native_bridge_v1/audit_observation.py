"""Independent native PSD/CSD at all bins and four upper-band sums."""
import numpy as np
from scipy import signal
from native_clock_case_audit_v1.sound import verify as broad, comparisons


def verify(name, audio, saved, check, gates):
    frames = np.array([audio[s:s+4096] for s in range(0, len(audio)-4096+1, 256)])
    w = .5-.5*np.cos(2*np.pi*np.arange(4096)/4096)
    args = dict(fs=48000, window=w, nperseg=4096, noverlap=0, detrend=False, scaling='density', axis=1)
    f, p = signal.welch(frames, **args)
    _, c = signal.csd(frames[:, :, 1], frames[:, :, 0], **args)
    mid_side = np.stack(((frames[:, :, 0]+frames[:, :, 1])/2, (frames[:, :, 0]-frames[:, :, 1])/2), axis=2)
    _, ms = signal.welch(mid_side, **args)
    p, c, ms = p*(48000/4096), c*(48000/4096), ms*(48000/4096)
    scale = float(np.max(np.sum(p, axis=1)))
    for key, expected in (('bin_power', p), ('bin_cross', c), ('bin_mid_side', ms)):
        check(name+'_'+key, saved[name+'_'+key], expected, scale, 2e-11)
    masks = [(f >= lo)&(f < hi) for lo, hi in ((14000, 16000), (16000, 20000), (20000, 22000), (22000, 24001))]
    values = dict(upper_power=np.stack([p[:, m].sum(axis=1) for m in masks], axis=1),
        upper_cross=np.stack([c[:, m].sum(axis=1) for m in masks], axis=1),
        upper_mid_side=np.stack([ms[:, m].sum(axis=1) for m in masks], axis=1))
    for key, expected in values.items():
        check(name+'_'+key, saved[name+'_'+key], expected, scale, 2e-11)
    windows = broad(name, audio, saved, check, gates)
    return dict(all_bins=2049, LR_complex_cross_and_direct_MS=True, windows=windows,
        linear_gate_relative_total_power=2e-11, frozen_statistics_gate=2e-11,
        not_a_new_crossFFT_normalized_or_certified_bound=True)
