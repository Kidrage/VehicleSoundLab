"""Independent Welch/CSD, selected trig DFT, M/S and 2x2 debt audit."""
import argparse
import math
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'measure', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    repo = Path(__file__).resolve().parents[1]
    for name in ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    import soundfile as sf
    from scipy import signal
    import scipy

    a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', sources={}, cases=[], max_matrix_error_FS2=0,
             max_direct_DFT_amplitude_error=0, max_MS_error_FS2=0,
             max_debt_eigenvalue_error_FS2=0, checked_inputs=0,
             checked_windows=0, direct_DFT_complex_values=0)
    try:
        for name in ['tools/audit_F3_local_detail_budget_v1.py', 'tools/research_archive_v1.py']:
            dest = a.out/'exact_sources'/name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, dest)
            r['sources'][name] = sha(dest)
        m = load(a.measure/'report.json')
        assert m['result'] == 'six_native_time_stereo_budgets_measured'
        for name, h in m['sources'].items():
            assert sha(a.measure/'exact_sources'/name) == h
        plan = load(a.measure/'exact_sources/research/F3_local_detail_budget_v1_plan.json')
        spec, gates = plan['measurement'], plan['verification']
        rate, n, size, hop = [spec[k] for k in ['rate', 'window_samples', 'fft_samples', 'hop_samples']]
        kw = dict(fs=rate, window='hann', nperseg=n, noverlap=n-hop,
                  nfft=size, detrend=False, scaling='density')
        frequency = np.arange(size//2+1)*rate/size
        bands = [np.flatnonzero((frequency >= low)&(frequency < high)) for low, high in spec['bands_hz']]
        selected = np.array([int(indices[k]) for indices in bands for k in [0, len(indices)//2, -1]])
        # Explicit trigonometric sums independently check every saved window
        # at the first, middle and last FFT bin of each band, both channels.
        angle = 2*np.pi*selected[:, None]*np.arange(n)/size
        trig = np.cos(angle)-1j*np.sin(angle)
        hann = .5-.5*np.cos(2*np.pi*np.arange(n)/n)

        def check_close(actual, expected, key):
            error = np.abs(actual-expected)
            assert np.all(error <= gates['independent_all_band_absolute_FS2']
                          + gates['independent_all_band_relative']*np.abs(expected)), (key, float(error.max()))
            return float(error.max())

        def measure(audio):
            f, powers = signal.welch(audio, axis=0, **kw)
            _, cross = signal.csd(audio[:, 1], audio[:, 0], **kw)
            assert np.array_equal(f, frequency)
            matrix = np.zeros((len(bands), 2, 2), complex)
            for j, indices in enumerate(bands):
                matrix[j, 0, 0], matrix[j, 1, 1] = powers[indices].sum(axis=0)*rate/size
                matrix[j, 0, 1] = cross[indices].sum()*rate/size
                matrix[j, 1, 0] = matrix[j, 0, 1].conjugate()
            starts = np.arange(0, len(audio)-n+1, hop)
            frames = audio[starts[:, None]+np.arange(n)]*hann[None, :, None]
            direct = np.stack([frames[:, :, c] @ trig.T for c in range(2)], axis=-1)
            actual_fft = np.fft.rfft(frames, n=size, axis=1)[:, selected]
            error = float(np.max(abs(direct-actual_fft)))
            assert error <= gates['direct_selected_DFT_amplitude'], error
            r['max_direct_DFT_amplitude_error'] = max(r['max_direct_DFT_amplitude_error'], error)
            r['checked_inputs'] += 1
            r['checked_windows'] += len(starts)
            r['direct_DFT_complex_values'] += direct.size
            for c, sign in [(0, 1), (1, -1)]:
                ms = (audio[:, 0]+sign*audio[:, 1])/2
                _, density = signal.welch(ms, **kw)
                observed = np.array([density[b].sum()*rate/size for b in bands])
                expected = (matrix[:, 0, 0].real+matrix[:, 1, 1].real+2*sign*matrix[:, 0, 1].real)/4
                r['max_MS_error_FS2'] = max(r['max_MS_error_FS2'], check_close(observed, expected, 'MS'))
            return matrix

        # Same four mathematical controls, audited before any real source.
        t = np.arange(8192)
        phase = 2*np.pi*512*t/4096
        delay = 2*np.pi*512*3/4096
        x = .2*np.cos(phase)
        known = [('mono', np.column_stack([x, x]), .02),
                 ('asymmetric', np.column_stack([x, .5*x]), .01),
                 ('quadrature', np.column_stack([x, .2*np.sin(phase)]), .02j),
                 ('delay', np.column_stack([x, .2*np.cos(phase-delay)]), .02*np.exp(1j*delay))]
        for name, audio, expected in known:
            measure(audio)
            _, cross = signal.csd(audio[:, 1], audio[:, 0], **kw)
            value = cross.sum()*rate/size
            assert abs(value-expected) <= gates['known_matrix_FS2']
            assert abs(np.angle(value/expected)) <= gates['known_control_phase']
        r['known_before_source'] = ['mono', 'asymmetric', 'quadrature', 'signed_delay']
        for offdiag, positive in [(.2, True), (2., False)]:
            lo = 1-abs(offdiag)
            assert (lo > 0) == positive
        print('PASS independent controls and direct trigonometric DFT', flush=True)

        def eigenvalues(matrix):
            aa, dd = matrix[:, 0, 0].real, matrix[:, 1, 1].real
            spread = np.sqrt((aa-dd)**2+4*abs(matrix[:, 0, 1])**2)
            return np.column_stack(((aa+dd-spread)/2, (aa+dd+spread)/2))

        def descriptor(matrix, published):
            diagonal = matrix.diagonal(axis1=-2, axis2=-1).real
            cross = matrix[:, 0, 1]
            check_close(diagonal, np.array(published['power_LR']), 'JSON powers')
            check_close(np.column_stack([cross.real, cross.imag]),
                        np.array(published['cross_L_conjR']), 'JSON cross')
            correlation = cross/(np.sqrt(diagonal[:, 0])*np.sqrt(diagonal[:, 1]))
            assert np.allclose(np.column_stack([correlation.real, correlation.imag]),
                               published['complex_correlation'], atol=1e-12, rtol=5e-12)
            mid = (diagonal[:, 0]+diagonal[:, 1]+2*cross.real)/4
            side = (diagonal[:, 0]+diagonal[:, 1]-2*cross.real)/4
            ratio = 10*np.log10(np.maximum(side, 1e-30)/np.maximum(mid, 1e-30))
            assert np.allclose(ratio, published['side_mid_db'], atol=1e-10, rtol=5e-12)
            assert ((side <= 1e-30)|(mid <= 1e-30)).tolist() == published['side_mid_floor_applied']

        for row in m['cases']:
            folder = a.measure/row['label']
            assert sha(folder/'measurement.npz') == row['data_sha256']
            data = np.load(folder/'measurement.npz')
            original = Path(row['original_folder'])
            coordinates = np.load(original/'coordinates.npz')['source_seconds']
            native, sr = sf.read(original/'native.wav', always_2d=True)
            start = math.ceil((coordinates[0]-row['native_registered_start_seconds'])*rate)
            stop = math.floor((coordinates[-1]-row['native_registered_start_seconds'])*rate)+1
            assert sr == rate and start == row['native_first_frame'] and stop-1 == row['native_last_frame_inclusive']
            assert np.array_equal(native[start:stop], data['native'])
            reference, sr = sf.read(original/'reference.wav', always_2d=True)
            assert sr == rate and np.array_equal(reference, data['processed'])
            generated = {}
            for item in row['generated']:
                dest = folder/('DNA_%d.wav' % item['seed'])
                assert sha(dest) == item['sha256']
                wave, sr = sf.read(dest, always_2d=True)
                assert sr == rate
                generated[item['seed']] = wave
            for chunk, saved in zip(row['chunks'], data['C_chunks']):
                first = chunk['start_frame']
                assert np.array_equal(saved, generated[chunk['seed']][first:first+chunk['frames']])
            inputs = [data['native'], data['processed']]+list(data['C_chunks'])
            expected = [data['native_matrix'], data['processed_matrix']]+list(data['C_matrices'])
            actual = [measure(audio) for audio in inputs]
            for observed, target in zip(actual, expected):
                r['max_matrix_error_FS2'] = max(r['max_matrix_error_FS2'], check_close(observed, target, row['label']))
            native_matrix = actual[0]
            c_matrices = np.array(actual[2:])
            mean = c_matrices.mean(axis=0)
            check_close(mean, data['C_mean'], 'mean')
            for matrix, published in [(native_matrix, row['native']),
                                       (actual[1], row['processed']), (mean, row['C_mean'])]:
                descriptor(matrix, published)
            deltas = list(native_matrix-c_matrices)+[native_matrix-mean]
            for delta, saved, published in zip(deltas, list(data['debt'])+[data['mean_debt']],
                                              row['comparisons']+[row['mean_comparison']]):
                check_close(delta, saved, 'debt')
                eig = eigenvalues(delta)
                target = np.array(published['debt_eigenvalues'])
                r['max_debt_eigenvalue_error_FS2'] = max(r['max_debt_eigenvalue_error_FS2'],
                                                        check_close(eig, target, 'literal eigenvalues'))
                assert (eig[:, 0] > 0).tolist() == published['debt_positive_definite']
                assert np.all(delta.diagonal(axis1=-2, axis2=-1).real > 0, axis=1).tolist() == published['diagonal_debt_positive']
                check_close(np.array(published['debt_matrix_real'])+1j*np.array(published['debt_matrix_imag']), saved, 'JSON debt')
            native_power = native_matrix.diagonal(axis1=-2, axis2=-1).real
            for matrix, published in zip(list(c_matrices)+[mean], row['comparisons']+[row['mean_comparison']]):
                ratio = 10*np.log10(matrix.diagonal(axis1=-2, axis2=-1).real/native_power)
                assert np.allclose(ratio, published['C_minus_native_power_db'], atol=1e-11, rtol=5e-12)
            r['cases'].append(dict(label=row['label'], all_eleven_inputs_checked=True,
                                   source_aperture_exact=True, nine_generated_chunks_exact=True,
                                   ten_debt_matrices_eigenvalues_checked=True,
                                   all_published_descriptors_and_ratios_checked=True))
            save(a.out/'report.json', r)
            print('PASS Welch/CSD/MS/DFT/debt', row['label'], flush=True)
        for name, h in m['protected_before'].items():
            assert sha(repo/name) == h
        r.update(result='independent_native_stereo_budget_audit_passed',
                 producer_report_sha256=sha(a.measure/'report.json'),
                 versions=dict(numpy=np.__version__, scipy=scipy.__version__),
                 all_runtime_models_F2_exact=True, no_realism_or_source_separation_gate=True)
    except Exception as exc:
        r.update(result='failed', error=repr(exc))
        raise
    finally:
        save(a.out/'report.json', r)


if __name__ == '__main__':
    main()
