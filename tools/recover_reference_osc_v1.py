"""Versioned archive recovery and material-derived stereo OSC C transfer.

Run only into a new directory. Never modifies early demos or native releases.
"""
from runtime_review import ROOT, sha
import json
from pathlib import Path
import subprocess
import numpy as np
import soundfile as sf
from reference_segments import read_segment
from reference_osc_v1.exporter import fit, write_model, Settings
from reference_osc_v1.observations import compare, describe
from sinusoidal_experiment import synthesize

OUT = ROOT/'references/analysis/reference_osc_v1'
PROBE = ROOT/'build-reference-osc-v1/Release/reference_osc_probe.exe'


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')


def render(model, name, amount):
    output, high = OUT/f'{name}_c_float.wav', OUT/f'{name}_high_float.wav'
    done = subprocess.run([str(PROBE), str(model), str(output), str(high), str(amount)],
        check=True, capture_output=True, text=True, timeout=120)
    y, rate = sf.read(output, always_2d=True)
    return y, dict(log=done.stdout.strip(), file=output.name, sha256=sha(output), sample_rate=rate)


def shared_audition(name, arrays, rate):
    """One gain for all options within an excerpt; never boosts HF independently."""
    gain = min(.5, .85/max(float(abs(x).max()) for x in arrays.values()))
    files = {}
    for key, x in arrays.items():
        y = x*gain
        ramp = min(round(.005*rate), len(y)//4)
        y[:ramp] *= np.linspace(0, 1, ramp)[:, None]
        y[-ramp:] *= np.linspace(1, 0, ramp)[:, None]
        target = OUT/f'{name}_{key}_audition.wav'
        sf.write(target, y, rate, subtype='PCM_24')
        files[key] = dict(file=target.name, sha256=sha(target))
    return dict(gain_db=float(20*np.log10(gain)), files=files,
        processing='One shared gain <= -6.0206 dB, 5 ms endpoint fades, PCM24. No RMS matching, denoising, compression or filtering. No independent HF normalization.')


def main():
    OUT.mkdir(exist_ok=False)
    report = dict(schema='vsl.reference-osc-review/1', native_release_changed=False,
        probe_sha256=sha(PROBE), runtime='Portable C11 AM/FM/cubic phase oscillators. No source PCM playback, event trigger, wavetable or noise generator.',
        scope='Fitted timed coefficient trajectories. No arbitrary RPM/load/gear synthesis or physical bank identification claimed.', excerpts={})
    preserved = [ROOT/'research/试听对照.html', ROOT/'research/立体声OSC试听.html',
        ROOT/'renders/v10_pure_osc.wav', ROOT/'renders/v10_three_layers.wav']
    archive = ROOT/'references/analysis/oscillator_experiment'
    preserved += [archive/f'A_road_{key}_rms_matched.wav' for key in ['reference', 'osc_16', 'osc_64']]
    report['preserved_before'] = {str(p.relative_to(ROOT)):sha(p) for p in preserved}

    # Archival identity only: old mono clip includes a pre-316s cabin cut.
    historical = ROOT/'references/clean/A_tailpipe_road_pull.wav'
    stereo, rate = sf.read(historical, always_2d=True)
    mono = stereo.mean(axis=1)
    base, segments, stats = fit(mono, rate, legacy=True)
    oracle = synthesize(mono, rate, 64)
    assert np.array_equal(base[:, 0], oracle), 'Legacy tracker/oracle mismatch'
    model = OUT/'archive64.model'
    representation = write_model(model, rate, len(base), segments)
    c, transfer = render(model, 'archive64', 0)
    error = float(abs(c-base).max())
    assert error < 1e-7, error
    # Recover the exact original gain law without changing original files.
    original16 = synthesize(mono, rate, 16)
    central = slice(rate//5, -rate//5)
    normalized = [x*10**(-23/20)/np.sqrt(np.mean(x[central]**2)) for x in [mono, original16, oracle]]
    common = min(1, .85/max(float(abs(x).max()) for x in normalized))
    gain = 10**(-23/20)/np.sqrt(np.mean(oracle[central]**2))*common
    y = c[:, 0]*gain
    y[:512] *= np.linspace(0, 1, 512)
    y[-512:] *= np.linspace(1, 0, 512)
    recovered = OUT/'archive64_c_original_gain.wav'
    sf.write(recovered, y, rate, subtype='PCM_24')
    decoded, _ = sf.read(recovered)
    original, _ = sf.read(archive/'A_road_osc_64_rms_matched.wav')
    archive_error = float(abs(decoded-original).max())
    assert archive_error <= 2/8388608, archive_error
    report['archive'] = dict(source=str(historical.relative_to(ROOT)), source_sha256=sha(historical),
        processing='Historical stereo mean for identity recovery only. Includes cabin cut; not used for new exterior calibration.',
        stats=stats, representation=representation, c_transfer=transfer, max_float_error=error,
        max_original_pcm24_error=archive_error, recovered_file=recovered.name,
        recovered_sha256=sha(recovered))
    dump(OUT/'progress.json', dict(stage='archive C parity passed', max_original_pcm24_error=archive_error))
    print('Archive64 recovered; maximum original PCM24 difference:', archive_error, flush=True)

    for name, segment, use in [
        ('low', 'A_exterior_low_rev', 'exterior_spectral_observation'),
        ('blips', 'A_exterior_blips', 'exterior_dynamic_observation'),
        ('moving', 'A_exterior_moving', 'exterior_dynamic_observation')]:
        x, rate, provenance = read_segment(segment, use)
        base, base_segments, base_stats = fit(x, rate)
        high, high_segments, high_stats = fit(x-base, rate, count=24, group=1,
            settings=Settings(window=2048, lower_hz=3000))
        model = OUT/f'{name}.model'
        representation = write_model(model, rate, len(x), base_segments, high_segments)
        c_base, transfer_base = render(model, name+'_base', 0)
        c_high, transfer_high = render(model, name+'_high35', .35)
        float_error = float(max(abs(c_base-base).max(), abs(c_high-(base+.35*high)).max()))
        assert float_error < 1e-7, float_error
        # Diagnostic bypass proof: amount0 is exactly the independently rendered base.
        files = shared_audition(name, dict(reference=x, base=c_base, high35=c_high), rate)
        report['excerpts'][name] = dict(provenance=provenance, base_stats=base_stats,
            high_stats=high_stats, representation=representation, max_c_float_error=float_error,
            transfer_base=transfer_base, transfer_high=transfer_high, audition=files,
            base_comparison=compare(x, base, rate), high35_comparison=compare(x, base+.35*high, rate),
            high_source='OSC tracking of x-base residual, 3-14 kHz detector range, 2048 Hann,24 support. Residual is NOT a separated noise/engine source; AM/FM may produce sidebands beyond detection range.',
            base_unchanged='Combined output = identical base + .35 * separately fitted high OSC. No base EQ/phase/gain replacement.')
        dump(OUT/'progress.json', dict(stage=name+' complete'))
        print(name, 'C parity:', float_error, 'support:', base_stats['mean_detected_support'], flush=True)

    # Separate Tecnica observation, not exterior calibration or bank extraction.
    cabin, rate, provenance = read_segment('B_cabin_pull', 'interior_channel_observation')
    report['cabin_observation'] = dict(provenance=provenance, measurements=describe(cabin, rate),
        interpretation='A Performante exterior and B Tecnica cabin differ in vehicle, recording position, transfer and driving. These recordings cannot isolate the engine-design difference. Cabin not mixed into exterior coefficients.')
    report['preserved_after'] = {str(p.relative_to(ROOT)):sha(p) for p in preserved}
    assert report['preserved_before'] == report['preserved_after']
    dump(OUT/'results.json', report)
    print('All archive preservation and C transfer checks passed.', flush=True)


if __name__ == '__main__':
    main()
