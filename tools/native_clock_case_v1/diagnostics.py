"""Original-scale waveform and complex physical-band comparisons."""
import numpy as np
from extraction_sound_v1.compare import compare


def relative(error, reference):
    den = float(np.linalg.norm(reference))
    if den:
        return float(np.linalg.norm(error) / den)
    return 0. if not np.count_nonzero(error) else None


def errors(candidate, reference):
    delta = candidate - reference
    size, hop, rate = 4096, 256, 48000
    starts = np.arange(0, len(reference) - size + 1, hop)
    window = .5 - .5 * np.cos(2 * np.pi * np.arange(size) / size)
    indices = starts[:, None] + np.arange(size)[None, :]
    ref = np.fft.rfft(reference[indices] * window[None, :, None], axis=1)
    diff = np.fft.rfft(delta[indices] * window[None, :, None], axis=1)
    frequency = np.arange(size // 2 + 1) * rate / size
    bands = np.searchsorted([3000, 6000, 8000, 10000, 14000], frequency, side='right')
    weights = np.full(len(frequency), 2.)
    weights[[0, -1]] = 1.
    per_band = []
    for b in range(6):
        mask = bands == b
        per_band.append(relative(diff[:, mask] * np.sqrt(weights[mask])[None, :, None],
                                 ref[:, mask] * np.sqrt(weights[mask])[None, :, None]))
    return dict(wave_NRMSE=relative(delta, reference),
                channel_wave_NRMSE=[relative(delta[:, c], reference[:, c]) for c in (0, 1)],
                band_complex_NRMSE=per_band,
                signed_mean_FS=delta.mean(axis=0).tolist(),
                signed_peak_range_FS=[delta.min(axis=0).tolist(), delta.max(axis=0).tolist()])


def comparison(candidate, reference, candidate_measurement, reference_measurement):
    return dict(**errors(candidate, reference),
                signed_changes=compare(candidate_measurement, reference_measurement))


def convergence(result, gates):
    wave = result['wave_NRMSE']
    bands = result['band_complex_NRMSE']
    return bool(wave is not None and wave <= gates['native16_vs_32_wave_NRMSE_max']
                and all(v is not None and v <= gates['native16_vs_32_each_band_complex_NRMSE_max']
                        for v in bands))
