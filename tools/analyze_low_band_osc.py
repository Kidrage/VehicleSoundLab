"""One-parameter ablation after explicit out-of-band error accounting.

Keep the established shared stereo estimator and trajectory budget; extend
candidate support from 80Hz to 28Hz. Do not retune individual real excerpts.
"""
from dataclasses import asdict
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools/python_deps'))
import numpy as np
import soundfile as sf
from osc_research.tracker import Settings, synthesize
from osc_research.metrics import measure, compare, power_db
from finalize_joint_stereo import read_source, powers, BANDS

OUT = ROOT/'references/analysis/joint_stereo_v1'
SETTINGS = Settings(lower_hz=28)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def known_low_control():
    sr = 48000
    t = np.arange(2*sr)/sr
    x = np.column_stack((.2*np.cos(2*np.pi*43.37*t+.2)+.08*np.cos(2*np.pi*176.19*t-.7),
                         .18*np.cos(2*np.pi*43.37*t+.43)+.07*np.cos(2*np.pi*176.19*t-.95)))
    full, _ = synthesize(x, sr, 64, SETTINGS)
    missing, _ = synthesize(x, sr, 64, Settings())
    exact = measure(full, sr, x)
    assert exact['relative_waveform_residual_db'] < -45, exact
    # Selection by summed powers and interpolation must commute with L/R swap.
    swapped, _ = synthesize(x[:, ::-1], sr, 64, SETTINGS)
    swap_error = float(np.max(abs(swapped[:, ::-1]-full)))
    assert swap_error < 1e-12
    return dict(reference=measure(x, sr), low28=exact, low80=measure(missing, sr, x),
                lr_swap_max_error=swap_error,
                scope='Known stationary stereo tones, including a coherent 43.37Hz tone. No realism claim.')


def main():
    original = OUT/'results.json'
    base = json.loads(original.read_text(encoding='utf-8'))
    report = dict(schema='vsl.osc-low-band-ablation/1',
        original_results_sha256=sha(original), settings=asdict(SETTINGS),
        oscillator_budget='64 shared frequencies; independent complex L/R gains; at most 128 channel oscillator outputs, same as joint64 baseline.',
        reason='Exploratory band accounting showed 20-30% of these B excerpts below 80Hz. This follow-up is exploratory; all six A/B excerpts receive the same fixed setting.',
        controls=known_low_control(),
        limits='Fits each excerpt to itself. Does not label low frequencies as engine-only, noise or a measured physical layer. A/B perspectives remain separate. No procedural runtime changes.',
        tools={str(p.relative_to(ROOT)): sha(p) for p in [Path(__file__),
            ROOT/'tools/osc_research/tracker.py', ROOT/'tools/osc_research/metrics.py']}, cases={})
    for name, case in base['cases'].items():
        x, sr = read_source(case)
        assert sha(ROOT/case['master']) == base['sources'][case['source']]['sha256']
        y, stats = synthesize(x, sr, 64, SETTINGS)
        metrics = measure(y, sr, x)
        trim = round(.2*sr)
        f, px = powers(x[trim:-trim], sr)
        _, pe = powers((x-y)[trim:-trim], sr)
        bands = []
        for lo, hi in BANDS:
            mask = (f >= lo) & (f < hi)
            bands.append(dict(hz=[lo, hi],
                residual_relative_to_reference_band_db=power_db(pe[mask].sum(), px[mask].sum()),
                residual_fraction_of_full_reference=float(pe[mask].sum()/px.sum())))
        gain = 10**(-23/20)/np.sqrt(np.mean(y[trim:-trim]**2))
        common = case['auditions']['reference']['shared_headroom_gain']
        audition = y*gain*common
        assert np.max(abs(audition)) < .95, 'Rebuild a common-headroom audition set before adding this take.'
        ramp = np.linspace(0, 1, 240)
        audition[:240] *= ramp[:, None]
        audition[-240:] *= ramp[::-1, None]
        file = OUT/f'{name}_joint64_low28_rms_matched.wav'
        sf.write(file, audition, sr, subtype='PCM_24')
        report['cases'][name] = dict(metrics=metrics, band_errors=compare(case['reference'], metrics),
            residual_bands=bands, tracking=stats,
            audition=dict(file=str(file.relative_to(ROOT)), sha256=sha(file),
                rms_gain=float(gain), shared_headroom_gain=common,
                processing='Same -23dBFS central stereo RMS target and shared peak scalar as the existing case; 5ms endpoint fades; PCM24. Not LUFS.'))
        print(name, 'residual dB', round(metrics['relative_waveform_residual_db'], 2),
              'S/M dB', round(metrics['side_to_mid_db'], 2), flush=True)
    (OUT/'low_band_extension.json').write_text(json.dumps(report, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
