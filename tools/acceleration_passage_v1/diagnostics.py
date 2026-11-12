"""Raw fixed-band budgets and an independent scalar FFT check; no phase warp."""
import numpy as np
from scipy import signal
from shift_evidence_v1.spectrum import observe, BANDS


def budget(audio):
    obs = observe(audio, 0, 80)
    p = obs['power_LR'].mean(axis=2)
    return p, obs


def controls():
    t = np.arange(48000)/48000
    x = np.column_stack((.2*np.sin(2*np.pi*250*t), .1*np.sin(2*np.pi*250*t+.4)))
    power, data = budget(x)
    ratio_error = float(np.max(abs(10*np.log10(power[:, 1]/np.array([.02, .005])))))
    n, fft = 3840, 16384
    w = signal.windows.hann(n, sym=False)
    z = np.fft.rfft(x[:n]*w[:, None], fft, axis=0)
    density = abs(z)**2/(48000*np.sum(w*w))
    density[1:-1] *= 2
    hz = np.fft.rfftfreq(fft, 1/48000)
    scalar = np.array([[sum(float(density[k, c])*48000/fft for k in range(len(hz))
                            if lo <= hz[k] < hi) for lo, hi in BANDS] for c in (0, 1)])
    error = float(abs(scalar-data['power_LR'][:, :, 0]).max())
    assert ratio_error < .001 and error < 1e-14
    return dict(known250Hz_power_error_db=ratio_error, scalar_fft_power_error=error)


def compare(reference, signals):
    target, target_obs = budget(reference)
    results = {}
    observations = {'reference': target_obs}
    for name, audio in signals.items():
        power, obs = budget(audio)
        assert np.array_equal(obs['seconds'], target_obs['seconds'])
        halves = []
        for selected in np.array_split(np.arange(len(obs['seconds'])), 2):
            a = target_obs['power_LR'][:, :, selected].mean(axis=2)
            b = obs['power_LR'][:, :, selected].mean(axis=2)
            halves.append((10*np.log10(np.maximum(b, 1e-30)/np.maximum(a, 1e-30))).T.tolist())
        results[name] = dict(mean_power_error_db_LR=(10*np.log10(power/target)).T.tolist(),
                             half_mean_power_error_db_LR=halves)
        observations[name] = obs
    return dict(bands_hz=list(BANDS), comparisons=results,
        warning='Mixed raw recording versus DNA only; missing broadband/space/level/clock effects are not isolated engine-component gains.'), observations
