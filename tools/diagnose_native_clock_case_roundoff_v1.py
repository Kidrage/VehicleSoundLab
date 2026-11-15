"""Reproduce the retained pure-stopband Hann-operator ratio discrepancy."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'known', 'failed', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace / 'tools/python_deps'))
    import numpy as np
    from scipy import signal, fft
    from native_clock_render_v1.filter import render
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', sources={}, inputs={})
    try:
        for name in ('tools/diagnose_native_clock_case_roundoff_v1.py', 'tools/research_archive_v1.py',
                     'tools/native_clock_render_v1/filter.py', 'tools/native_clock_render_v1/basis.py',
                     'tools/native_clock_render_v1/geometry.py'):
            dest = a.out / 'exact_sources' / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo / name, dest); r['sources'][name] = sha(dest)
        known = load(a.known / 'report.json')
        c = next(c for c in known['cases'] if c['label'] == 'pure_stopband')
        path = a.known / c['file']
        assert sha(path) == c['sha256']
        for file in (path, a.known / 'report.json', a.failed):
            r['inputs'][str(file)] = sha(file)
        assert load(a.failed)['result'] == 'failed'
        with np.load(path) as f:
            z = {k: f[k] for k in f.files}
        high, _ = render(z['nodes'], z['positions'], z['orders'], z['source_seconds'],
                         float(z['native_start']), int(z['count']), up=32)
        reference, error = high['native'], z['native'] - high['native']
        explicit = .5 - .5 * np.cos(2 * np.pi * np.arange(4096) / 4096)
        alternative = signal.windows.hann(4096, sym=False)
        groups = np.searchsorted([3000, 6000, 8000, 10000, 14000], np.arange(2049) * 48000 / 4096, side='right')
        weights = np.full(2049, 2.); weights[[0, -1]] = 1
        rows, arrays = [], dict(reference=reference, candidate=z['native'])
        for name, window in (('original_explicit_Hann', explicit), ('scipy_constructed_Hann', alternative)):
            ref = fft.rfft(reference[None] * window[None, :, None], axis=1)
            diff = fft.rfft(error[None] * window[None, :, None], axis=1)
            norms, sums = [], []
            for b in range(6):
                mask = groups == b; weight = np.sqrt(weights[mask])[None, :, None]
                x, y = diff[:, mask] * weight, ref[:, mask] * weight
                norms.append(float(np.linalg.norm(x) / np.linalg.norm(y)))
                sums.append(float(np.sqrt(np.sum(abs(x) ** 2) / np.sum(abs(y) ** 2))))
            rows.append(dict(window=name, NRMSE_norm=norms, NRMSE_sum=sums))
            arrays[name + '_reference_spectrum'] = ref
            arrays[name + '_error_spectrum'] = diff
        original_ref = np.fft.rfft(reference[None] * explicit[None, :, None], axis=1)
        original_diff = np.fft.rfft(error[None] * explicit[None, :, None], axis=1)
        assert np.array_equal(original_ref, arrays['original_explicit_Hann_reference_spectrum'])
        assert np.array_equal(original_diff, arrays['original_explicit_Hann_error_spectrum'])
        output = a.out / 'observed.npz'; np.savez_compressed(output, **arrays)
        r.update(result='native_clock_case_Hann_operator_discrepancy_reproduced', control='pure_stopband',
            file=output.name, sha256=sha(output), window_diagnosis=rows,
            failed_attempt_report_sha256=sha(a.failed), original_normalized_gate=2e-11,
            Hann_vector_max_difference=float(np.max(abs(explicit - alternative))),
            same_Hann_cross_FFT_spectra_bitwise_equal=True,
            normalized_cross_FFT_all_qualified=False,
            no_old_line_failure_relabel_or_gate_change=True)
        save(a.out / 'report.json', r)
        print('HANN_DIAGNOSIS_REPRODUCED', r['Hann_vector_max_difference'], flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error)); save(a.out / 'report.json', r); raise


if __name__ == '__main__':
    main()
