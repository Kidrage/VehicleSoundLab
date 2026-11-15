"""Independent declared rounded-frame observations; no producer imports.

The frozen wave is verified separately against the independent scalar basis.
Cross-operator normalized failures remain measurements, not repaired passes.
"""
import numpy as np
from observer_complete_v1.audit_oracle import full_frame


def frame(audio, *, size=4096, hop=256):
    audio = np.asarray(audio)
    if (audio.ndim != 2 or audio.shape[1] != 2 or np.iscomplexobj(audio)
            or not np.isfinite(audio).all() or size < 4 or size % 2
            or not 0 < hop < size or size % hop or len(audio) < size):
        raise ValueError('Finite stereo and complete finite-frame geometry required')
    starts = np.arange(-(size-hop), len(audio), hop)
    window = .5-.5*np.cos(2*np.pi*np.arange(size)/size)
    cover = np.zeros(len(audio))
    for start in starts:
        lo, hi = max(0, start), min(len(audio), start+size)
        w = window[lo-start:hi-start]
        cover[lo:hi] += w*w
    normalizer = 1/np.sqrt(cover)
    endpoint = np.full(size//2+1, np.sqrt(2.))
    endpoint[[0, -1]] = 1.
    rows = []
    for start in starts:
        lo, hi = max(0, start), min(len(audio), start+size)
        samples = np.zeros((size, 2))
        samples[lo-start:hi-start] = audio[lo:hi]*normalizer[lo:hi, None]
        samples *= window[:, None]
        rows.append(np.column_stack([np.fft.rfft(samples[:, c])*endpoint/np.sqrt(size) for c in (0, 1)]))
    return np.asarray(rows), cover


def ratio(numerator, denominator):
    den = float(np.linalg.norm(denominator))
    return float(np.linalg.norm(numerator)/den) if den else (0. if not np.count_nonzero(numerator) else None)


def declared(audio, wave, amplitude, weights):
    audio, wave, weights = map(np.asarray, (audio, wave, weights))
    if (wave.shape != audio.shape or np.iscomplexobj(wave) or not np.isfinite(wave).all()
            or weights.shape != (2049,) or np.iscomplexobj(weights) or not np.isfinite(weights).all()
            or np.any(weights <= 0) or not np.isfinite(amplitude) or amplitude <= 0
            or len(audio) < 8192):
        raise ValueError('Complete finite wave and positive unchanged original metric required')
    def supported(value):
        rows, _ = frame(value)
        starts = np.arange(-3840, len(value), 256)
        keep = (starts >= 0) & (starts+4096 <= len(value))
        return rows[keep]*amplitude*weights[None, :, None]
    error = wave-audio
    rows, reference = supported(error), supported(audio)
    target_rows, target_reference = supported(error[2048:-2048]), supported(audio[2048:-2048])
    return metrics(error, audio, rows, reference, target_rows, target_reference)


def metrics(error, audio, rows, reference, target_rows, target_reference):
    bands = np.searchsorted([3000, 6000, 8000, 10000, 14000], np.arange(2049)*16, side='right')
    return dict(whole_wave_NRMSE=ratio(error, audio),
        target_wave_NRMSE=ratio(error[2048:-2048], audio[2048:-2048]),
        target_supported_band_complex_NRMSE=[ratio(target_rows[:, bands == b], target_reference[:, bands == b]) for b in range(6)],
        whole_supported_band_complex_NRMSE=[ratio(rows[:, bands == b], reference[:, bands == b]) for b in range(6)],
        whole_wave_regions_NRMSE=[ratio(error[part], audio[part]) for part in (slice(0, 2048), slice(2048, -2048), slice(-2048, None))])


def cross_operator(oracle, old, wave, audio):
    error = wave-audio
    target_rows, _ = full_frame(error[2048:-2048])
    target_reference, _ = full_frame(audio[2048:-2048])
    return metrics(error, audio, oracle.spectral(error), oracle.spectral(audio),
        target_rows[old['keep']]*old['amplitude']*old['weights'][None, :, None],
        target_reference[old['keep']]*old['amplitude']*old['weights'][None, :, None])


def compare(got, expected, *, enforce=False):
    if set(got) != set(expected):
        raise ValueError('All original seventeen metric values required')
    errors = {}
    for key, reference in expected.items():
        left, right = np.asarray(got[key], dtype=object).ravel(), np.asarray(reference, dtype=object).ravel()
        if left.shape != right.shape:
            raise ValueError('Metric shape changed: '+key)
        pairs = []
        for a, b in zip(left, right):
            if a is None or b is None:
                if a is not None or b is not None:
                    raise AssertionError(('Undefined metric changed', key))
                pairs.append(0.)
            else:
                assert np.isfinite([a, b]).all(), key
                pairs.append(abs(float(a)-float(b)))
        errors[key] = max(pairs)
        if enforce:
            assert errors[key] < 2e-12, ('declared_'+key, errors[key], 2e-12)
    return dict(absolute_differences=errors, original_2e_12_comparison_passed=all(v < 2e-12 for v in errors.values()))


def fidelity(value):
    return bool(value['target_wave_NRMSE'] is not None and value['target_wave_NRMSE'] < .02
        and all(v is not None and v < .02 for v in value['target_supported_band_complex_NRMSE']))
