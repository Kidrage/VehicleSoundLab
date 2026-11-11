"""Stereo window powers and complex correlation, with bounded FFT batches."""
import numpy as np
from scipy import signal

BANDS = ((28, 120), (120, 400), (400, 1200), (1200, 3000),
         (3000, 8000), (8000, 16000))
RELATIVE_BANDS = ((.5, 2.5), (2.5, 6.5), (6.5, 18.5), (18.5, 45.5),
                  (45.5, 110.5), (110.5, 180.5))


def observe(audio, start_seconds, window_ms, hop=240, rate=48000, clock=None):
    size = round(window_ms * rate / 1000)
    fft = 16384
    window = signal.windows.hann(size, sym=False)
    starts = np.arange(0, len(audio) - size + 1, hop)
    hz = np.fft.rfftfreq(fft, 1 / rate)
    low = hz <= 1200
    power_low = np.empty((int(low.sum()), len(starts)))
    powers = np.empty((2, len(BANDS), len(starts)))
    crosses = np.empty((len(BANDS), len(starts)), dtype=complex)
    times = start_seconds + (starts + size / 2) / rate
    if clock is not None:
        roots = np.interp(times, clock[0], clock[1]) / 5
        relative_powers = np.empty_like(powers)
        relative_crosses = np.empty_like(crosses)
    scale = 1 / (rate * np.sum(window ** 2))
    for first in range(0, len(starts), 64):
        selected = starts[first:first + 64]
        frames = audio[selected[:, None] + np.arange(size)[None, :]]
        z = np.fft.rfft(frames * window[None, :, None], fft, axis=1)
        density = abs(z) ** 2 * scale
        density[:, 1:-1] *= 2
        cross = z[:, :, 0] * np.conj(z[:, :, 1]) * scale
        cross[:, 1:-1] *= 2
        stop = first + len(selected)
        power_low[:, first:stop] = density[:, low].mean(axis=2).T
        for j, (lo, hi) in enumerate(BANDS):
            keep = (hz >= lo) & (hz < hi)
            powers[:, j, first:stop] = density[:, keep].sum(axis=1).T * rate / fft
            crosses[j, first:stop] = cross[:, keep].sum(axis=1) * rate / fft
        if clock is not None:
            for j, (lo, hi) in enumerate(RELATIVE_BANDS):
                mask = ((hz[None, :] >= lo * roots[first:stop, None]) &
                        (hz[None, :] < hi * roots[first:stop, None]))
                relative_powers[:, j, first:stop] = np.einsum('bfc,bf->cb', density, mask) * rate / fft
                relative_crosses[j, first:stop] = np.sum(cross * mask, axis=1) * rate / fft
    result = dict(seconds=times,
                hz=hz[low], power_low=power_low, power_LR=powers, cross_LR=crosses,
                window_samples=size, hop_samples=hop, fft_size=fft)
    if clock is not None:
        result.update(relative_power_LR=relative_powers, relative_cross_LR=relative_crosses)
    return result


def region_stats(observed, lo, hi):
    keep = (observed['seconds'] >= lo) & (observed['seconds'] < hi)
    if int(keep.sum()) < 3:
        return None
    power = observed['power_LR'][:, :, keep].mean(axis=2)
    cross = observed['cross_LR'][:, keep].mean(axis=1)
    correlation = cross / np.sqrt(np.maximum(power[0] * power[1], 1e-60))
    return dict(seconds=[float(lo), float(hi)], frames=int(keep.sum()),
                power_LR=power.tolist(),
                lr_level_db=(10 * np.log10(np.maximum(power[0], 1e-30) /
                                         np.maximum(power[1], 1e-30))).tolist(),
                complex_band_correlation=[[float(z.real), float(z.imag)] for z in correlation])
