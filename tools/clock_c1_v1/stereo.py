"""Ordinary LR/MS and temporal powers; independent from the locked observer."""
import numpy as np
from locked_source_tail_v1.audit_measure import LABELS, masks


def measure(audio):
    part = audio[2048:-2048]
    starts = np.arange(0, len(part)-4096+1, 256)
    window = .5-.5*np.cos(2*np.pi*np.arange(4096)/4096)
    x = np.fft.rfft(part[starts[:, None]+np.arange(4096)]*window[None, :, None], axis=1)
    edge = np.r_[1., np.full(2047, 2.), 1.]/(4096*np.dot(window, window))
    power, cross, ms = [], [], []
    for mask in masks():
        a = x[:, mask]; scale = edge[mask]
        power.append(np.sum(abs(a)**2*scale[None, :, None], axis=1))
        cross.append(np.sum(a[:, :, 0]*a[:, :, 1].conj()*scale, axis=1))
        m = (a[:, :, 0]+a[:, :, 1])/2
        s = (a[:, :, 0]-a[:, :, 1])/2
        ms.append(np.column_stack((np.sum(abs(m)**2*scale, axis=1), np.sum(abs(s)**2*scale, axis=1))))
    p, cross, ms = np.asarray(power).transpose(1, 0, 2), np.asarray(cross).T, np.asarray(ms).transpose(1, 0, 2)
    mean = p.mean(axis=0); defined = mean > 0
    normalized = np.divide(p, mean, out=np.zeros_like(p), where=defined)-defined
    cv = np.sqrt(np.mean(normalized**2, axis=0))
    flat = normalized.reshape(len(p), -1)
    covariance = flat.T@flat/len(flat)
    denominator = np.sqrt(mean[:, 0]*mean[:, 1])
    coherence = np.divide(cross.mean(axis=0), denominator, out=np.zeros(len(denominator), complex), where=denominator>0)
    return dict(starts=starts, power=p, cross=cross, mid_side=ms, mean_power=mean,
        mean_mid_side=ms.mean(axis=0), CV=cv, covariance=covariance,
        complex_coherence=coherence, power_defined=defined)


def compare(old, new):
    rows = []
    for k, label in enumerate(LABELS):
        rows.append(dict(band=label, old_Welch_FS2_LR=old['mean_power'][k].tolist(),
            C1_Welch_FS2_LR=new['mean_power'][k].tolist(),
            power_change_dB_LR=(10*np.log10(new['mean_power'][k]/old['mean_power'][k])).tolist(),
            coherence_complex_difference=float(abs(new['complex_coherence'][k]-old['complex_coherence'][k])),
            old_Side_Mid_dB=float(10*np.log10(old['mean_mid_side'][k, 1]/old['mean_mid_side'][k, 0])),
            C1_Side_Mid_dB=float(10*np.log10(new['mean_mid_side'][k, 1]/new['mean_mid_side'][k, 0])),
            CV_change_LR=(new['CV'][k]-old['CV'][k]).tolist()))
    return dict(bands=rows, normalized_covariance_max_change=float(np.max(abs(new['covariance']-old['covariance']))),
        no_new_gain_floor_width_or_room=True, virtual_frequency_not_physical_Hz=True)
