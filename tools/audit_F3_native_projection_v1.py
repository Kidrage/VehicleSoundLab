"""Independent normal-equation, scalar synthesis and all-window stereo audit."""
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
    a = p.parse_args()
    repo = Path(__file__).resolve().parents[1]
    for name in ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy import linalg, signal
    a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', cases=[], max_wave_difference_FS=0,
             max_spectral_difference_FS2=0, max_DFT_amplitude_difference=0,
             source_map_difference_cycles=0, stereo_inputs=0, spectral_windows=0,
             explicit_DFT_complex_values=0)
    try:
        shutil.copy2(__file__, a.out/'executed_audit.py')
        m = load(a.study/'report.json')
        assert m['result'] == 'native_harmonic_remainder_cross_budgets_measured'
        for name, h in m['sources'].items():
            assert sha(a.study/'exact_sources'/name) == h
        for name, h in m['inputs'].items():
            assert sha(name) == h
        plan = load(a.study/'exact_sources/research/F3_native_projection_v1_plan.json')
        spec, gates = plan['measurement'], plan['gates']
        rate, n, size, hop = [spec[k] for k in ['rate', 'window_samples', 'fft_samples', 'hop_samples']]
        frequency = np.arange(size//2+1)*rate/size
        masks = [np.flatnonzero((frequency >= lo)&(frequency < hi)) for lo, hi in spec['bands_hz']]
        bins = np.array([int(b[k]) for b in masks for k in [0, len(b)//2, -1]])
        window = signal.windows.hann(n, sym=False)
        angle = 2*np.pi*np.arange(n)[:, None]*bins[None, :]/size
        real_basis, imag_basis = np.cos(angle), -np.sin(angle)
        kw = dict(fs=rate, window='hann', nperseg=n, noverlap=0,
                  nfft=size, detrend=False, scaling='density')

        def close(got, expected, label):
            error = abs(got-expected)
            assert np.all(error <= gates['matrix_absolute_FS2']+gates['matrix_relative']*abs(expected)), (label, float(error.max()))
            r['max_spectral_difference_FS2'] = max(r['max_spectral_difference_FS2'], float(error.max()))

        def power(x):
            _, diagonal = signal.welch(x, axis=0, **kw)
            _, cross = signal.csd(x[:, 1], x[:, 0], **kw)
            result = np.zeros((8, 2, 2), complex)
            for b, mask in enumerate(masks):
                result[b, 0, 0], result[b, 1, 1] = diagonal[mask].sum(axis=0)*rate/size
                result[b, 0, 1] = cross[mask].sum()*rate/size
                result[b, 1, 0] = result[b, 0, 1].conjugate()
            return result

        def cross(x, y):
            result = np.zeros((8, 2, 2), complex)
            for left in range(2):
                for right in range(2):
                    _, values = signal.csd(y[:, right], x[:, left], **kw)
                    result[:, left, right] = [values[mask].sum()*rate/size for mask in masks]
            return result

        def dft(x, starts):
            frames = x[starts[:, None]+np.arange(n)]*window[None, :, None]
            direct = np.stack([frames[:, :, c]@real_basis+1j*(frames[:, :, c]@imag_basis) for c in range(2)], axis=-1)
            expected = np.fft.rfft(frames, n=size, axis=1)[:, bins]
            error = float(abs(direct-expected).max())
            assert error <= gates['explicit_DFT_amplitude'], error
            r['max_DFT_amplitude_difference'] = max(r['max_DFT_amplitude_difference'], error)
            r['explicit_DFT_complex_values'] += direct.size

        all_rows = m['known']+[row[key] for row in m['cases'] for key in ['source', 'generated']]
        parent = a.workspace/'baselines/F3_local_detail_budget_v1/evidence/measure1'
        receipt = load(parent/'report.json')
        source_rows = {row['label']: row for row in receipt['cases']}
        cholesky_cache = {}
        for row in all_rows:
            label = row['label']
            path = a.study/label/'arrays.npz'
            assert sha(path) == row['data_sha256']
            d = np.load(path)
            audio, phase = d['audio'], d['phase']
            # Independent phase-coordinate inversion with explicit intervals.
            if label.endswith('_source'):
                entry = source_rows[label[:-7]]
                times = entry['native_registered_start_seconds']+(entry['native_first_frame']+np.arange(len(audio)))/rate
                positions = d['source_seconds']
                at = np.searchsorted(positions, times, side='right')-1
                at = np.minimum(at, len(positions)-2)
                actual_phase = (at+(times-positions[at])/(positions[at+1]-positions[at]))/1024
                error = float(abs(actual_phase-phase).max())
                assert error <= gates['known_phase_inverse_cycles']
                r['source_map_difference_cycles'] = max(r['source_map_difference_cycles'], error)
                source = np.load(parent/entry['label']/'measurement.npz')['native']
                assert np.array_equal(audio, source)
            elif label.endswith('_C'):
                entry = source_rows[label[:-2]]
                original = np.load(parent/entry['label']/'measurement.npz')['C_chunks']
                assert np.array_equal(audio, original.transpose(1, 0, 2).reshape(len(audio), 18))
                assert np.array_equal(phase, np.arange(len(audio))*entry['root_hz']/rate)
            else:
                assert label.startswith('known_')
                if label == 'known_rising_inverse_clock':
                    exact = 60*np.arange(len(audio))/rate+7.5*(np.arange(len(audio))/rate)**2
                    assert abs(exact-d['exact_analytic_phase']).max() <= 8*np.spacing(float(exact.max()))
                    assert abs(exact-phase).max() <= gates['known_phase_inverse_cycles']
                else:
                    assert np.array_equal(phase, 64*np.arange(len(audio))/rate)
                # Reconstruct mathematical fixtures independently; do not
                # accept arrays labelled truth without checking their formula.
                original_phase = d['exact_analytic_phase'] if label == 'known_rising_inverse_clock' else phase
                tone = np.zeros_like(audio)
                for channel in range(2):
                    gain = 1 if channel == 0 or label == 'known_mono' else .7
                    offset = 0 if channel == 0 or label == 'known_mono' else .4
                    for order, amplitude in [(5, .12), (127, .035), (201, .02)]:
                        tone[:, channel] += gain*amplitude*np.cos(2*np.pi*order*original_phase+.13*order+offset)
                inter = np.column_stack([
                    .04*np.cos(2*np.pi*60.5*phase+.2)+.03*np.sin(2*np.pi*170.5*phase+.1),
                    .025*np.cos(2*np.pi*60.5*phase+.7)+.035*np.sin(2*np.pi*170.5*phase-.1)])
                if label == 'known_zero':
                    truth_h = truth_r = np.zeros_like(audio)
                elif label == 'known_interharmonic':
                    truth_h, truth_r = np.zeros_like(audio), inter
                elif label == 'known_mixed_half_order':
                    truth_h, truth_r = tone, inter
                elif label == 'known_deterministic_AM':
                    truth_h, truth_r = np.zeros_like(audio), np.zeros_like(audio)
                    for c, amp, offset in [(0, .13, .1), (1, .09, .5)]:
                        truth_h[:, c] = amp*np.cos(2*np.pi*127*phase+offset)
                        truth_r[:, c] = .2*amp*(np.cos(2*np.pi*126.5*phase+offset)+np.cos(2*np.pi*127.5*phase+offset))
                elif label.startswith('known_white_mix_'):
                    seed = int(label.removeprefix('known_white_mix_'))
                    normal = np.random.default_rng(seed).standard_normal(audio.shape)
                    noise = .035*np.column_stack([normal[:, 0], .6*normal[:, 0]+.8*normal[:, 1]])
                    assert np.array_equal(noise, d['noise'])
                    assert abs(audio-tone-noise).max() <= gates['known_exact_wave_FS']
                    truth_h = truth_r = None
                else:
                    truth_h, truth_r = tone, np.zeros_like(audio)
                if truth_h is not None:
                    assert abs(d['truth_H']-truth_h).max() <= gates['known_exact_wave_FS']
                    assert abs(d['truth_R']-truth_r).max() <= gates['known_exact_wave_FS']
                    assert abs(audio-truth_h-truth_r).max() <= gates['known_exact_wave_FS']
            # Different solver and explicit summation, no QR or producer imports.
            key = phase.tobytes()
            if key not in cholesky_cache:
                columns = [np.ones(len(phase))]
                columns += [np.cos(2*np.pi*k*phase) for k in range(1, 289)]
                columns += [np.sin(2*np.pi*k*phase) for k in range(1, 289)]
                design = np.array(columns).T
                cholesky_cache[key] = (design, linalg.cho_factor(design.T@design))
            design, factor = cholesky_cache[key]
            coefficient = linalg.cho_solve(factor, design.T@audio)
            h = np.broadcast_to(coefficient[0], audio.shape).copy()
            for k in range(1, 289):
                h += np.cos(2*np.pi*k*phase)[:, None]*coefficient[k]
                h += np.sin(2*np.pi*k*phase)[:, None]*coefficient[288+k]
            rem = audio-h
            error = max(float(abs(h-d['harmonic']).max()), float(abs(rem-d['remainder']).max()))
            assert error <= gates['projection_reconstruction_FS'], (label, error)
            r['max_wave_difference_FS'] = max(r['max_wave_difference_FS'], error)
            assert abs(design.T@rem).max()/len(audio) <= gates['normal_residual_FS']
            assert abs(h.T@rem).max()/len(audio) <= gates['global_HR_FS2']
            if 'truth_H' in d.files:
                error = max(float(abs(h-d['truth_H']).max()), float(abs(rem-d['truth_R']).max()))
                gate = gates['known_chirp_inverse_wave_FS'] if label.endswith('rising_inverse_clock') else gates['known_exact_wave_FS']
                assert error <= gate
            if label.startswith('known_white_mix_'):
                noise_h = design@linalg.cho_solve(factor, design.T@d['noise'])
                assert abs(h-d['deterministic_H']-noise_h).max() <= gates['known_exact_wave_FS']
                expected = .035**2*(len(audio)-577)/len(audio)
                assert abs(np.mean(rem*rem, axis=0)/expected-1).max() <= gates['white_noise_retained_power_relative']
            starts = np.arange(0, len(audio)-n+1, hop)
            assert np.array_equal(d['window_starts'], np.broadcast_to(starts, d['window_starts'].shape))
            values = {}
            for i in range(audio.shape[1]//2):
                x, hx, rx = [v[:, 2*i:2*i+2] for v in [audio, d['harmonic'], d['remainder']]]
                for v in [x, hx, rx]:
                    dft(v, starts)
                for j, first in enumerate(starts):
                    section = slice(first, first+n)
                    for name, v in [('P_full', x), ('P_harmonic', hx), ('P_remainder', rx)]:
                        close(power(v[section]), d[name][i, j], name)
                    cross_power = cross(hx[section], rx[section])
                    close(cross_power, d['X_HR'][i, j], 'H/R cross')
                    coupled = cross_power+cross_power.conj().swapaxes(-1, -2)
                    close(coupled, d['cross_HR_RH'][i, j], 'Hermitian cross')
                    close(d['P_harmonic'][i, j]+d['P_remainder'][i, j]+coupled, d['P_full'][i, j], 'sum identity')
                    aa, dd, bb = coupled[:, 0, 0].real, coupled[:, 1, 1].real, abs(coupled[:, 0, 1])
                    spread = np.sqrt((aa-dd)**2+4*bb*bb)
                    values['input%d_window%d' % (i, j)] = np.column_stack([(aa+dd-spread)/2, (aa+dd+spread)/2])
                r['stereo_inputs'] += 1
                r['spectral_windows'] += len(starts)
            np.savez_compressed(a.out/(label+'_cross_eigenvalues.npz'), **values)
            r['cases'].append(dict(label=label, stereo_inputs=audio.shape[1]//2,
                                   normal_equation_wave_verified=True, all_window_spectra_verified=True,
                                   signed_cross_eigenvalues_saved=True))
            save(a.out/'report.json', r)
            print('PASS independent wave/spectra/cross', label, flush=True)
            if not label.startswith('known_'):
                cholesky_cache.clear()
        assert r['stereo_inputs'] == 71
        assert all(sha(repo/name) == h for name, h in m['protected_before'].items())
        r.update(result='independent_native_projection_audit_passed',
                 producer_report_sha256=sha(a.study/'report.json'),
                 auditor_sha256=sha(__file__), same_runtime_C_voices_F2=True,
                 source_separation_qualified=False)
    except Exception as exc:
        r.update(result='failed', error=repr(exc))
        raise
    finally:
        save(a.out/'report.json', r)


if __name__ == '__main__':
    main()
