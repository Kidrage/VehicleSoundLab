"""Diagnose the reported low-bitrate-like original64 quality before more HF.

No original assets or native/frozen programs are changed. Whole archival
diagnostics identify processing artifacts, not physical engine/RPM calibration.
New exterior observations use the approved catalogue reader separately.
"""
from runtime_review import ROOT, sha
import json
import subprocess
import numpy as np
import soundfile as sf
from scipy import signal
from reference_segments import read_segment, checked_source
from osc_quality_v1.fitting import frames, synthesize
from osc_quality_v1.metrics import relative_error, modulation_amplitude, spectral_diagnostics

OUT = ROOT/'references/analysis/osc_quality_v1'
PROBE = ROOT/'build-reference-osc-v1/Release/reference_osc_probe.exe'


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')


def main():
    OUT.mkdir(exist_ok=False)
    source = checked_source('A')
    legacy_path = ROOT/'references/clean/A_tailpipe_road_pull.wav'
    provenance = json.loads(legacy_path.with_suffix('.wav.provenance.json').read_text())
    assert sha(legacy_path) == provenance['output_sha256'] and source['raw_sha256'] == provenance['input_sha256']
    stereo, rate = sf.read(legacy_path, always_2d=True)
    x = stereo.mean(axis=1)  # Explicit historical mono coordinate, identity diagnostic.
    baseline, base_rate = sf.read(ROOT/'references/analysis/reference_osc_v1/archive64_c_float.wav', always_2d=True)
    assert base_rate == rate
    exterior, ext_rate, ext_provenance = read_segment('A_exterior_moving', 'exterior_dynamic_observation')
    assert ext_rate == rate
    report = dict(schema='vsl.osc-quality/1', question='Untransposed original64 sounds downsampled/compressed; investigate before HF tuning.',
        source=source, historical_source=provenance, explicit_historical_mono=True,
        exterior_provenance=ext_provenance, no_runtime_changes=True,
        formats={}, variants={}, controls={})
    protected = [legacy_path, ROOT/'references/analysis/oscillator_experiment/A_road_osc_64_rms_matched.wav',
        ROOT/'references/analysis/oscillator_experiment/A_road_reference_rms_matched.wav',
        ROOT/'baselines/reference_osc_v2/manifest.json']
    report['preserved_before'] = {str(p.relative_to(ROOT)):sha(p) for p in protected}
    for p in [*protected[:3], ROOT/'references/analysis/reference_osc_v2/base_float.wav']:
        info = sf.info(p)
        report['formats'][str(p.relative_to(ROOT))] = dict(rate=info.samplerate, frames=info.frames, duration=info.duration, channels=info.channels, subtype=info.subtype)

    observed = frames(x, rate)
    arrays = {'reference':x}
    for name, count, gated in [('legacy64', 64, False), ('gated64', 64, True), ('gated128', 128, True)]:
        y, stats = synthesize(x, rate, observed, count=count, gated=gated)
        if name == 'legacy64':
            assert abs(y-baseline[:, 0]).max() < 1e-7
        arrays[name] = y
        report['variants'][name] = dict(tracks=stats, residual_db=relative_error(x, y, rate), spectrum=spectral_diagnostics(x, y, rate))
        print(name, 'residual', report['variants'][name]['residual_db'], 'births', stats['births'], flush=True)
    short = frames(x, rate, window=1024, maximum=64)
    y, stats = synthesize(x, rate, short, gated=True)
    arrays['short64'] = y
    report['variants']['short64'] = dict(tracks=stats, window=1024,
        confounds='Original detector at smaller window also increases minimum peak separation in Hz; diagnostic temporal control, not a selected full-engine algorithm.',
        residual_db=relative_error(x, y, rate), spectrum=spectral_diagnostics(x, y, rate))
    # Same passband, preserve full recording texture. No peak pruning/tracking.
    taps = signal.firwin(1025, [80, 14000], pass_zero=False, fs=rate, window=('kaiser', 12))
    arrays['band_only'] = signal.fftconvolve(x, taps, mode='same')
    report['variants']['band_only'] = dict(residual_db=relative_error(x, arrays['band_only'], rate),
        method='Linear-phase FIR80-14000Hz, delay compensated offline. Full recording reference control, not an oscillator runtime or new voice.',
        spectrum=spectral_diagnostics(x, arrays['band_only'], rate))
    dump(OUT/'progress.json', dict(stage='real-clip controls completed'))

    # Known truths expose time-resolution losses without engine/source ambiguity.
    seconds = 3
    t = np.arange(seconds*rate)/rate
    controls = {}
    for mod in [3, 25]:
        controls[f'am{mod}'] = ((.15+.1*np.cos(2*np.pi*mod*t))*np.cos(2*np.pi*223.7*t+.3)
            +.07*np.cos(2*np.pi*791.3*t-.4), 223.7, mod)
    phi = np.arange(32)*.37
    controls['stationary32'] = (sum(.12/(n**1.2)*np.cos(2*np.pi*n*190.3*t+phi[n-1]) for n in range(1, 33)), None, None)
    controls['chirp32'] = (sum(.12/(n**1.2)*np.cos(2*np.pi*n*(190.3*t+15*t*t)+phi[n-1]) for n in range(1, 33)), None, None)
    for name, (audio, carrier, mod) in controls.items():
        result = {}
        for window in [4096, 1024]:
            observations = frames(audio, rate, window=window, maximum=64)
            z, stats = synthesize(audio, rate, observations, gated=True)
            result[str(window)] = dict(residual_db=relative_error(audio, z, rate), stats=stats)
            if carrier:
                original_am = modulation_amplitude(audio, rate, carrier, mod)
                reconstructed_am = modulation_amplitude(z, rate, carrier, mod)
                result[str(window)]['retained_known_AM_db'] = float(20*np.log10(max(reconstructed_am, 1e-30)/original_am))
        report['controls'][name] = result
        print('known', name, {k:round(v['residual_db'], 3) for k, v in result.items()}, flush=True)
    dump(OUT/'progress.json', dict(stage='known signal controls completed'))

    # Actual original64 source oscillator oversampling, not event-source proxy.
    original_model = ROOT/'references/analysis/reference_osc_v1/archive64.model'
    frozen_v1 = json.loads((ROOT/'references/analysis/reference_osc_v1/verification.json').read_text())
    assert sha(original_model) == frozen_v1['artifacts']['archive64.model']
    model4 = OUT/'alias4x.model'
    with original_model.open() as old, model4.open('w', encoding='ascii', newline='\n') as new:
        header = old.readline().split()
        new.write(f'VSL_REFERENCE_OSC 1 {rate*4} {len(x)*4} {header[4]}\n')
        for _ in range(int(header[4])):
            start, length, count = map(int, old.readline().split())
            new.write(f'{start*4} {length*4} {count}\n')
            for _ in range(count):
                new.write(old.readline())
    command = [str(PROBE), str(model4), str(OUT/'alias4x_float.wav'), str(OUT/'alias4x_unused_high.wav'), '0']
    process = subprocess.run(command, check=True, capture_output=True, text=True, timeout=120)
    high_rate, sr = sf.read(OUT/'alias4x_float.wav', always_2d=True)
    assert sr == rate*4 and np.array_equal(high_rate[::4], baseline)
    fir = signal.firwin(1025, .24, window=('kaiser', 14))
    reduced = signal.resample_poly(high_rate[:, 0], 1, 4, window=fir)
    report['aliasing'] = dict(rate=rate, oversampled_rate=sr,
        every_fourth_oversampled_sample_exact_native=True, decimator='1025tap Kaiser14 cutoff.24 of192k Nyquist',
        difference_to_native_db=relative_error(baseline[:, 0], reduced, rate), log=process.stdout.strip(),
        caution='Difference includes residual antialias filter error and non-bandlimited AM/phase joins; not an isolated proof that every residual is aliasing.')
    # One old gain for all real-clip controls. Original assets never overwritten.
    gain = json.loads((ROOT/'references/analysis/reference_osc_v2/results.json').read_text(encoding='utf-8'))['gain']
    report['audition'] = dict(gain=gain, gain_db=float(20*np.log10(gain)), files={},
        processing='Shared original64 gain,512-sample endpoint ramps,PCM24; no per-version normalization/compressor/limiter. Reference is explicit historical mono.')
    for name, audio in arrays.items():
        value = audio*gain
        value[:512] *= np.linspace(0, 1, 512)
        value[-512:] *= np.linspace(1, 0, 512)
        assert abs(value).max() < .95
        path = OUT/f'{name}_audition.wav'
        sf.write(path, value, rate, subtype='PCM_24')
        report['audition']['files'][name] = dict(file=path.name, sha256=sha(path))
    report['preserved_after'] = {str(p.relative_to(ROOT)):sha(p) for p in protected}
    assert report['preserved_before'] == report['preserved_after']
    dump(OUT/'results.json', report)
    print('Quality diagnostics completed. Oversampling difference:', report['aliasing']['difference_to_native_db'], flush=True)


if __name__ == '__main__':
    main()
