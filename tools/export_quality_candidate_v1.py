"""Transfer the same quality candidate to the unchanged C oscillator core."""
from runtime_review import ROOT, sha
import json
import subprocess
import numpy as np
import soundfile as sf
from scipy import signal
from osc_quality_v1.fitting import frames, synthesize, export_model
from osc_quality_v1.refine import refine
from osc_quality_v1.metrics import relative_error


def main():
    out = ROOT/'references/analysis/osc_quality_v1/refinement'
    model = out/'joint64.model'
    if model.exists():
        raise SystemExit('Preserve exported candidate; do not overwrite.')
    audio, rate = sf.read(ROOT/'references/clean/A_tailpipe_road_pull.wav', always_2d=True)
    x = audio.mean(axis=1)
    observed = frames(x, rate, maximum=64)
    refined, _ = refine(x, rate, observed)
    reference, _ = synthesize(x, rate, refined, gated=True)
    previous, previous_rate = sf.read(out/'joint64_float.wav')
    assert previous_rate == rate and abs(previous-reference).max() < 1e-7
    representation = export_model(model, rate, len(x), refined)
    probe = ROOT/'build-reference-osc-v1/Release/reference_osc_probe.exe'
    def render(path, name):
        target = out/f'{name}_float.wav'
        process = subprocess.run([str(probe), str(path), str(target), str(out/f'{name}_unused_high.wav'), '0'],
            check=True, capture_output=True, text=True, timeout=120)
        value, sr = sf.read(target, always_2d=True)
        return value, sr, process.stdout.strip()
    c, sr, log = render(model, 'joint64_c')
    error = float(abs(c[:, 0]-reference).max())
    assert sr == rate and error < 1e-7
    gain = json.loads((ROOT/'references/analysis/reference_osc_v2/results.json').read_text(encoding='utf-8'))['gain']
    audition = c[:, 0]*gain
    audition[:512] *= np.linspace(0, 1, 512)
    audition[-512:] *= np.linspace(1, 0, 512)
    sf.write(out/'joint64_c_audition.wav', audition, rate, subtype='PCM_24')
    original, _ = sf.read(out/'joint64_audition.wav')
    decoded, _ = sf.read(out/'joint64_c_audition.wav')
    pcm_error = float(abs(decoded-original).max())
    assert pcm_error <= 2/8388608
    model4 = out/'joint64_4x.model'
    with model.open() as source, model4.open('w', encoding='ascii', newline='\n') as dest:
        header = source.readline().split()
        dest.write(f'VSL_REFERENCE_OSC 1 {rate*4} {len(x)*4} {header[4]}\n')
        for _ in range(int(header[4])):
            start, length, count = map(int, source.readline().split())
            dest.write(f'{start*4} {length*4} {count}\n')
            for _ in range(count):
                dest.write(source.readline())
    high_rate, sr, log4 = render(model4, 'joint64_4x')
    assert sr == rate*4 and np.array_equal(high_rate[::4], c)
    down = signal.resample_poly(high_rate[:, 0], 1, 4, window=signal.firwin(1025, .24, window=('kaiser', 14)))
    result = dict(result='pass', probe_sha256=sha(probe), model_sha256=sha(model),
        representation=representation, max_C_float_error=error, max_audition_pcm24_error=pcm_error,
        logs=[log, log4], alias_4x_difference_db=relative_error(c[:, 0], down, rate),
        phase_stride_exact=True, runtime_changed=False, audition_sha256=sha(out/'joint64_c_audition.wav'),
        subjective_quality_accepted=False)
    (out/'c_verification.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
