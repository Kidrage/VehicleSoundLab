"""Conservative, unnormalized recording-level measurements, not physical source separation."""
import numpy as np
from scipy.signal import spectrogram


BANDS = ((20, 80), (80, 250), (250, 1200), (1200, 3000),
         (3000, 6000), (6000, 14000), (14000, 20000))


def recording_measurements(audio, rate):
    assert audio.ndim == 2 and audio.shape[1] == 2 and np.isfinite(audio).all()
    assert rate == 48000 and len(audio) >= rate
    measured = []
    means = []
    for channel in range(2):
        hz, seconds, psd = spectrogram(audio[:, channel], fs=rate, window='hann',
            nperseg=rate, noverlap=rate//2, detrend=False, scaling='density', mode='psd')
        means.append(psd.mean(axis=1))
        measured.append(np.array([psd[(hz >= lo) & (hz < hi)].sum(axis=0)*(hz[1]-hz[0])
                                  for lo, hi in BANDS]))
    band_power = np.array(measured)
    quarter = rate//4
    count = len(audio)//quarter
    frame_rms = np.sqrt(np.mean(audio[:count*quarter].reshape(count, quarter, 2)**2, axis=1))
    stats = dict(frames=len(audio), sample_rate=rate, channels=2,
        duration_seconds=len(audio)/rate,
        rms_dbfs_LR=(10*np.log10(np.maximum(np.mean(audio**2, axis=0), 1e-30))).tolist(),
        decoded_sample_peak_LR=abs(audio).max(axis=0).tolist(),
        decoded_samples_above_full_scale_LR=np.sum(abs(audio) >= 1, axis=0).tolist(),
        recording_LR_correlation=float(np.corrcoef(audio.T)[0, 1]),
        bands_Hz=[list(band) for band in BANDS],
        mean_recording_band_dbfs_LR=(10*np.log10(np.maximum(band_power.mean(axis=2), 1e-30))).tolist(),
        spectral_window_seconds=1, spectral_hop_seconds=.5,
        limits=['Mixed recording powers, not engine/intake/exhaust/noise source budgets',
            'Spectral peaks are not RPM measurements or Sound DNA extraction',
            'Decoded samples above full scale do not prove original ADC clipping',
            'No denoising, gain normalization, resampling, pitch warp or listening acceptance'])
    arrays = dict(hz=hz, seconds=seconds, mean_psd_LR=np.array(means),
                  band_power_LR=band_power,
                  rms_seconds=(np.arange(count)+.5)*.25, rms_LR=frame_rms)
    return stats, arrays
