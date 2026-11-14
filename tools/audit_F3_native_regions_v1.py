"""Independent interval differences, Welch/CSD and exact control audit."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'study', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args();repo = Path(__file__).resolve().parents[1]
    for name in ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy import signal
    a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', cases=[], stereo_inputs=0, windows=0, DFT_complex_values=0,
             max_matrix_error_FS2=0, max_DFT_error=0, max_root_bound_error_Hz=0,
             max_literal_eigenvalue_error_FS2=0, max_eigenvalue_input_perturbation_bound_FS2=0)
    try:
        shutil.copy2(__file__, a.out/'executed_audit.py')
        m = load(a.study/'report.json')
        assert m['result'] == 'native_frequency_regions_measured'
        for name, h in m['sources'].items():
            assert sha(a.study/'exact_sources'/name) == h
        for name, h in m['inputs'].items():
            assert sha(name) == h
        plan = load(a.study/'exact_sources/research/F3_native_regions_v1_plan.json')
        spec, gates = plan['measurement'], plan['gates']
        rate, n, hop, size = [spec[k] for k in ['rate', 'window_samples', 'hop_samples', 'fft_samples']]
        hz = np.arange(size//2+1)*rate/size
        bands = [np.flatnonzero((hz >= low)&(hz < high)) for low, high in spec['bands_hz']]
        selected = np.array([int(b[k]) for b in bands for k in [0, len(b)//2, -1]])
        angle = 2*np.pi*selected[:, None]*np.arange(n)/size
        trig = np.cos(angle)-1j*np.sin(angle)
        window = signal.windows.hann(n, sym=False)
        kw = dict(fs=rate, window='hann', nperseg=n, noverlap=0, nfft=size, detrend=False, scaling='density')
        source_rows = {c['label']: c for c in m['cases']}
        receipt = load(a.workspace/'baselines/F3_local_detail_budget_v1/evidence/measure1/report.json')
        originals = {c['label']: c for c in receipt['cases']}

        def close(got, expected, label):
            error = abs(got-expected)
            assert np.all(error <= gates['matrix_absolute_FS2']+gates['matrix_relative']*abs(expected)), (label, float(error.max()))
            r['max_matrix_error_FS2'] = max(r['max_matrix_error_FS2'], float(error.max()))

        for entry in m['known']+[row[k] for row in m['cases'] for k in ['source', 'C']]:
            label = entry['label'];path = a.study/label/'arrays.npz'
            assert sha(path) == entry['data_sha256']
            d = np.load(path);audio = d['audio'];starts = np.arange(0, len(audio)-n+1, hop)
            assert np.array_equal(starts, d['window_starts'])
            roots = d['root_bounds'];regions = d['regions'];coverage = d['interval_coverage_count']
            if label.endswith('_source'):
                row = source_rows[label[:-7]];original = originals[label[:-7]]
                context = np.load(a.workspace/'baselines/F3_local_detail_budget_v1/evidence/measure1'/row['label']/'measurement.npz')
                assert np.array_equal(audio, context['native'])
                times = row['native_first_seconds']+np.column_stack([starts, starts+n-1])/rate
                assert np.array_equal(times, d['window_times'])
                positions = d['source_seconds'];expected = []
                for first, last in times:
                    slopes = [(1/1024)/(right-left) for left, right in zip(positions[:-1], positions[1:]) if left <= last and right >= first]
                    expected.append([min(slopes), max(slopes)])
                error = float(abs(roots-np.array(expected)).max())
                assert error <= 1e-12;r['max_root_bound_error_Hz'] = max(r['max_root_bound_error_Hz'], error)
            elif label.endswith('_C'):
                root = label[:-2];source = np.load(a.study/(root+'_source')/'arrays.npz')
                assert np.array_equal(roots, source['root_bounds']) and np.array_equal(regions, source['regions'])
                original = np.load(a.workspace/'baselines/F3_local_detail_budget_v1/evidence/measure1'/root/'measurement.npz')['C_chunks']
                assert np.array_equal(audio, original.transpose(1, 0, 2).reshape(len(audio), 18))
            else:
                assert label.startswith('known_')
                t = np.arange(len(audio))/rate
                phase = 60*t+7.5*t*t if label.startswith('known_rising_') else 64*t
                if label.startswith('known_rising_'):
                    expected = 60+15*np.column_stack([starts, starts+n-1])/rate
                    assert np.allclose(roots, expected, atol=1e-12, rtol=0)
                else:
                    assert np.array_equal(roots, np.full_like(roots, 64.))
                half = label in ['known_static_interline', 'known_rising_half_orders']
                items = [(60.5, .04), (170.5, .03)] if half else [(5, .12), (127, .035), (201, .02)]
                truth = np.zeros_like(audio)
                for c in range(2):
                    gain, offset = (1, 0) if c == 0 or label == 'known_mono' else (.7, .4)
                    for order, amp in items:
                        truth[:, c] += gain*amp*np.cos(2*np.pi*order*phase+.13*order+offset)
                if label == 'known_zero':
                    truth[:] = 0
                elif label == 'known_static_mixed':
                    for c in range(2):
                        for order, amp in [(60.5, .04), (170.5, .03)]:
                            truth[:, c] += (1 if c == 0 else .7)*amp*np.cos(2*np.pi*order*phase+.13*order+(0 if c == 0 else .4))
                elif label in ['known_slow_AM', 'known_deterministic_half_order_AM']:
                    envelope = 1+.4*np.cos(2*np.pi*4*t) if label == 'known_slow_AM' else 1+.4*np.cos(np.pi*phase)
                    for c, amp, offset in [(0, .13, .1), (1, .09, .5)]:
                        truth[:, c] = amp*np.cos(2*np.pi*127*phase+offset)*envelope
                    if label == 'known_slow_AM':
                        assert np.array_equal(envelope, d['known_envelope'])
                elif label.startswith('known_white_'):
                    seed = int(label.removeprefix('known_white_'))
                    z = np.random.default_rng(seed).standard_normal(audio.shape)
                    truth = .035*np.column_stack([z[:, 0], .6*z[:, 0]+.8*z[:, 1]])
                assert abs(audio-truth).max() <= 2e-12
            # Difference-array coverage is independent of producer boolean summation.
            for w, (low, high) in enumerate(roots):
                change = np.zeros(len(hz)+1, int)
                for order in range(1, 289):
                    lo = np.searchsorted(hz, order*low-2*rate/n, side='left')
                    hi = np.searchsorted(hz, order*high+2*rate/n, side='right')
                    change[lo] += 1;change[hi] -= 1
                actual = np.cumsum(change[:-1])
                assert np.array_equal(actual, coverage[w])
                code = np.full(len(hz), 2, np.uint8);code[actual == 0] = 1;code[actual == 1] = 0
                code[(hz < low-2*rate/n)|(hz > 288*high+2*rate/n)] = 3
                assert np.array_equal(code, regions[w])
                for b, indices in enumerate(bands):
                    counts = [int(np.sum(code[indices] == category)) for category in range(4)]
                    assert np.array_equal(counts, d['region_bin_counts'][w, b]) and sum(counts) == len(indices)
            for i in range(audio.shape[1]//2):
                wave = audio[:, 2*i:2*i+2]
                frames = wave[starts[:, None]+np.arange(n)]*window[None, :, None]
                direct = np.stack([frames[:, :, c]@trig.T for c in range(2)], axis=-1)
                ft = np.fft.rfft(frames, n=size, axis=1)[:, selected]
                error = float(abs(direct-ft).max());assert error <= gates['direct_DFT_amplitude']
                r['max_DFT_error'] = max(r['max_DFT_error'], error);r['DFT_complex_values'] += direct.size
                for w, first in enumerate(starts):
                    _, powers = signal.welch(wave[first:first+n], axis=0, **kw)
                    _, cross = signal.csd(wave[first:first+n, 1], wave[first:first+n, 0], **kw)
                    for b, indices in enumerate(bands):
                        total = np.zeros((2, 2), complex)
                        for category in range(4):
                            indices_c = indices[regions[w, indices] == category]
                            matrix = np.zeros((2, 2), complex)
                            matrix[0, 0], matrix[1, 1] = powers[indices_c].sum(axis=0)*rate/size
                            matrix[0, 1] = cross[indices_c].sum()*rate/size;matrix[1, 0] = matrix[0, 1].conjugate()
                            close(matrix, d['P_regions'][i, w, b, category], 'region PSD')
                            aa, dd, bb = matrix[0, 0].real, matrix[1, 1].real, abs(matrix[0, 1])
                            spread = np.sqrt((aa-dd)**2+4*bb*bb)
                            # Verify literal eigenvalues on the SAME saved
                            # matrix. Separately bound the eigenvalue change
                            # from independent Welch/CSD input rounding (Weyl).
                            saved = d['P_regions'][i, w, b, category]
                            a0, d0 = np.longdouble(saved[0, 0].real), np.longdouble(saved[1, 1].real)
                            br, bi = np.longdouble(saved[0, 1].real), np.longdouble(saved[0, 1].imag)
                            root = np.sqrt((a0-d0)**2+4*(br*br+bi*bi))
                            literal = np.array([(a0+d0-root)/2, (a0+d0+root)/2])
                            target = d['region_eigenvalues'][i, w, b, category]
                            close(literal, target, 'literal PSD eigenvalues')
                            r['max_literal_eigenvalue_error_FS2'] = max(r['max_literal_eigenvalue_error_FS2'], float(abs(literal-target).max()))
                            perturbation = float(abs(matrix-saved).sum(axis=1).max())
                            independent_eigen = np.array([(aa+dd-spread)/2, (aa+dd+spread)/2])
                            assert np.all(abs(independent_eigen-target) <= perturbation+gates['matrix_absolute_FS2']+gates['matrix_relative']*abs(target))
                            r['max_eigenvalue_input_perturbation_bound_FS2'] = max(r['max_eigenvalue_input_perturbation_bound_FS2'], perturbation)
                            total += matrix
                        close(total, d['P_total'][i, w, b], 'exhaustive partition')
                r['stereo_inputs'] += 1;r['windows'] += len(starts)
            if label == 'known_slow_AM':
                power = d['P_total'][0, :, 6].diagonal(axis1=-2, axis2=-1).real
                envelope = 1+.4*np.cos(2*np.pi*4*np.arange(len(audio))/rate)
                expected = np.array([np.average(envelope[first:first+n]**2, weights=window**2) for first in starts])[:, None]*np.array([.13**2, .09**2])/2
                assert abs(power/expected-1).max() <= gates['slow_AM_full_band_relative_error_max']
            # Re-evaluate declared control gates and reported fractions from raw matrices.
            if label.startswith('known_'):
                trace = lambda v: v.diagonal(axis1=-2, axis2=-1).real.sum(axis=-1)
                total = trace(d['P_total']).sum();fractions = trace(d['P_regions']).sum(axis=(0, 1, 2))/total if total else np.zeros(4)
                assert np.allclose(fractions, entry['region_power_fraction'], atol=1e-12, rtol=1e-12)
                if label in ['known_mono', 'known_asymmetric_phased']:
                    assert fractions[1] <= gates['static_tone_interline_power_fraction_max']
                if label == 'known_static_interline':
                    assert fractions[1] >= gates['static_half_order_interline_power_fraction_min']
                if label == 'known_rising_harmonics':
                    assert fractions[1] <= gates['swept_harmonic_interline_power_fraction_max']
                if label.startswith('known_white_'):
                    covariance = np.mean([np.einsum('nc,nd,n->cd', audio[first:first+n], audio[first:first+n], window**2)/np.dot(window, window) for first in starts], axis=0)
                    # Positive-frequency cross power has an imaginary part;
                    # real time covariance supplies only its real component.
                    # H(L)*R has the sign of Im(L*conj(R)).
                    imaginary = np.mean([
                        np.dot(signal.hilbert(audio[first:first+n, 0]*window, N=size).imag[:n],
                               audio[first:first+n, 1]*window)/np.dot(window, window)
                        for first in starts])
                    rho = (covariance[0, 1]+1j*imaginary)/np.sqrt(covariance[0, 0]*covariance[1, 1])
                    assert abs(rho-.6) <= gates['known_white_full_band_correlation_absolute_error']
                    assert abs(rho-complex(*entry['known_full_band_correlation'])) <= 1e-12
            r['cases'].append(dict(label=label, exact_control_or_source_input=True, all_bin_regions_exact=True,
                                   all_window_stereo_matrices_and_eigenvalues_checked=True))
            save(a.out/'report.json', r);print('PASS independent regions', label, flush=True)
        assert r['stereo_inputs'] == 73
        assert all(sha(repo/n) == h for n, h in m['protected_before'].items())
        r.update(result='independent_native_regions_audit_passed', producer_report_sha256=sha(a.study/'report.json'),
                 auditor_sha256=sha(__file__), runtime_C_voices_F2_exact=True, physical_separation=False)
    except Exception as exc:
        r.update(result='failed', error=repr(exc));raise
    finally:
        save(a.out/'report.json', r)


if __name__ == '__main__':
    main()
