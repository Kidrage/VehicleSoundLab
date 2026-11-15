"""Independent direct FIR/polyphase/scalar-offset sinc and stereo-stat audit."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('workspace', 'study', 'out'):
        p.add_argument('--'+key, type=Path, required=True)
    a = p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[key] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy import signal, special
    a.out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, a.out/'executed_audit.py')
    r = dict(result='running', cases=[], producer_sha256=sha(a.study/'report.json'), auditor_sha256=sha(__file__))
    try:
        source = load(a.study/'report.json')
        known = source['result'] == 'source_resampling_known_measured'
        assert known or source['result'] == 'source_resampling_six_actual_measured'
        for name, digest in source['sources'].items(): assert sha(a.study/'exact_sources'/name) == digest
        for name, digest in source['inputs'].items(): assert sha(name) == digest
        window = .5-.5*np.cos(2*np.pi*np.arange(4096)/4096)
        endpoints = np.r_[1., np.full(2047, 2.), 1.]
        frequency = np.arange(2049)*16
        bands = np.digitize(frequency, [3000, 6000, 8000, 10000, 14000])
        masks = [(frequency >= 14000) & (frequency < 16000),
            (frequency >= 16000) & (frequency < 18432), frequency == 18432, frequency > 18432]

        def close(x, y, scale=None, gate=2e-11):
            x, y = np.asarray(x), np.asarray(y)
            assert x.shape == y.shape
            if scale is None: scale = float(np.max(abs(y))) if y.size else 0.
            error = float(np.max(abs(x-y))) if y.size else 0.
            relative = error/scale if scale else error
            assert relative < gate, (relative, gate)
            return relative

        def kernel(size, cutoff, beta):
            index = np.arange(size)-(size-1)/2
            w = special.i0(beta*np.sqrt(1-(index/((size-1)/2))**2))/special.i0(beta)
            h = 2*cutoff*np.sinc(2*cutoff*index)*w
            return h/h.sum()

        def ordinary(audio):
            starts = range(0, len(audio)-4096+1, 256)
            X = np.array([np.fft.rfft(audio[start:start+4096]*window[:, None], axis=0) for start in starts])
            return X, abs(X)**2*endpoints[None, :, None]/(4096*sum(window**2))

        def moments(audio):
            X, _ = ordinary(audio)
            grams, ms = [], []
            weights = endpoints/(4096*sum(window**2))
            for b in range(6):
                mask = bands == b
                gram = np.array([[(X[:, mask, i]*X[:, mask, j].conj()*weights[mask]).sum(axis=1)
                    for j in range(2)] for i in range(2)]).transpose(2, 0, 1)
                grams.append(gram)
                M, S = (X[:, mask, 0]+X[:, mask, 1])/2, (X[:, mask, 0]-X[:, mask, 1])/2
                ms.append(np.stack(((abs(M)**2*weights[mask]).sum(axis=1),
                    (abs(S)**2*weights[mask]).sum(axis=1)), axis=1))
            grams = np.stack(grams, axis=1); ms = np.stack(ms, axis=1)
            powers = grams.diagonal(axis1=2, axis2=3).real.copy()
            mean = powers.mean(axis=0)
            centered = powers.reshape(len(powers), 12)-mean.ravel()
            cov = centered.T@centered/len(centered)
            lag = np.array([centered[:-j].T@centered[j:]/(len(centered)-j) for j in range(1, 9)])
            return dict(mean_power=mean, mean_mid_side=ms.mean(axis=0), covariance=cov,
                lag_covariance=lag, CV=np.sqrt(cov.diagonal()).reshape(6, 2)/mean,
                complex_coherence=grams[:, :, 0, 1].mean(axis=0)/np.sqrt(mean[:, 0]*mean[:, 1]))

        for case in source['cases']:
            path = a.study/case['file']; assert sha(path) == case['sha256']
            with np.load(path) as f: z = {k: f[k] for k in f.files}
            if known:
                audio, positions, start, cutoff = z['audio'], z['positions'], 0., 14000.
                frequencies, coefficients = z['frequencies'], z['coefficients']
                def analytic(times, gains):
                    result = np.zeros((len(times), 2))
                    for freq, coeff, gain in zip(frequencies, coefficients, gains):
                        phase = 2*np.pi*freq*times
                        result += gain*(np.cos(phase)[:, None]*coeff.real-np.sin(phase)[:, None]*coeff.imag)
                    return result
                scale = float(abs(coefficients).sum())
                close(audio, analytic(np.arange(len(audio))/48000, np.ones(len(frequencies))), scale)
            else:
                with np.load(case['original_preparation']) as f: original = {k: f[k] for k in f.files}
                audio, positions, start, cutoff = original['native'], original['source_coordinates'], float(original['source_start']), case['cutoff_hz']
                for name in ('source_coordinates', 'positions', 'original_positions', 'orders', 'scale', 'weights', 'amplitude', 'source_start'):
                    assert np.array_equal(z[name], original[name])
                assert np.array_equal(z['orders'], np.arange(1, 289))
                scale = float(np.max(abs(audio)))
            first = int(np.floor((positions[0]-start)*48000+1e-6))-4800
            stop = int(np.ceil((positions[-1]-start)*48000-1e-6))+4801
            assert first >= 0 and stop <= len(audio) and np.array_equal(z['crop'], [first, stop])
            taps = kernel(1025, cutoff/48000, 12.)
            close(z['taps'], taps, gate=2e-13)
            # Direct complete convolution is independent of FFT convolution.
            filtered = np.column_stack([np.convolve(audio[first:stop, c], z['taps'], mode='same') for c in (0, 1)])
            ferr = close(z['filtered'], filtered, scale)
            query = (positions-start-first/48000)*48000
            assert np.array_equal(query, z['query'])
            poly = kernel(321, 1/32, 8.6)*16
            poly = np.r_[0., poly]
            dense = signal.upfirdn(poly, filtered, up=16, axis=0)[161:161+len(filtered)*16]
            indices = np.floor(query*16).astype(int)
            fraction = query*16-indices
            legacy = dense[indices]*(1-fraction[:, None])+dense[indices+1]*fraction[:, None]
            legacy_error = close(z['legacy'], legacy, scale)
            errors = {}
            for radius in (64, 128, 256):
                answer = np.zeros((len(query), 2)); normalizer = np.zeros(len(query))
                centers = np.floor(query).astype(int)
                for offset in range(1-radius, radius+1):
                    ids = centers+offset; assert ids.min() >= 0 and ids.max() < len(filtered)
                    d = query-ids
                    sinc = np.divide(np.sin(np.pi*d), np.pi*d, out=np.ones_like(d), where=d != 0)
                    weight = sinc*special.i0(12*np.sqrt(1-(d/radius)**2))/special.i0(12.)
                    answer += weight[:, None]*filtered[ids]; normalizer += weight
                answer /= normalizer[:, None]
                errors['sinc'+str(radius)] = close(z['sinc'+str(radius)], answer, scale)
            if known:
                offsets = np.arange(1025)-512
                gains = np.array([sum(z['taps']*np.cos(2*np.pi*freq*offsets/48000)) for freq in frequencies])
                truth = analytic(positions, gains)
                close(z['filtered_truth'], truth, scale)
                close(z['raw_truth'], analytic(positions, np.ones(len(frequencies))), scale)
                for name in ('legacy', 'sinc64', 'sinc128', 'sinc256'):
                    maximum = float(np.max(abs(z[name]-z['filtered_truth'])))
                    value = maximum/scale if scale else maximum
                    close(case['maximum_error_relative_source_L1'][name], value)
                    if name != 'legacy': assert value <= 2e-6
                    _, power = ordinary(z[name]-z['filtered_truth'])
                    tail = power.mean(axis=0)[frequency > 18432].sum(axis=0)
                    close(case['interpolation_error_above18432_Welch_FS2_LR'][name], tail)
                    if case['label'] == 'zero': assert np.count_nonzero(z[name]) == 0
                    if case['label'] == 'silent_right': assert np.count_nonzero(z[name][:, 1]) == 0
                    if case['label'] == 'mono': assert np.array_equal(z[name][:, 0], z[name][:, 1])
                close(case['source_FIR_effect_max_FS'], np.max(abs(z['raw_truth']-z['filtered_truth'])))
            else:
                reproduce = np.max(abs(z['legacy']-original['audio']))
                assert reproduce <= 2e-12
                close(case['legacy_original_reproduction_max_FS'], reproduce)
                baseline = z['legacy'][2048:-2048]
                base = moments(baseline)
                coverage = np.zeros(len(baseline))
                for begin in range(-3840, len(baseline), 256):
                    first_t, stop_t = max(begin, 0), min(begin+4096, len(baseline))
                    coverage[first_t:stop_t] += window[first_t-begin:stop_t-begin]**2
                for name in ('legacy', 'sinc64', 'sinc128', 'sinc256'):
                    target = z[name][2048:-2048]
                    X, power = ordinary(target)
                    mass = np.zeros((2049, 2))
                    for begin in range(0, len(target)-4096+1, 256):
                        row = np.fft.rfft(target[begin:begin+4096]*window[:, None]
                            /np.sqrt(coverage[begin:begin+4096, None]), axis=0)
                        row *= (float(z['amplitude'])*np.sqrt(endpoints/4096)*z['weights'])[:, None]
                        mass += abs(row)**2
                    close(z[name+'_weighted_mass'], mass)
                    close(z[name+'_Welch_FS2'], power.mean(axis=0))
                    row = case['measurements'][name]
                    close(row['highest_split_weighted_mass_LR'], [mass[m].sum(axis=0) for m in masks])
                    close(row['highest_split_Welch_FS2_LR'], [power.mean(axis=0)[m].sum(axis=0) for m in masks])
                    close(row['target_wave_NRMSE_vs_legacy'], np.linalg.norm(target-baseline)/np.linalg.norm(baseline))
                    close(row['target_wave_max_FS_vs_legacy'], np.max(abs(target-baseline)))
                    current = moments(target)
                    for key, value in current.items():
                        close(z[name+'_measured_broad_'+key], value)
                    changes = row['signed_stereo_and_temporal_changes_vs_legacy']
                    for key in ('mean_power', 'mean_mid_side'):
                        prefix = 'power' if key == 'mean_power' else 'mid_side'
                        close(changes[prefix+'_change_dB'], 10*np.log10(current[key]/base[key]), scale=1.)
                        close(changes[prefix+'_change_FS2'], current[key]-base[key], scale=float(np.max(abs(base[key]))))
                    close(changes['CV_change'], current['CV']-base['CV'], scale=1.)
                    dc = current['complex_coherence']-base['complex_coherence']
                    close(changes['complex_coherence_change'], np.column_stack((dc.real, dc.imag)), scale=1.)
                    for key in ('covariance', 'lag_covariance'):
                        close(changes[key+'_signed_change_FS4'], current[key]-base[key], scale=float(np.max(abs(base[key]))))
                        close(changes[key+'_relative_difference'], np.linalg.norm(current[key]-base[key])/np.linalg.norm(base[key]), scale=1.)
            r['cases'].append(dict(label=case['label'], direct_FIR_error_relative_source=ferr,
                independent_polyphase_and_linear_error_relative_source=legacy_error,
                all_query_sinc_errors_relative_source=errors, all_checked_fields_verified=True))
            save(a.out/'report.json', r); print('SOURCE_QUERY_AUDIT', case['label'], 'PASS', flush=True)
        if known:
            assert len(source['cases']) == 8 and len(source['invalid_rejections']) == 8
            assert source['maximum_error_gate_relative_source_L1'] == 2e-6
        else:
            assert len(source['cases']) == 6 and not source['original_source_fidelity_qualified']
            assert source['original_source_fidelity_gates_unchanged'] and not source['eligible_for_later_source_statistics']
        r.update(result='independent_source_resampling_verified', verification_passed=True,
            all_known_qualified=known, all_actual_cases_verified=not known,
            no_source_admission_or_sustained_voice_or_C_qualification=True)
        save(a.out/'report.json', r)
    except BaseException as error:
        r.update(result='failed', error=repr(error)); save(a.out/'report.json', r); raise


if __name__ == '__main__':
    main()
