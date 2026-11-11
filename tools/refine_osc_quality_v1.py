"""Targeted quality candidate following the initial diagnostic controls."""
from runtime_review import ROOT, sha
import json
import numpy as np
import soundfile as sf
from osc_quality_v1.fitting import frames, synthesize
from osc_quality_v1.refine import refine
from osc_quality_v1.metrics import relative_error, modulation_amplitude, spectral_diagnostics

OUT = ROOT/'references/analysis/osc_quality_v1/refinement'


def main():
    OUT.mkdir(exist_ok=False)
    input_path = ROOT/'references/clean/A_tailpipe_road_pull.wav'
    x, rate = sf.read(input_path, always_2d=True)
    x = x.mean(axis=1)  # Explicit archival mono processing-quality diagnostic.
    observations = frames(x, rate, maximum=64)
    refined, stats = refine(x, rate, observations)
    for old, new in zip(observations, refined):
        assert old[0] == new[0] and np.array_equal(old[1][:, 0], new[1][:, 0])
    y, tracking = synthesize(x, rate, refined, gated=True)
    report = dict(schema='vsl.osc-quality-refinement/1', input_sha256=sha(input_path),
        fit=stats, tracking=tracking, residual_db=relative_error(x, y, rate),
        spectrum=spectral_diagnostics(x, y, rate), controls={})
    gain = json.loads((ROOT/'references/analysis/reference_osc_v2/results.json').read_text(encoding='utf-8'))['gain']
    value = y*gain
    value[:512] *= np.linspace(0, 1, 512)
    value[-512:] *= np.linspace(1, 0, 512)
    assert np.isfinite(value).all() and abs(value).max() < .95
    sf.write(OUT/'joint64_audition.wav', value, rate, subtype='PCM_24')
    sf.write(OUT/'joint64_float.wav', y, rate, subtype='FLOAT')
    report['audition'] = dict(file='joint64_audition.wav', sha256=sha(OUT/'joint64_audition.wav'), gain=gain,
        processing='Same old64 gain/512sample ramps/PCM24; no per-version RMS adjustment, compressor or limiter.')
    print('Real clip refined:', report['residual_db'], 'peak', abs(value).max(), flush=True)
    t = np.arange(3*rate)/rate
    phi = np.arange(32)*.37
    controls = {
        'am25':((.15+.1*np.cos(2*np.pi*25*t))*np.cos(2*np.pi*223.7*t+.3)+.07*np.cos(2*np.pi*791.3*t-.4), 223.7, 25),
        'stationary32':(sum(.12/(n**1.2)*np.cos(2*np.pi*n*190.3*t+phi[n-1]) for n in range(1, 33)), None, None),
        'chirp32':(sum(.12/(n**1.2)*np.cos(2*np.pi*n*(190.3*t+15*t*t)+phi[n-1]) for n in range(1, 33)), None, None)}
    for name, (audio, carrier, modulation) in controls.items():
        observed = frames(audio, rate, maximum=64)
        updated, fit_stats = refine(audio, rate, observed)
        rendered, _ = synthesize(audio, rate, updated, gated=True)
        v = dict(residual_db=relative_error(audio, rendered, rate), fit=fit_stats)
        if carrier:
            v['retained_known_AM_db'] = float(20*np.log10(modulation_amplitude(rendered, rate, carrier, modulation)/modulation_amplitude(audio, rate, carrier, modulation)))
        report['controls'][name] = v
        print('known refined', name, v['residual_db'], flush=True)
    (OUT/'results.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')


if __name__ == '__main__':
    main()
