"""Independent finite-tone/STFT Gram matrices and scalar per-group OSC probes."""
import argparse
import math
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'study', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--stage', choices=['known', 'real'], required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(args.workspace/'tools/python_deps'))
    import numpy as np
    from scipy import signal
    args.out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, args.out/'executed_audit.py')
    report = dict(result='running', cases=[], matrices=0, maximum_Gram_scaled_error=0.,
                  maximum_analytic_STFT_error_FS=0., maximum_scalar_probe_error_FS=0.,
                  maximum_parent_recovery_scaled_error=0., maximum_wave_sum_error_FS=0.,
                  maximum_real_per_band_Gram_scaled_error=0.)
    try:
        source = load(args.study/'report.json')
        assert source['result'] == ('carrier_transfer_known_ready' if args.stage == 'known' else 'all90_carrier_partitions_ready')
        for name, digest in source['sources'].items():
            assert sha(repo/name) == sha(args.study/'exact_sources'/name) == digest
        for name, digest in source['inputs'].items():
            assert sha(name) == digest
        plan = load(args.study/'exact_sources/research/carrier_transfer_v1_plan.json')
        gate = plan['checks']
        route = np.zeros((2, 12))
        route[0, ::2] = 1
        route[1, 1::2] = 1

        def stft(audio, root):
            frequency, _, spectrum = signal.stft(audio.reshape(len(audio), 12).T, fs=1024*root,
                window='hann', nperseg=4096, noverlap=3840, boundary=None, padded=False)
            return frequency, np.moveaxis(spectrum, (0, 1, 2), (2, 1, 0))

        def matrices(spectrum, frequency, root):
            weights = np.full(len(frequency), 4/3)
            weights[[0, -1]] = 2/3
            def gram(value, scale):
                return np.einsum('wfi,wfj,f->wij', value, value.conj(), scale, optimize=True)
            all_frequency = gram(spectrum, weights)
            line, broad = [], []
            orders = np.arange(1, 289)
            for low, high in plan['bands_Hz']:
                chosen = (frequency >= low)&(frequency < high)
                broad.append(gram(spectrum[:, chosen], weights[chosen]))
                at = orders[(orders*root >= low)&(orders*root < high)]*4
                line.append(gram(spectrum[:, at], np.full(len(at), 2.)))
            return dict(line_Gram=np.stack(line, axis=1), broad_Gram=np.stack(broad, axis=1), all_frequency_Gram=all_frequency)

        def verify_file(path, root, digest, expected_tones=None, parent=None, variant=None, bundle=None):
            assert sha(path) == digest
            with np.load(path) as raw:
                audio = raw['grouped_audio']
                frequency, spectrum = stft(audio, root)
                if expected_tones is not None:
                    starts = np.arange(0, len(audio)-4096+1, 256)
                    bins = np.arange(2049)/4096
                    analytic = np.zeros_like(spectrum)
                    def geometric(x):
                        x = np.remainder(x+.5, 1)-.5
                        return 4096*np.exp(1j*np.pi*4095*x)*np.sinc(4096*x)/np.sinc(x)
                    def kernel(x):
                        return (.5*geometric(x)-.25*geometric(x+1/4096)-.25*geometric(x-1/4096))/2048
                    for tag, channel, order, real, imaginary in expected_tones:
                        z = complex(real, imaginary)
                        at = 2*int(tag)+int(channel)
                        phase = np.exp(2j*np.pi*np.remainder(starts*order/1024, 1))
                        analytic[:, :, at] += .5*z*phase[:, None]*kernel(order/1024-bins)
                        analytic[:, :, at] += .5*z.conjugate()*phase[:, None].conj()*kernel(-order/1024-bins)
                    error = float(abs(analytic-spectrum).max())
                    assert error < gate['known_analytic_FS'], error
                    report['maximum_analytic_STFT_error_FS'] = max(report['maximum_analytic_STFT_error_FS'], error)
                    spectral_matrices = matrices(analytic, frequency, root)
                else:
                    spectral_matrices = matrices(spectrum, frequency, root)
                scale = max(float(np.diagonal(spectral_matrices['all_frequency_Gram'], axis1=-2, axis2=-1).real.sum(axis=-1).max()), 1e-24)
                for key, value in spectral_matrices.items():
                    error = float(abs(value-raw[key]).max()/scale)
                    assert error < gate['independent_Gram_scaled'], (path.name, key, error)
                    report['maximum_Gram_scaled_error'] = max(report['maximum_Gram_scaled_error'], error)
                    if key == 'all_frequency_Gram':
                        assert abs(value.real-raw['time_energy_Gram']).max()/scale < gate['Parseval_scaled']
                        continue
                    prefix = key.removesuffix('_Gram')
                    if parent is not None:
                        band_scale = np.maximum(np.diagonal(value, axis1=-2, axis2=-1).real.sum(axis=-1).mean(axis=0), 1e-24)
                        band_error = float((abs(value-raw[key])/band_scale[None, :, None, None]).max())
                        assert band_error < gate['independent_Gram_scaled'], (path.name, key, band_error)
                        report['maximum_real_per_band_Gram_scaled_error'] = max(report['maximum_real_per_band_Gram_scaled_error'], band_error)
                    mean = value.mean(axis=0)
                    total = np.einsum('ai,bij,cj->bac', route, mean, route, optimize=False)
                    diagonal = np.diagonal(mean, axis1=-2, axis2=-1).real.reshape(4, 6, 2)
                    low = diagonal[:, 0]
                    rest = np.empty((4, 2))
                    cross = np.empty((4, 2))
                    for band in range(4):
                        for channel in (0, 1):
                            rest[band, channel] = sum(mean[band, 2*g+channel, 2*h+channel].real for g in range(1, 6) for h in range(1, 6))
                            cross[band, channel] = 2*sum(mean[band, channel, 2*h+channel].real for h in range(1, 6))
                    for field, expected in [('group_self_power', diagonal), ('low_power', low), ('rest_power', rest),
                        ('signed_low_rest_cross', cross), ('total_power', total[:, [0, 1], [0, 1]].real),
                        ('signed_all_group_cross', total[:, [0, 1], [0, 1]].real-diagonal.sum(axis=1)),
                        ('complex_LR', total[:, 0, 1])]:
                        assert abs(raw[prefix+'_'+field]-expected).max()/scale < gate['independent_Gram_scaled'], field
                    assert abs(low+rest+cross-total[:, [0, 1], [0, 1]].real).max()/scale < gate['independent_Gram_scaled']
                    if parent is not None:
                        full = np.einsum('ai,wbij,cj->wbac', route, value, route, optimize=False)
                        power = full[:, :, [0, 1], [0, 1]].real.reshape(len(full), 8)
                        target = parent[variant+('_power' if prefix == 'line' else '_broadband_power')]
                        target_cross = parent[variant+('_cross' if prefix == 'line' else '_broadband_cross')]
                        target_scale = np.maximum(target.reshape(len(full), 4, 2).mean(axis=(0, 2)), 1e-24)
                        error = max(float((abs(power-target).reshape(len(full), 4, 2)/target_scale[None, :, None]).max()),
                                    float((abs(full[:, :, 0, 1]-target_cross)/target_scale[None]).max()))
                        assert error < gate['recovered_parent_scaled']
                        report['maximum_parent_recovery_scaled_error'] = max(report['maximum_parent_recovery_scaled_error'], error)
                    report['matrices'] += int(np.prod(value.shape[:2]))
                if parent is not None:
                    error = float(abs(audio.sum(axis=1)-parent[variant+'_audio']).max())
                    assert error < gate['wave_sum_FS']
                    report['maximum_wave_sum_error_FS'] = max(report['maximum_wave_sum_error_FS'], error)
                    # Each nominal carrier group is independently reconstructed
                    # at all37 parent sample probes, using scalar CDFs and OSC.
                    wanted = np.zeros((37, 6, 2))
                    probes = parent['probe_positions']
                    tags = np.searchsorted(np.asarray(plan['carrier_edges_Hz']), np.arange(1, 289)*root, side='right')-1
                    assert np.array_equal(tags, raw['group_tags'])
                    for j, sample in enumerate(probes):
                        for h in range(288):
                            amplitude = parent['probe_amplitude'][j, h]
                            if variant == 'fixed':
                                phase = bundle['model_fixed_phase'][h]
                            else:
                                common = parent['probe_common'][j, h]
                                if variant == 'relative':
                                    delta = parent['probe_relative'][j, h]
                                else:
                                    product = amplitude[0]*amplitude[1]/bundle['mean_product'][h]
                                    probability = parent['probe_uniform'][j, h]
                                    cdf = [float(np.interp(product, bundle['knots'][h], bundle[variant][h, :, column])) for column in range(bundle[variant].shape[-1])]
                                    cell = min(next((q for q in range(len(cdf)-1) if probability < cdf[q+1]), len(cdf)-2), len(cdf)-2)
                                    u = (probability-cdf[cell])/(cdf[cell+1]-cdf[cell])
                                    delta = bundle['low'][h, cell]+u*(bundle['high'][h, cell]-bundle['low'][h, cell])
                                phase = [common+delta/2, common-delta/2]
                            x = max(0., min(1., ((h+1)*root-19200)/2400))
                            for channel in (0, 1):
                                wanted[j, tags[h], channel] += amplitude[channel]*(1-3*x*x+2*x*x*x)*math.cos(2*math.pi*(int(sample)%1024)*(h+1)/1024+phase[channel])
                    error = float(abs(wanted-audio[probes]).max())
                    assert error < gate['independent_probe_FS'], error
                    report['maximum_scalar_probe_error_FS'] = max(report['maximum_scalar_probe_error_FS'], error)

        if args.stage == 'known':
            for row in source['cases']:
                path = args.study/(row['label']+'.npz')
                with np.load(path) as raw:
                    tones = raw['tones'].copy()
                verify_file(path, 64., row['sha256'], expected_tones=tones)
                with np.load(path) as raw:
                    cross = raw['broad_signed_low_rest_cross'][0]
                    if row['label'] == 'positive_cross':
                        assert np.all(cross > 0)
                    if row['label'] == 'negative_cross':
                        assert np.all(cross < 0)
                    if row['label'] in ('low_AM_sidebands', 'low_PM_sidebands'):
                        assert np.all(raw['broad_group_self_power'][:2, 0] > 0)
                    if row['label'] == 'silence':
                        assert not raw['grouped_audio'].any() and not raw['all_frequency_Gram'].any()
                report['cases'].append(dict(label=row['label'], analytic_and_STFT_Gram_verified=True))
            report['result'] = 'independent_carrier_transfer_known_passed'
        else:
            parent = args.workspace/'baselines/conditional_phase_time_v1/evidence/real1'
            for row in source['cases']:
                label = row['label']
                with np.load(parent/label/'bundle.npz') as old:
                    bundle = {name:old[name] for name in old.files}
                for seed in row['seeds']:
                    with np.load(parent/label/f'probe_{seed["seed"]}.npz') as capture:
                        for variant, descriptor in seed['variants'].items():
                            verify_file(args.study/label/descriptor['file'], row['root_hz'], descriptor['sha256'], parent=capture, variant=variant, bundle=bundle)
                    print('AUDITED group probes and full spectral accounting', label, seed['seed'], flush=True)
                report['cases'].append(dict(label=label, waveforms=sum(len(seed['variants']) for seed in row['seeds'])))
                save(args.out/'report.json', report)
            assert sum(case['waveforms'] for case in report['cases']) == 90
            report['result'] = 'independent_carrier_transfer_real_passed'
        report.update(producer_sha256=sha(args.study/'report.json'), auditor_sha256=sha(__file__), physical_source_separation=False)
        save(args.out/'report.json', report)
        print(report['result'])
    except BaseException as error:
        report.update(result='failed', error=repr(error))
        save(args.out/'report.json', report)
        raise


if __name__ == '__main__':
    main()
