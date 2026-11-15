"""Separate waveform, rounded-frame and calibration effects on a failed audit.

Read existing controls/capture only. No fit, gate change, admission or new voice.
"""
import argparse
import os
from pathlib import Path
import shutil
import sys
from itertools import product
from research_archive_v1 import load, save, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'known', 'case', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(args.workspace / 'tools/python_deps'))
    import numpy as np
    from observer_complete_v1.audit_oracle import full_frame
    from observer_frequency_v1.reduced_oracle import synthesize
    from observer_supported_v1.audit_oracle import metric

    args.out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, args.out / 'executed_diagnosis.py')
    report = dict(result='running', cases=[], inputs={}, no_fit_or_source_mutation=True)

    def bind(path):
        report['inputs'][str(path)] = sha(path)
        return load(path)

    def declared_frame(audio):
        """Explicit per-window FFT; prescribed FP64 window and input order.

        This deliberately represents the declared rounded measurement operator;
        its agreement is not a universal bound on two different FFT operators.
        """
        count = len(audio)
        starts = range(-3840, count, 256)
        window = .5 - .5*np.cos(2*np.pi*np.arange(4096)/4096)
        coverage = np.zeros(count)
        for start in starts:
            lo, hi = max(start, 0), min(start+4096, count)
            coverage[lo:hi] += window[lo-start:hi-start]**2
        normalizer = 1/np.sqrt(coverage)
        endpoint = np.full(2049, np.sqrt(2.))
        endpoint[[0, -1]] = 1.
        rows = []
        for start in starts:
            lo, hi = max(start, 0), min(start+4096, count)
            samples = np.zeros((4096, 2))
            samples[lo-start:hi-start] = audio[lo:hi]*normalizer[lo:hi, None]
            samples *= window[:, None]
            rows.append(np.column_stack([np.fft.rfft(samples[:, c])*endpoint/64 for c in (0, 1)]))
        return np.asarray(rows), coverage

    def scores(audio, wave, profile, frame):
        def supported(samples):
            rows, _ = frame(samples)
            starts = np.arange(-3840, len(samples), 256)
            keep = (starts >= 0) & (starts+4096 <= len(samples))
            return rows[keep]*profile['amplitude']*profile['weights'][None, :, None]
        def ratio(numerator, denominator):
            scale = float(np.linalg.norm(denominator))
            return float(np.linalg.norm(numerator)/scale) if scale else (0. if not np.count_nonzero(numerator) else None)
        error = wave-audio
        rows, reference = supported(error), supported(audio)
        target_rows, target_reference = supported(error[2048:-2048]), supported(audio[2048:-2048])
        bands = np.searchsorted([3000, 6000, 8000, 10000, 14000], np.arange(2049)*16, side='right')
        return dict(whole_wave_NRMSE=ratio(error, audio),
            target_wave_NRMSE=ratio(error[2048:-2048], audio[2048:-2048]),
            target_supported_band_complex_NRMSE=[ratio(target_rows[:, bands == b], target_reference[:, bands == b]) for b in range(6)],
            whole_supported_band_complex_NRMSE=[ratio(rows[:, bands == b], reference[:, bands == b]) for b in range(6)],
            whole_wave_regions_NRMSE=[ratio(error[part], audio[part]) for part in (slice(0, 2048), slice(2048, -2048), slice(-2048, None))])

    try:
        known = bind(args.known / 'report.json')
        assert known['result'] == 'locked_source_fit_known_measured' and known['all_qualified']
        source_root = args.case.parent
        spec = bind(source_root / 'run_spec.json')
        assert spec['declared_cases'] == [args.case.name] and spec['only_one_finite_case']
        assert bind(source_root / 'report.json')['result'] == 'failed'
        original_audit = bind(source_root / (args.case.name + '_audit') / 'report.json')
        assert original_audit['result'] == 'failed'
        directories = [args.known / row['label'] for row in known['cases'] if row['label'] != 'both_zero']
        directories.append(args.case)
        for directory in directories:
            source = bind(directory / 'report.json')
            assert sha(directory / 'capture.npz') == source['capture_sha256']
            report['inputs'][str(directory / 'capture.npz')] = source['capture_sha256']
            with np.load(directory / 'capture.npz') as saved:
                z = {name: saved[name] for name in saved.files}
            old = metric(z['metric_target'], 64.)
            frozen = dict(old, amplitude=float(z['amplitude']), weights=z['weights'])
            scalar = synthesize(z['fitted'], z['positions'], z['orders'], len(z['audio']))
            row = dict(label=directory.name, known_control=directory != args.case,
                waveform_max_difference_FS=float(np.max(abs(scalar-z['wave']))),
                variants={}, producer_fidelity_qualified=source['fidelity_qualified'])
            for waveform, frame_name, calibration in product(('scalar', 'frozen_wave'), ('scipy', 'declared'), ('independent', 'frozen')):
                value = scores(z['audio'], scalar if waveform == 'scalar' else z['wave'],
                    old if calibration == 'independent' else frozen,
                    full_frame if frame_name == 'scipy' else declared_frame)
                differences = {name: float(np.max(abs(np.asarray(value[name])-np.asarray(expected))))
                               for name, expected in source['metrics'].items()}
                row['variants']['/'.join((waveform, frame_name, calibration))] = dict(
                    metrics=value, absolute_differences=differences,
                    original_2e_12_field_agreement_passed=all(v < 2e-12 for v in differences.values()))
            if row['known_control']:
                assert row['variants']['frozen_wave/declared/frozen']['original_2e_12_field_agreement_passed']
            report['cases'].append(row)
            save(args.out / 'report.json', report)
            print('METRIC_DIAGNOSIS', directory.name,
                {key: max(value['absolute_differences'].values()) for key, value in row['variants'].items()}, flush=True)
        report.update(result='locked_source_metric_operator_diagnosed', known_controls_first=True,
            original_failed_audit_retained=True, no_complete_math_or_audio_or_C_qualification=True,
            original_field_gate=2e-12, original_fidelity_gate=.02,
            no_gate_change_or_weak_band_removal_or_gain_matching=True)
    except BaseException as error:
        report.update(result='failed', error=repr(error))
        raise
    finally:
        save(args.out / 'report.json', report)


if __name__ == '__main__':
    main()
