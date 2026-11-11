"""Independent convolution check of saved C exhaust source objects."""
import json
from runtime_review import ROOT, sha, rms
import numpy as np
import soundfile as sf
from scipy.signal import fftconvolve

OUT = ROOT / 'renders/exhaust_phase_v1'


def read(name):
    x, rate = sf.read(OUT / name, always_2d=True)
    assert rate == 48000 and np.isfinite(x).all(), name
    return x


def measure():
    primary = json.loads((OUT / 'results.json').read_text(encoding='utf-8'))
    rows = {}
    for case in primary['cases']:
        rows[case] = {}
        baseline_mix = read(f'{case}_base.wav')
        for tag in ['delay', 'mild', 'strong']:
            impulse = read(f'impulse_48000_{tag}.wav')[:, 0]
            result = {}
            for bank in ['exhaust_left', 'exhaust_right']:
                baseline = read(f'{case}_base_source_{bank}.wav')[:, 0]
                actual = read(f'{case}_{tag}_source_{bank}.wav')[:, 0]
                # C serial double-precision filtering is compared to a separate
                # FFT convolution of float32-quantized source and impulse files.
                expected = fftconvolve(baseline, impulse)[:len(baseline)]
                error = actual - expected
                maximum = float(np.max(np.abs(error)))
                relative = rms(error) - rms(actual)
                assert maximum < 2e-7 and relative < -115, (case, tag, bank, maximum, relative)
                if tag == 'delay':
                    assert np.array_equal(actual[:48], np.zeros(48))
                    assert np.array_equal(actual[48:], baseline[:-48])
                result[bank] = dict(
                    maximum_absolute_convolution_error=maximum,
                    convolution_error_to_actual_db=relative,
                    whole_file_rms_change_db=rms(actual)-rms(baseline),
                    source_sha256=sha(OUT/f'{case}_{tag}_source_{bank}.wav'))
            actual_mix = read(f'{case}_{tag}.wav')
            result['mix'] = dict(whole_file_rms_change_db=rms(actual_mix)-rms(baseline_mix),
                                peak=float(np.max(np.abs(actual_mix))))
            rows[case][tag] = result
    return dict(result='pass', primary_results_sha256=sha(OUT/'results.json'),
                independent_convolution_comparisons=7*3*2, sample_rate=48000,
                method='FFT convolution of baseline float32 source files with C measured float32 impulse response; compare actual candidate source files. Truncate only after convolution at original file end.',
                tolerance='Maximum absolute error <2e-7 and error/actual power <-115 dB; allows float32 input/impulse/output quantization.',
                delay_control='Both banks are exactly 48 samples delayed in exported float32 sources.',
                interpretation='Unity magnitude applies to isolated stationary exhaust sources. Finite-window RMS and complete mixes can change through transients, layer interference, and the existing DNA-driven IR return. This does not measure realism or new cycle variability.',
                cases=rows)


def main():
    path = OUT / 'independent_convolution.json'
    if path.exists():
        raise SystemExit('Preserve completed independent convolution evidence.')
    result = measure()
    path.write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
    maximum = max(row[bank]['maximum_absolute_convolution_error']
                  for case in result['cases'].values() for row in case.values()
                  for bank in ['exhaust_left', 'exhaust_right'])
    print(json.dumps(dict(result='pass', comparisons=42, maximum_absolute_error=maximum), indent=2))


if __name__ == '__main__':
    main()
