"""Add residual-band accounting without re-running unchanged oscillator fits.

The original fit metrics remain authoritative. Here audition PCM24 is divided
by its recorded scalar gains; central-window quantization error is checked
against those metrics. This cannot reconstruct the deliberately faded edges.
"""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal
from osc_research.metrics import power_db

OUT = ROOT/'references/analysis/joint_stereo_v1'
BANDS = [(0, 28), (28, 80), (80, 400), (400, 1200), (1200, 3000),
         (3000, 8000), (8000, 14000), (14000, 24001)]


def read_source(case):
    with sf.SoundFile(ROOT/case['master']) as f:
        sr = f.samplerate
        lo, hi = case['source_seconds']
        f.seek(round(lo*sr))
        return f.read(round((hi-lo)*sr), always_2d=True), sr


def powers(x, sr):
    f, p = signal.welch(x, sr, nperseg=8192, axis=0, detrend=False)
    return f, p.mean(axis=1)


def main():
    original = OUT/'results.json'
    report = json.loads(original.read_text(encoding='utf-8'))
    diagnostics = dict(input_results_sha256=hashlib.sha256(original.read_bytes()).hexdigest(),
        tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        method='8192-frame Welch mean channel powers on central original reference and gain-reversed PCM24 audition derivatives. No filtering or source separation. Band accounting includes frequencies excluded by the 80Hz..14kHz estimator.',
        reconstruction_precision='Original scalar waveform residual must match PCM24-derived residual within 0.002dB; endpoint fades are excluded.',
        limits='Band residual includes all estimator errors and source interference; it is not physical stochastic sound. Near-zero side or reference-band energy makes relative errors unstable.',
        cases={})
    for name, case in report['cases'].items():
        x, sr = read_source(case)
        trim = round(.2*sr)
        x = x[trim:-trim]
        f, px = powers(x, sr)
        bands = []
        for lo, hi in BANDS:
            mask = (f >= lo) & (f < hi)
            bands.append(dict(hz=[lo, hi], reference_power_fraction=float(px[mask].sum()/px.sum()),
                              reference_band_dbfs=power_db(px[mask].sum()*sr/8192, 1)))
        methods = {}
        for key, method in case['methods'].items():
            item = case['auditions'][key]
            y, rate = sf.read(ROOT/item['file'], always_2d=True)
            assert sr == rate
            y = y[trim:-trim]/(item['rms_gain']*item['shared_headroom_gain'])
            error = x-y
            error_db = power_db(np.mean(error*error), np.mean(x*x))
            assert abs(error_db-method['metrics']['relative_waveform_residual_db']) < .002, (name, key)
            _, pe = powers(error, sr)
            rows = []
            for lo, hi in BANDS:
                mask = (f >= lo) & (f < hi)
                rows.append(dict(hz=[lo, hi],
                    residual_relative_to_reference_band_db=power_db(pe[mask].sum(), px[mask].sum()),
                    residual_fraction_of_full_reference=float(pe[mask].sum()/px.sum())))
            modeled = (f >= 80) & (f < 14000)
            methods[key] = dict(central_waveform_residual_db=error_db, bands=rows,
                modeled_band_residual_db=power_db(pe[modeled].sum(), px[modeled].sum()))
        diagnostics['cases'][name] = dict(reference_bands=bands, methods=methods)
        print(name, 'reference below 80Hz', round(sum(b['reference_power_fraction'] for b in bands[:2])*100, 1),
              '%, joint modeled-band residual dB', round(methods['joint64']['modeled_band_residual_db'], 2))
    (OUT/'band_accounting.json').write_text(json.dumps(diagnostics, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
