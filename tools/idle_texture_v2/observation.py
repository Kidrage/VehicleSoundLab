"""Band-local inventories: quiet upper lines must not compete with the bass."""
import numpy as np
from scipy import signal
from idle_modal_v1.modal import peaks


def inventory(audio, plan):
    n, hop, rate = plan['analysis_frames'], plan['analysis_hop'], plan['sample_rate']
    frames = [audio[j:j+n] for j in range(0, len(audio)-n+1, hop)]
    result = []
    for band in plan['upper_bands_hz']:
        local = dict(plan, modal_band_hz=band, maximum_modes=plan['maximum_modes_per_band'])
        found = [peaks(frame, rate, local) for frame in frames]
        anchor = found[len(found)//2]
        paths = np.full((len(found), len(anchor)), np.nan)
        for j, row in enumerate(found):
            for k, f in enumerate(anchor):
                near = row[abs(row-f) <= plan['tracking_radius_hz']]
                if len(near) == 1:
                    paths[j,k] = near[0]
        support = np.mean(np.isfinite(paths), axis=0)
        keep = support >= plan['minimum_observed_fraction']
        result.append(dict(band_hz=band, anchor_hz=anchor.tolist(),
            support=support.tolist(), kept=keep.tolist(),
            frequencies_hz=np.nanmedian(paths[:,keep],axis=0).tolist(),
            paths_hz=[[float(v) if np.isfinite(v) else None for v in row] for row in paths]))
    return result


def stereo(audio, plan):
    rate = plan['sample_rate']
    hz, ll = signal.welch(audio[:,0], fs=rate, nperseg=24000, noverlap=12000, detrend=False)
    _, rr = signal.welch(audio[:,1], fs=rate, nperseg=24000, noverlap=12000, detrend=False)
    _, lr = signal.csd(audio[:,0],audio[:,1],fs=rate,nperseg=24000,noverlap=12000,detrend=False)
    powers = []
    for lo,hi in plan['bands_hz']:
        mask = (hz>=lo)&(hz<hi)
        l,r,z = ll[mask].sum(),rr[mask].sum(),lr[mask].sum()
        powers.append(dict(band_hz=[lo,hi],right_over_left_db=float(10*np.log10(r/l)),
            complex_coherence=[float(z.real/np.sqrt(l*r)),float(z.imag/np.sqrt(l*r))]))
    return dict(maximum_channel_difference=float(abs(audio[:,0]-audio[:,1]).max()),
        side_to_mid_db=float(10*np.log10(np.sum((audio[:,0]-audio[:,1])**2)/
            max(np.sum((audio[:,0]+audio[:,1])**2),1e-300))) if np.any(audio[:,0]!=audio[:,1]) else None,
        band_observations=powers)


def controls(plan):
    rate=plan['sample_rate']; t=np.arange(3*rate)/rate
    # Upper line is 66dB below a low line: a global power floor would omit it.
    x=.2*np.cos(2*np.pi*75.31*t)+.0001*np.cos(2*np.pi*1831.47*t+.4)
    found=inventory(np.column_stack((x,.7*x)),plan)
    upper=found[1]['frequencies_hz']
    assert len(upper)==1 and abs(upper[0]-1831.47)<.04,upper
    # Deliberately absent from enough fixed windows; no interpolation into support.
    y=.2*np.cos(2*np.pi*1831.47*t)
    y[rate:]=0
    missing=inventory(np.column_stack((y,y)),plan)
    assert not missing[1]['frequencies_hz']
    return dict(quiet_upper_line_frequency_error_hz=abs(upper[0]-1831.47),
        missing_line_not_invented=True,holdout_read=False)
