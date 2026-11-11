"""Actual exterior overlap: normalized fast envelope agreement by carrier band."""
from runtime_review import ROOT
import json
import numpy as np
import soundfile as sf
from scipy import signal


def main():
    out = ROOT/'references/analysis/osc_quality_v1'
    paths = {'recording':out/'reference_audition.wav', 'old64':out/'legacy64_audition.wav',
             'joint64':out/'refinement/joint64_c_audition.wav'}
    arrays = {k:sf.read(path)[0] for k, path in paths.items()}
    rate, envelope_rate = 48000, 500
    valid = slice(round(2.6*envelope_rate), round(5.8*envelope_rate))
    result = dict(scope='Archival exterior overlap2.6..5.8 seconds; normalized band envelopes. Includes beating/source/noise/space; not isolated combustion modulation.', bands={})
    for lo, hi in [(80, 400), (400, 1200), (1200, 3000), (3000, 8000)]:
        modulations = {}
        for name, x in arrays.items():
            carrier = signal.sosfiltfilt(signal.butter(4, [lo, hi], btype='bandpass', fs=rate, output='sos'), x)
            envelope = signal.resample_poly(abs(signal.hilbert(carrier)), 1, 96)
            envelope = envelope/max(np.mean(envelope[valid]), 1e-12)-1
            modulations[name] = {f'{a}-{b}':signal.sosfiltfilt(signal.butter(4, [a, b], btype='bandpass', fs=envelope_rate, output='sos'), envelope)[valid]
                for a, b in [(10, 40), (40, 80)]}
        result['bands'][f'{lo}-{hi}'] = {}
        for modband, reference in modulations['recording'].items():
            result['bands'][f'{lo}-{hi}'][modband] = {name:dict(
                normalized_envelope_error_db=float(10*np.log10(np.mean((reference-values[modband])**2)/max(np.mean(reference**2), 1e-30))),
                correlation=float(np.corrcoef(reference, values[modband])[0, 1]),
                modulation_power_ratio_db=float(10*np.log10(max(np.mean(values[modband]**2), 1e-30)/max(np.mean(reference**2), 1e-30))))
                for name, values in modulations.items() if name != 'recording'}
    (out/'temporal_observations.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    for band, observations in result['bands'].items():
        print(band, {k:{name:round(v['correlation'], 3) for name, v in values.items()} for k, values in observations.items()})


if __name__ == '__main__':
    main()
