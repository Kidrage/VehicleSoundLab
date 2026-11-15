"""Read-only diagnosis of the terminal real case's unequal base-guard operators.

Never imports a production fitter or changes a capture, factor, gate or run.
The FFT composite metric and the reconstructed declared band Cholesky are
measured separately. Mathematical equivalence is not bitwise equivalence.
"""
import argparse
import os
from pathlib import Path
import shutil
import sys
import time

from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('workspace', 'case', 'out'):
        p.add_argument('--' + key, type=Path, required=True)
    a = p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[key] = '2'
    sys.path.insert(0, str(a.workspace / 'tools/python_deps'))
    import numpy as np
    from scipy import linalg
    from waveform_file_real_v1.audit_oracle import make
    from observer_frequency_v1.reduced_oracle import synthesize, adjoint
    from waveform_trace_audit_v1 import root_frobenius

    a.out.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    repo = Path(__file__).resolve().parents[1]
    names = ('tools/diagnose_waveform_real_guard_v1.py',
             'tools/waveform_file_real_v1/audit_oracle.py',
             'tools/observer_frequency_v1/reduced_oracle.py',
             'tools/waveform_trace_audit_v1.py')
    result = dict(result='running', inputs={}, sources={})
    for name in names:
        dest = a.out / 'exact_sources' / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo / name, dest)
        result['sources'][name] = sha(dest)
    for path in (a.case/'capture.npz', a.case/'report.json', a.case.parent/'run_spec.json'):
        result['inputs'][str(path)] = sha(path)
    try:
        info = load(a.case/'report.json')
        assert info['capture_sha256'] == result['inputs'][str(a.case/'capture.npz')]
        with np.load(a.case/'capture.npz') as f:
            z = {name: f[name] for name in f.files}
        oracle, old = make(z['audio'], z['target'], z['positions'], z['orders'], z['scale'])
        N, M, H = len(z['audio']), len(z['positions']), len(z['orders'])
        L = np.linalg.cholesky(oracle.R)
        norm_mono = root_frobenius(oracle)['root_Frobenius'] / np.sqrt(2)
        source_norm = info['solver']['augmented_root_Frobenius']
        e, base = z['base_wave_model_residual'], z['base_z']

        def normal(weighted):
            nodes = adjoint(weighted, z['positions'], z['orders']) * z['scale'][None]
            answer = linalg.solve_triangular(L, nodes.reshape(M, -1), lower=True).reshape(M, H, 2)
            return np.vstack((answer.real.reshape(M*H, 2), answer.imag.reshape(M*H, 2))) + base

        # ALL original bins/windows, using an independently implemented FFT
        # forward/adjoint. This is the original corrected objective, not the
        # rounded native band-root action used by the initial diagnostic.
        fft_weighted = e / old['sigma']**2 + oracle.spectral_adjoint(oracle.spectral(e))
        fft_normal = normal(fft_weighted)
        spectral = oracle.spectral(e)
        energy = np.sum((e/old['sigma'])**2, axis=0) + np.sum(abs(spectral)**2, axis=(0, 1))
        den_fft = norm_mono * np.sqrt(energy + np.sum(base**2, axis=0))
        fft_stable = np.linalg.norm(fft_normal, axis=0) / den_fft
        print('GUARD_DIAG_FFT', fft_stable.tolist(), flush=True)

        # Reconstruct the DECLARED lower-band metric, including all4096
        # diagonals and its exact declared multiplication/accumulation order.
        # The original objective LOCKED the input weights/scales. Re-estimation
        # using an alternative Hann implementation is retained above only as
        # the diagnostic which actually failed; it cannot replace these data.
        size = 4096
        weights = z['weights']
        sigma, amplitude = float(z['sigma']), float(z['amplitude'])
        kernel = np.fft.irfft(weights**2, n=size)
        window = .5 - .5*np.cos(2*np.pi*np.arange(size)/size)
        coverage = np.zeros(N)
        for start in range(-3840, N, 256):
            first, last = max(0, start), min(N, start+size)
            coverage[first:last] += window[first-start:last-start]**2
        normalizer = 1/np.sqrt(coverage)
        endpoint = np.r_[1., np.full(2047, np.sqrt(2.)), 1.]

        def locked_fft_action(wave):
            value = wave/sigma**2
            for start in range(0, N-size+1, 256):
                gain = window*normalizer[start:start+size]
                rows = np.fft.rfft(wave[start:start+size]*gain[:, None], axis=0)*endpoint[:, None]/64
                rows *= (amplitude*weights[:, None])**2
                value[start:start+size] += np.fft.irfft(rows/endpoint[:, None], n=size, axis=0)*64*gain[:, None]
            return value

        locked_fft_weighted = locked_fft_action(e)
        locked_fft_normal = normal(locked_fft_weighted)
        bands = np.zeros((size, N), dtype='float64', order='F')
        bands[0] = 1 / sigma**2
        for start in range(0, N-size+1, 256):
            gain = amplitude*window/np.sqrt(coverage[start:start+size])
            for d in range(size):
                bands[d, start:start+size-d] += gain[d:]*kernel[d]*gain[:size-d]
        sbmv = linalg.get_blas_funcs('sbmv', (bands,))
        band_weighted = np.column_stack([
            sbmv(size-1, 1., bands, np.array(c, copy=True), lower=1) for c in e.T])
        band_normal = normal(band_weighted)
        bands = linalg.cholesky_banded(bands, lower=True, overwrite_ab=True, check_finite=False)
        print('GUARD_DIAG_BAND_ROOT_READY', time.monotonic()-started, flush=True)
        tbmv = linalg.get_blas_funcs('tbmv', (bands,))

        def action(x, transpose=False):
            value = np.array(x, dtype='float64', order='F', copy=True)
            for c in range(value.shape[1]):
                value[:, c] = tbmv(size-1, bands, value[:, c], lower=1,
                                   trans=int(transpose), overwrite_x=1)
            return value

        root_model = action(e, True)
        root_weighted = action(root_model)
        root_normal = normal(root_weighted)
        den_root = source_norm*np.sqrt(np.sum(root_model**2, axis=0)+np.sum(base**2, axis=0))
        root_stable = np.linalg.norm(root_normal, axis=0)/den_root
        nodes = (z['base_q'][:M*H] + 1j*z['base_q'][M*H:]).reshape(M, H, 2)
        predicted = synthesize(nodes*z['scale'][None], z['positions'], z['orders'], N)
        root_back = np.linalg.norm(action(predicted-z['audio'], True)-root_model, axis=0)/np.linalg.norm(action(z['audio'], True), axis=0)
        reported = np.array(info['solver']['stable_root_normal_relative'])
        reported_back = np.array(info['solver']['root_backward_discrepancy'])
        result.update(result='terminal_real_base_guard_operator_diagnosed',
            original_fft_stable_LR=fft_stable.tolist(),
            original_band_stable_LR=(np.linalg.norm(band_normal, axis=0)/den_fft).tolist(),
            reconstructed_band_root_stable_LR=root_stable.tolist(),
            source_reported_band_root_stable_LR=reported.tolist(),
            source_reported_band_root_backward_LR=reported_back.tolist(),
            reconstructed_band_root_backward_LR=root_back.tolist(),
            original_failed_cross_operator_absolute_error=float(np.max(abs(fft_stable-reported))),
            locked_fft_stable_LR=(np.linalg.norm(locked_fft_normal, axis=0)/den_root).tolist(),
            locked_weight_recomputation_relative_error=float(np.max(abs(old['weights']-weights)/weights)),
            coverage_implementation_absolute_error=float(np.max(abs(oracle.profile['full_coverage']-coverage))),
            same_root_stable_absolute_error=float(np.max(abs(root_stable-reported))),
            same_root_backward_absolute_error=float(np.max(abs(root_back-reported_back))),
            normalized_normal_operator_difference=float(np.max(np.linalg.norm(fft_normal-root_normal, axis=0)/den_root)),
            waveform_metric_relative_difference=float(np.linalg.norm(fft_weighted-root_weighted)/np.linalg.norm(fft_weighted)),
            mono_norm_relative_difference=float(abs(norm_mono-source_norm)/source_norm),
            same_root_agreement_gate=2e-12, original_guard_gate=1e-11,
            no_gate_or_source_change=True, no_sound_or_solver_qualification=True,
            elapsed_seconds_PC_only=time.monotonic()-started)
        np.savez_compressed(a.out/'diagnosis.npz', fft_weighted=fft_weighted,
            band_weighted=band_weighted, root_weighted=root_weighted,
            fft_normal=fft_normal, band_normal=band_normal, root_normal=root_normal,
            root_model=root_model, den_fft=den_fft, den_root=den_root,
            locked_fft_weighted=locked_fft_weighted, locked_fft_normal=locked_fft_normal)
        result['diagnosis_sha256'] = sha(a.out/'diagnosis.npz')
        save(a.out/'report.json', result)
        print('GUARD_DIAG_COMPLETE', result['same_root_stable_absolute_error'],
              result['same_root_backward_absolute_error'], flush=True)
    except BaseException as error:
        result.update(result='failed', error=repr(error))
        save(a.out/'report.json', result)
        raise


if __name__ == '__main__':
    main()
