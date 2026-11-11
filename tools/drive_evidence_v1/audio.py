"""Windowed observations; acoustic peaks are not engine or injector telemetry."""
import csv
import numpy as np
from scipy import signal
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

BANDS = [(28, 120), (120, 400), (400, 1200), (1200, 3000), (3000, 8000), (8000, 16000)]


def strongest(hz, spectrum, low=160, high=450):
    db = 10 * np.log10(np.maximum(spectrum, 1e-30))
    peaks, _ = signal.find_peaks(db, prominence=8)
    peaks = peaks[(hz[peaks] >= low) & (hz[peaks] <= high)]
    if not len(peaks):
        return np.nan
    k = peaks[np.argmax(spectrum[peaks])]
    a, b, c = db[k-1:k+2]
    delta = .5 * (a-c) / (a-2*b+c) if abs(a-2*b+c) > 1e-12 else 0
    return float(hz[k] + np.clip(delta, -.5, .5) * (hz[1]-hz[0]))


def observe(audio, provenance, output):
    rate, window, hop, fft = 48000, 3840, 480, 32768
    hz, times, psd = signal.spectrogram(audio.T, rate, window='hann', nperseg=window,
        noverlap=window-hop, nfft=fft, detrend=False, scaling='density', mode='psd')
    assert psd.shape == (2, len(hz), len(times))
    power = psd.mean(axis=0)  # A selection view, never a waveform downmix.
    bands = np.stack([psd[:, (hz >= lo) & (hz < hi)].sum(axis=1) * rate/fft for lo, hi in BANDS], axis=1)
    peaks = np.array([strongest(hz, power[:, i]) for i in range(len(times))])
    times += provenance['seconds'][0]
    np.savez_compressed(output / 'audio.npz', hz=hz, seconds=times, psd_LR=psd,
        band_power_LR=bands, strongest160_450_hz=peaks)
    with (output / 'audio.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['source_seconds', 'strongest160_450_hz'] + [f'{lo}_{hi}_{channel}_dbfs' for channel in ('L', 'R') for lo, hi in BANDS])
        levels = 10*np.log10(np.maximum(bands, 1e-30)).transpose(2, 0, 1).reshape(len(times), -1)
        writer.writerows(zip(times, peaks, *levels.T))
    fig, axes = plt.subplots(3, 1, figsize=(13, 9), sharex=True, constrained_layout=True)
    keep = (hz >= 80) & (hz <= 1800)
    db = 10*np.log10(np.maximum(power[keep], 1e-30))
    axes[0].pcolormesh(times, hz[keep], db, vmin=db.max()-55, vmax=db.max(), shading='auto', rasterized=True, cmap='magma')
    axes[0].set_ylabel('Observed Hz')
    axes[0].set_title(f"{provenance['segment_id']} | 80ms window / 10ms hop | no RPM assignment")
    axes[1].plot(times, peaks, '.', ms=2)
    axes[1].set_ylabel('Strongest peak\n160..450Hz')
    for i, (lo, hi) in enumerate(BANDS):
        axes[2].plot(times, 10*np.log10(np.maximum(bands[:, i].mean(axis=0), 1e-30)), label=f'{lo}-{hi}Hz')
    axes[2].set_ylabel('Band power dBFS')
    axes[2].set_xlabel('Decoded audio source seconds; A/V offset unmeasured')
    axes[2].legend(ncol=3, fontsize=8)
    fig.savefig(output / 'audio.png', dpi=140)
    plt.close(fig)
    return dict(window_samples=window, hop_samples=hop, padded_fft_size=fft,
        padded_resolution_warning='Zero padding interpolates bins; actual window is80ms',
        peak_rule='Highest-power local peak160..450Hz, prominence>=8dB; no continuity or order inference',
        frames=len(times), raw_rms_dbfs=float(10*np.log10(np.mean(audio**2))),
        raw_peak=float(abs(audio).max()), finite_peaks=int(np.isfinite(peaks).sum()),
        channel_policy='Preserve L/R PSD and band powers; mean power used only for peak selection/plot')
