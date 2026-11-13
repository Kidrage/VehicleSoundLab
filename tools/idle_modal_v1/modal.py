"""Independent acoustic modes; deliberately no inferred engine clock or RPM."""
import numpy as np
from scipy import signal


def peaks(x, rate, plan):
    n = len(x); win = signal.windows.hann(n, sym=False)
    z = np.fft.rfft(x * win[:, None], axis=0)
    p = np.sum(abs(z)**2, axis=1)
    hz = np.fft.rfftfreq(n, 1/rate)
    indices, _ = signal.find_peaks(10*np.log10(p+1e-30),
        prominence=plan['peak_prominence_db'],
        distance=max(1, round(plan['peak_spacing_hz']*n/rate)))
    lo, hi = plan['modal_band_hz']
    indices = indices[(hz[indices] >= lo) & (hz[indices] < hi)]
    if not len(indices):
        return np.empty(0)
    indices = indices[p[indices] >= p[indices].max()*10**(plan['peak_floor_db_relative_to_maximum']/10)]
    indices = indices[np.argsort(p[indices])[::-1]][:plan['maximum_modes']]
    q = np.log(p+1e-30)
    d = .5*(q[indices-1]-q[indices+1])/(q[indices-1]-2*q[indices]+q[indices+1])
    return np.sort((indices+np.clip(d, -.5, .5))*rate/n)


def coefficients(x, rate, frequencies):
    """Joint weighted real LS; all modes use the SAME native local origin."""
    t = (np.arange(len(x))-(len(x)-1)/2)/rate
    angle = 2*np.pi*t[:, None]*frequencies[None, :]
    a = np.column_stack((np.cos(angle), np.sin(angle)))
    w = np.sqrt(signal.windows.hann(len(x), sym=False))
    beta, _, rank, _ = np.linalg.lstsq(a*w[:, None], x*w[:, None], rcond=None)
    if rank != a.shape[1]:
        raise ValueError('Unresolved independent modal design')
    k = len(frequencies)
    # Re(z exp(i wt)) == Re(z)cos(wt)-Im(z)sin(wt).
    return beta[:k]-1j*beta[k:]


def fit(audio, rate, plan):
    n, hop = plan['analysis_frames'], plan['analysis_hop']
    frames = [audio[j:j+n] for j in range(0, len(audio)-n+1, hop)]
    inventories = [peaks(x, rate, plan) for x in frames]
    center = len(frames)//2
    # Fixed central training inventory. A line missing from another window
    # remains missing; do not substitute the strongest unrelated neighbour.
    anchor = inventories[center]
    paths = np.full((len(frames), len(anchor)), np.nan)
    for row, inventory in enumerate(inventories):
        for k, f in enumerate(anchor):
            near = inventory[abs(inventory-f) <= plan['tracking_radius_hz']]
            if len(near) == 1:
                paths[row, k] = near[0]
    support = np.mean(np.isfinite(paths), axis=0)
    keep = support >= plan['minimum_observed_fraction']
    frequencies = np.nanmedian(paths[:, keep], axis=0)
    if not len(frequencies):
        raise ValueError('No training-supported modes')
    z = np.asarray([coefficients(x, rate, frequencies) for x in frames])
    amplitude = np.sqrt(np.mean(abs(z)**2, axis=0))
    phase = np.angle(z[center])
    return dict(frequencies_hz=frequencies.tolist(), amplitude_LR=amplitude.tolist(),
        initial_phase_LR=phase.tolist(),
        evidence=dict(training_windows=len(frames), anchor_frequencies_hz=anchor.tolist(),
            support_fraction=support.tolist(), kept=keep.tolist(),
            local_frequency_paths_hz=[[None if not np.isfinite(v) else float(v) for v in row] for row in paths],
            phase_origin='Central training window midpoint; not a combustion-cycle phase'))


def render(model, frames, rate, ratio=1.):
    out = np.zeros((frames, 2))
    frequencies = np.asarray(model['frequencies_hz'])*ratio
    if ratio <= 0 or frequencies.max(initial=0) >= rate/2:
        raise ValueError('Invalid frequency ratio')
    amplitude, phase = np.asarray(model['amplitude_LR']), np.asarray(model['initial_phase_LR'])
    # Blocked native direct sine bank. Length does not depend on pitch.
    for start in range(0, frames, 8192):
        t = np.arange(start, min(frames, start+8192))/rate
        angle = 2*np.pi*np.remainder(t[:, None]*frequencies, 1.)
        for c in range(2):
            out[start:start+len(t), c] = np.cos(angle+phase[:, c])@amplitude[:, c]
    return out


def controls(plan):
    rate=plan['sample_rate']; n=plan['analysis_frames']; t=(np.arange(n)-(n-1)/2)/rate
    f=np.array([75.31, 191.47]); amp=np.array([[.20,.12],[.08,.06]])
    phase=np.array([[.31,-.4],[1.1,.7]])
    x=sum(amp[k]*np.cos(2*np.pi*f[k]*t[:,None]+phase[k]) for k in range(2))
    measured=peaks(x,rate,plan)
    assert len(measured)==2
    freq_error=float(np.max(abs(measured-f))); assert freq_error < .04
    z=coefficients(x,rate,f)
    coeff_error=float(np.max(abs(z-amp*np.exp(1j*phase)))); assert coeff_error < 1e-12
    model=dict(frequencies_hz=f.tolist(),amplitude_LR=amp.tolist(),initial_phase_LR=phase.tolist())
    y=render(model,12347,rate,1.1); tt=np.arange(len(y))/rate
    oracle=sum(amp[k]*np.cos(2*np.pi*f[k]*1.1*tt[:,None]+phase[k]) for k in range(2))
    err=float(np.max(abs(y-oracle))); assert err < 1e-12
    assert np.array_equal(render(model,24000,rate),render(model,48000,rate)[:24000])
    return dict(off_grid_frequency_error_hz=freq_error,complex_coefficient_error=coeff_error,
        direct_modal_oracle_error=err,duration_independent_of_pitch=True,prefix_exact=True)
