"""Independent lfilter/quantiles/binary CDF/OSC/STFT audit of time probes."""
import argparse
import math
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('workspace', 'study', 'out'):
        parser.add_argument('--'+key, type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[key] = '2'
    sys.path.insert(0, str(args.workspace/'tools/python_deps'))
    import numpy as np
    from scipy import signal, special
    args.out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, args.out/'executed_audit.py')
    report = dict(result='running', cases=[], waveforms=0, observer_rows=0,
                  maximum_wave_probe_error_FS=0., maximum_observer_error_FS=0.,
                  maximum_statistics_scaled_error=0., maximum_state_error=0.,
                  maximum_feature_error=0.)
    try:
        producer = load(args.study/'report.json')
        assert producer['result'] == 'six_source_conditional_time_probes_ready'
        for name, digest in producer['sources'].items():
            assert sha(repo/name) == sha(args.study/'exact_sources'/name) == digest
        for name, digest in producer['inputs'].items():
            assert sha(name) == digest
        plan = load(args.study/'exact_sources/research/conditional_phase_time_v1_plan.json')
        bands = plan['bands_Hz']
        gate = plan['checks']
        variants = plan['variants']

        def inverse(table, normal):
            count = len(table)
            nodes = np.r_[0., (np.arange(count)+.5)/count, 1.]
            probability = special.ndtr(normal)
            return np.column_stack([np.interp(probability[:, j], nodes,
                np.r_[table[0, j], table[:, j], table[-1, j]]) for j in range(table.shape[1])])

        def binary_phase(product, uniform, knots, cdf, lower, upper):
            # Evaluate only queried CDF boundaries; producer forms a complete
            # interpolated row then counts all boundaries instead.
            index = np.searchsorted(knots, product, side='right')-1
            index = np.clip(index, 0, len(knots)-2)
            weight = np.clip((product-knots[index])/(knots[index+1]-knots[index]), 0., 1.)
            def edge(j):
                return (1-weight)*cdf[index, j]+weight*cdf[index+1, j]
            lo = np.zeros(len(product), dtype=int)
            hi = np.full(len(product), len(lower)-1, dtype=int)
            while np.any(lo < hi):
                mid = (lo+hi)//2
                left = uniform < edge(mid+1)
                hi = np.where(left, mid, hi)
                lo = np.where(left, lo, mid+1)
            first, last = edge(lo), edge(lo+1)
            return lower[lo]+(uniform-first)/(last-first)*(upper[lo]-lower[lo])

        def statistics(power, cross):
            mean = np.mean(power, axis=0)
            centered = power-mean
            covariance = np.cov(power, rowvar=False, bias=True)
            valid = mean > 1e-24
            deviation = np.sqrt(np.maximum(0., np.diag(covariance)))
            cv = np.divide(deviation, mean, out=np.zeros_like(mean), where=valid)
            denominator = np.sqrt(mean[::2]*mean[1::2])
            stereo_valid = denominator > 1e-24
            cross_mean = cross.mean(axis=0)
            coherence = np.divide(cross_mean, denominator, out=np.zeros(len(denominator), complex), where=stereo_valid)
            lag = np.array([np.einsum('ni,nj->ij', centered[:-j], centered[j:], optimize=False)/(len(power)-j)
                            for j in range(1, min(9, len(power)))])
            return dict(mean=mean, covariance=covariance, CV=cv, power_defined=valid,
                        complex_coherence=coherence, coherence_defined=stereo_valid,
                        mid_power=(mean[::2]+mean[1::2]+2*cross_mean.real)/4,
                        side_power=(mean[::2]+mean[1::2]-2*cross_mean.real)/4,
                        lag_covariance=lag)

        def compare_stats(actual, saved, prefix, json_encoded=False):
            mean = actual['mean']
            scales = dict(mean=np.maximum(mean, 1e-24),
                          covariance=np.maximum(np.outer(mean, mean), 1e-48),
                          lag_covariance=np.maximum(np.outer(mean, mean), 1e-48),
                          mid_power=np.maximum((mean[::2]+mean[1::2])/2, 1e-24),
                          side_power=np.maximum((mean[::2]+mean[1::2])/2, 1e-24))
            for key, value in actual.items():
                target = np.asarray(saved[prefix+key])
                if json_encoded and np.iscomplexobj(value):
                    target = target[..., 0]+1j*target[..., 1]
                if value.dtype.kind == 'b':
                    assert np.array_equal(value, target), prefix+key
                    continue
                error = float(np.max(abs(value-target)/scales.get(key, 1.)))
                assert error < gate['independent_stats_relative'], (prefix+key, error)
                report['maximum_statistics_scaled_error'] = max(report['maximum_statistics_scaled_error'], error)

        def observe(wave, root):
            frequency, _, stft = signal.stft(wave.T, fs=1024*root, window='hann', nperseg=4096,
                noverlap=3840, boundary=None, padded=False)
            starts = np.arange(0, len(wave)-4096+1, 256)
            orders = np.arange(1, 289)
            z = np.moveaxis(stft[:, 4*orders, :], (0, 1, 2), (2, 1, 0))*2
            z *= np.exp(-2j*np.pi*np.remainder(starts[:, None]*orders/1024, 1))[..., None]
            scale = np.full(len(frequency), 4/3)
            scale[[0, -1]] = 2/3
            line, line_cross, broad, broad_cross = [], [], [], []
            for low, high in bands:
                mask = (orders*root >= low)&(orders*root < high)
                line.append((abs(z[:, mask])**2).sum(axis=1)/2)
                line_cross.append((z[:, mask, 0]*z[:, mask, 1].conj()).sum(axis=1)/2)
                mask = (frequency >= low)&(frequency < high)
                broad.append((abs(stft[:, mask])**2*scale[mask, None]).sum(axis=1).T)
                broad_cross.append((stft[0, mask]*stft[1, mask].conj()*scale[mask, None]).sum(axis=0))
            return z, np.concatenate(line, axis=1), np.stack(line_cross, axis=1), np.concatenate(broad, axis=1), np.stack(broad_cross, axis=1)

        for row in producer['cases']:
            label, root = row['label'], row['root_hz']
            folder = args.study/label
            assert sha(folder/'bundle.npz') == row['bundle_sha256']
            assert sha(folder/'source.npz') == row['source_sha256']
            bundle = dict(np.load(folder/'bundle.npz', allow_pickle=False))
            model = {key[6:]: value for key, value in bundle.items() if key.startswith('model_')}
            # Bundled inputs must be literal copies of independently frozen parents.
            original = dict(np.load(args.workspace/f'baselines/relative_phase_v1/evidence/real1/{label}/profile.npz'))
            assert set(model) == set(original)
            assert all(np.array_equal(model[key], original[key]) for key in original)
            with np.load(folder/'source.npz') as saved:
                source_wave = saved['audio']
                with np.load(args.workspace/f'baselines/coefficient_geometry_v1/evidence/real1/{label}/source.npz') as native:
                    assert np.array_equal(source_wave, native['rebuilt'])
                observed = observe(source_wave, root)
                source_rows = saved['source_rows'].reshape(-1, 288, 2, 2)
                target = source_rows[..., 0]+1j*source_rows[..., 1]
                assert abs(observed[0]-target).max() < gate['source_rows_FS']
                for prefix, power, cross in [('line_', observed[1], observed[2]), ('broad_', observed[3], observed[4])]:
                    stats = statistics(power, cross)
                    compare_stats(stats, saved, prefix)
                    compare_stats(stats, row['source_statistics'], prefix, True)
                report['observer_rows'] += len(target)
            rho = np.r_[model['rho'], model['residual_rho']]
            k = len(model['rho'])
            frames = 1024*plan['cycles']
            n = np.arange(frames)
            at = n//256
            fraction = n%256/256.
            orders = np.arange(1, 289)
            taper_x = np.clip((orders*root-19200)/2400, 0., 1.)
            taper = 1-3*taper_x**2+2*taper_x**3
            masks = [(orders*root >= low)&(orders*root < high) for low, high in bands]
            for seed_row in row['seeds']:
                seed = seed_row['seed']
                path = folder/f'probe_{seed}.npz'
                assert sha(path) == seed_row['sha256']
                with np.load(path) as saved:
                    states = []
                    for random_seed, name in [(seed, 'state'), (np.random.SeedSequence([seed, 789783]), 'independent_state')]:
                        noise = np.random.Generator(np.random.PCG64(random_seed)).standard_normal(saved[name].shape)
                        state = np.empty_like(noise)
                        for j, r in enumerate(rho):
                            scale = math.sqrt(1-r*r)
                            state[:, j] = signal.lfilter([scale], [1., -r], noise[:, j], zi=[(1-scale)*noise[0, j]])[0]
                        error = float(abs(state-saved[name]).max())
                        assert error < 2e-12
                        report['maximum_state_error'] = max(report['maximum_state_error'], error)
                        states.append(state)
                    amplitude = np.empty((frames, 288, 2))
                    common = np.empty((frames, 288))
                    relative = np.empty((frames, 288))
                    uniform = np.empty((frames, 288))
                    probes = saved['probe_positions']
                    for start in range(0, frames, 1024):
                        end = min(start+1024, frames)
                        u = fraction[start:end, None]
                        normals = []
                        for state in states:
                            interpolated = ((1-u)*state[at[start:end]]+u*state[at[start:end]+1])/np.sqrt((1-u)**2+u*u+2*rho*u*(1-u))
                            normals.append(np.einsum('nk,dk->nd', interpolated[:, :k], model['basis'], optimize=False)
                                           +interpolated[:, k:]*model['residual_std'])
                        amplitude[start:end] = inverse(model['amplitude'], normals[0][:, :576]).reshape(-1, 288, 2)
                        common[start:end] = inverse(model['phase'][:, :288], normals[0][:, 576:864])
                        relative[start:end] = inverse(model['phase'][:, 288:], normals[0][:, 864:])
                        uniform[start:end] = special.ndtr(normals[1][:, 864:])
                        mask = (probes >= start)&(probes < end)
                        for feature, target_name in zip(normals, ['probe_normal', 'probe_independent_normal']):
                            error = float(abs(feature[probes[mask]-start]-saved[target_name][mask]).max()) if mask.any() else 0.
                            assert error < 2e-12
                            report['maximum_feature_error'] = max(report['maximum_feature_error'], error)
                    assert abs(amplitude[probes]-saved['probe_amplitude']).max() < 2e-12
                    assert abs(common[probes]-saved['probe_common']).max() < 2e-12
                    assert abs(relative[probes]-saved['probe_relative']).max() < 2e-12
                    assert abs(uniform[probes]-saved['probe_uniform']).max() < 2e-12
                    tapered = amplitude*taper[None, :, None]
                    instant_power = np.concatenate([(tapered[:, mask]**2).sum(axis=1)/2 for mask in masks], axis=1)
                    instant_cross = {name: np.zeros((frames, 4), complex) for name in variants}
                    wave_probes = {name: np.zeros((len(probes), 2)) for name in variants}
                    outside = np.zeros((288, 2), dtype=int)
                    for h in range(288):
                        product = amplitude[:, h, 0]*amplitude[:, h, 1]/bundle['mean_product'][h]
                        knots = bundle['knots'][h]
                        outside[h] = [(product < knots[0]).sum(), (product > knots[-1]).sum()]
                        deltas = dict(fixed=np.full(frames, model['fixed_phase'][h, 0]-model['fixed_phase'][h, 1]), relative=relative[:, h])
                        for name in ('parent', 'density', 'variation'):
                            deltas[name] = binary_phase(product, uniform[:, h], knots, bundle[name][h], bundle['low'][h], bundle['high'][h])
                        for name, delta in deltas.items():
                            if name != 'fixed':
                                assert abs(abs(np.diff(delta)).max()-saved[name+'_maximum_unwrapped_relative_phase_step'][h]) < 2e-8
                            for band, mask in enumerate(masks):
                                if mask[h]:
                                    instant_cross[name][:, band] += tapered[:, h, 0]*tapered[:, h, 1]*np.exp(1j*delta)/2
                            angles = model['fixed_phase'][h] if name == 'fixed' else np.column_stack([common[probes, h]+delta[probes]/2, common[probes, h]-delta[probes]/2])
                            for j, sample in enumerate(probes):
                                for channel in (0, 1):
                                    phase = angles[channel] if name == 'fixed' else angles[j, channel]
                                    wave_probes[name][j, channel] += tapered[sample, h, channel]*math.cos(2*math.pi*(int(sample)%1024)*(h+1)/1024+phase)
                    assert np.array_equal(outside, saved['outside_P_counts'])
                    assert np.array_equal(np.asarray(seed_row['outside_P_fraction']), outside.sum(axis=1)/frames)
                    for name in variants:
                        compare_stats(statistics(instant_power, instant_cross[name]), saved, name+'_instant_')
                        wave = saved[name+'_audio']
                        error = float(abs(wave_probes[name]-wave[probes]).max())
                        assert error < gate['independent_waveform_FS'], (label, seed, name, error)
                        report['maximum_wave_probe_error_FS'] = max(report['maximum_wave_probe_error_FS'], error)
                        observed = observe(wave, root)
                        error = float(abs(observed[0]-saved[name+'_coefficients']).max())
                        assert error < gate['independent_waveform_FS']
                        report['maximum_observer_error_FS'] = max(report['maximum_observer_error_FS'], error)
                        for key, value in zip(['power', 'cross', 'broadband_power', 'broadband_cross'], observed[1:]):
                            denominator = max(float(abs(saved[name+'_broadband_power']).max()), 1e-24)
                            assert abs(value-saved[name+'_'+key]).max()/denominator < gate['independent_stats_relative']
                        for prefix, power, cross in [('line_', observed[1], observed[2]), ('broad_', observed[3], observed[4])]:
                            stats = statistics(power, cross)
                            compare_stats(stats, saved, name+'_'+prefix)
                            compare_stats(stats, seed_row['variants'][name], prefix, True)
                            chunks = []
                            count = row['source_rows']
                            for start in range(0, len(power)-count+1, count):
                                chunks.append(statistics(power[start:start+count], cross[start:start+count]))
                            for field in ('mean', 'CV', 'complex_coherence'):
                                assert abs(np.stack([chunk[field] for chunk in chunks])-saved[name+'_chunks_'+prefix+field]).max() < gate['independent_stats_relative']
                        assert len(observed[0]) == seed_row['observed_rows'] == 241
                        report['waveforms'] += 1
                        report['observer_rows'] += len(observed[0])
                    del amplitude, common, relative, uniform, tapered
                print('AUDITED waveform, instantaneous and reobserved statistics', label, seed, flush=True)
            report['cases'].append(dict(label=label, seeds=len(row['seeds']), original_rows=row['source_rows']))
            save(args.out/'report.json', report)
        assert report['waveforms'] == 90
        report.update(result='independent_conditional_time_real_audit_passed',
                      producer_sha256=sha(args.study/'report.json'), auditor_sha256=sha(__file__),
                      all_instantaneous_reobserved_and_JSON_statistics_verified=True,
                      normalized_coordinate_only=True, heard=False)
        save(args.out/'report.json', report)
        print(report['result'])
    except BaseException as error:
        report.update(result='failed', error=repr(error))
        save(args.out/'report.json', report)
        raise


if __name__ == '__main__':
    main()
