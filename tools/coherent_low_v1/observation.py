"""Observe relative acoustic cycles without assigning physical RPM or sources."""
import hashlib
import json
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy import signal


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def observe(workspace):
    catalog_path = workspace / 'references/segments_v1.json'
    catalog = json.loads(catalog_path.read_text(encoding='utf-8'))
    assert catalog['schema'] == 'vsl.reference-segments/1'
    segment = catalog['segments']['A_exterior_moving']
    assert 'exterior_dynamic_observation' in segment['allowed_uses']
    source = catalog['sources'][segment['source']]
    for key in ('raw', 'master'):
        assert sha(workspace / source[key]) == source[key + '_sha256']
    with sf.SoundFile(workspace / source['master']) as stream:
        assert stream.samplerate == 48000 and stream.channels == 2 and stream.subtype == 'FLOAT'
        first, stop = [round(t * stream.samplerate) for t in segment['seconds']]
        stream.seek(first)
        audio = stream.read(stop - first, always_2d=True, dtype='float64')
    ridge_path = workspace / 'references/analysis/sustain_osc_v1/ridge_observations.npz'
    ridge = np.load(ridge_path)
    seconds, frequency = ridge['seconds'], ridge['window128']
    spread = np.ptp(np.array([ridge['window80'], frequency, ridge['window192']]), axis=0)
    assert spread.max() < 2 and np.max(abs(np.diff(frequency))) < 1
    rate = 48000
    times = np.arange(round(seconds[0] * rate), round(seconds[-1] * rate) + 1) / rate
    relative_hz = np.interp(times, seconds, frequency) / 5
    cycles = np.r_[0, np.cumsum((relative_hz[:-1] + relative_hz[1:]) / (2 * rate))]
    positions = np.interp(np.arange(int(cycles[-1] * 1024)) / 1024, cycles, times) * rate * 16
    taps = signal.firwin(1025, 14000, fs=rate, window=('kaiser', 12))
    band = signal.fftconvolve(audio, taps[:, None], mode='same', axes=0)
    dense = signal.resample_poly(band, 16, 1, axis=0, window=('kaiser', 8.6), padtype='line')
    normalized = np.column_stack([np.interp(positions, np.arange(len(dense)), dense[:, c]) for c in range(2)])
    frozen_path = workspace / 'references/analysis/low_body_v1/unhighpassed_normalized_float.wav'
    frozen, frozen_rate = sf.read(frozen_path, always_2d=True)
    assert frozen_rate == rate and np.array_equal(normalized.astype('float32'), frozen.astype('float32'))
    return normalized, dict(
        catalog_sha256=sha(catalog_path), source='A', segment='A_exterior_moving',
        master=source['master'], master_sha256=source['master_sha256'],
        original_seconds=[316.10, 317.25], ridge_sha256=sha(ridge_path),
        normalized_reference_sha256=sha(frozen_path), reproduced_frozen_float_samples=True,
        phase_coordinate='Tracked acoustic ridge / 5; not identified firing order, RPM or load',
        processing='Common cycle warp, 14kHz FIR lowpass, 16x Kaiser interpolation; no highpass or gain change',
        scope='One short mixed exterior context; no isolated physical LF source claim')


def phase_evidence(audio):
    count = len(audio) // 1024
    spectra = np.fft.rfft(audio[:count * 1024].reshape(count, 1024, 2), axis=1)[:, 1:9] * 2 / 1024
    mean = spectra.mean(axis=0)
    power = np.mean(abs(spectra) ** 2, axis=0)
    fractions = abs(mean) ** 2 / np.maximum(power, 1e-30)
    phase_lock = abs(np.mean(spectra / np.maximum(abs(spectra), 1e-15), axis=0))
    first, second = spectra[:count // 2].mean(axis=0), spectra[count // 2:].mean(axis=0)
    # Contiguous half holdout: a phase estimated early is tested later.
    test = spectra[count // 2:]
    baseline = np.mean(abs(test) ** 2, axis=0)
    prediction_gain = 1 - np.mean(abs(test - first) ** 2, axis=0) / np.maximum(baseline, 1e-30)
    rng = np.random.default_rng(90217)
    null_fractions = []
    for _ in range(1000):
        rotations = np.exp(2j * np.pi * rng.random((count, 8, 1)))
        null_fractions.append(abs(np.mean(spectra * rotations, axis=0)) ** 2 / np.maximum(power, 1e-30))
    mono_error = np.sqrt(np.mean((audio[:, 0] - audio[:, 1]) ** 2))
    observed_rms = np.sqrt(np.mean(audio ** 2))
    return dict(
        complete_cycles=count, harmonics=list(range(1, 9)),
        normalized_hz=(np.arange(1, 9) * 46.875).tolist(),
        coherent_power_fraction_LR=fractions.tolist(),
        phase_concentration_LR=phase_lock.tolist(),
        contiguous_half_prediction_gain_LR=prediction_gain.tolist(),
        half_mean_phase_difference_degrees_LR=np.rad2deg(np.angle(first * second.conj())).tolist(),
        random_cycle_phase_null_95_percentile_LR=np.quantile(null_fractions, .95, axis=0).tolist(),
        stereo_difference_relative_db=float(20 * np.log10(max(mono_error / observed_rms, 1e-15))),
        validation_limit='Harmonic 5 defined the warp and is not independent evidence; other harmonics are acoustic relationships, not physical engine orders')
