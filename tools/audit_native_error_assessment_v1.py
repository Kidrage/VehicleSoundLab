"""Independent complete publication audit; imports no new producer modules."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from itertools import combinations
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
    from scipy import fft, signal
    a.out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, a.out/'executed_audit.py')
    r = dict(result='running', producer_sha256=sha(a.study/'report.json'), checks={}, auditor_sha256=sha(__file__))
    try:
        source = load(a.study/'report.json')
        assert source['result'] == 'native_error_assessment_published'
        for name, digest in source['sources'].items():
            assert sha(a.study/'exact_sources'/name) == digest
        for name, digest in source['inputs'].items():
            assert sha(name) == digest
        for group in ('arrays', 'figures'):
            for name, digest in source[group].items():
                assert sha(a.study/name) == digest
        assert not source['source_fidelity_qualified'] and not source['eligible_for_later_source_statistics']
        assert source['source_fidelity_gate_unchanged'] == .02
        assert source['no_physical_inverse_or_sustained_source_or_C_or_listening_qualification']
        window = .5-.5*np.cos(2*np.pi*np.arange(4096)/4096)
        endpoints = np.r_[1., np.full(2047, 2.), 1.]

        def check(name, saved, expected, gate=2e-11):
            saved, expected = np.asarray(saved), np.asarray(expected)
            assert saved.shape == expected.shape, (name, saved.shape, expected.shape)
            scale = float(np.max(abs(expected))) if expected.size else 0.
            error = float(np.max(abs(saved-expected))) if expected.size else 0.
            relative = error/scale if scale else error
            assert relative < gate, (name, relative, gate)
            r['checks'][name] = relative

        def observed(audio, weights, amplitude):
            starts = list(range(0, len(audio)-4096+1, 256))
            coverage = np.zeros(len(audio))
            # The declared coverage is a floating-point operator: accumulate
            # complete supports in ascending-start order, as in the original
            # locked observer. Reordering the sum perturbs very weak bins.
            all_starts = np.arange(-3840, len(audio), 256)
            for first in all_starts:
                indices = first+np.arange(4096)
                valid = (indices >= 0) & (indices < len(audio))
                coverage[indices[valid]] += window[valid]**2
            # Multiply the Hann BEFORE coverage division, matching the
            # declared pre-FFT samples. Dividing the source first is another
            # rounded operator; STFT's internal sum(window) normalization
            # adds a second avoidable round trip at a nearly empty bin.
            rows = np.array([fft.rfft(audio[first:first+4096]*window[:, None]
                /np.sqrt(coverage[first:first+4096, None]), axis=0) for first in starts])
            rows *= (amplitude*(np.sqrt(endpoints)/64)*weights)[None, :, None]
            _, _, ordinary = signal.stft(audio.T, window=window, nperseg=4096,
                noverlap=3840, boundary=None, padded=False)
            ordinary = ordinary.transpose(2, 1, 0)*window.sum()
            power = (abs(ordinary)**2).mean(axis=0)*endpoints[:, None]/(4096*sum(window**2))
            return rows, power, coverage, starts

        with np.load(a.study/'known.npz') as f:
            known = {k: f[k] for k in f.files}
        rows, power, coverage, starts = observed(known['audio'], known['weights'], .7)
        check('known_all_rows', known['rows'], rows)
        check('known_all_Welch', known['power'], power)
        check('known_full_coverage', known['coverage'], coverage)
        assert np.array_equal(starts, known['starts'])
        direct = np.empty_like(known['direct_DFT'])
        for first in range(0, 2049, 63):
            bins = np.arange(first, min(first+63, 2049))
            table = np.cos(2*np.pi*bins[:, None]*np.arange(4096)[None]/4096)
            table = table-1j*np.sin(2*np.pi*bins[:, None]*np.arange(4096)[None]/4096)
            direct[first:first+len(bins)] = table@(known['audio']*window[:, None]/np.sqrt(coverage[:, None]))
        direct *= (.7*np.sqrt(endpoints/4096)*known['weights'])[:, None]
        check('known_all2049_directDFT', known['direct_DFT'], direct)
        assert source['known']['passed'] and source['known']['gate'] == 2e-11
        case_path = next(Path(path).parent for path in source['inputs'] if Path(path).name == 'capture.npz')
        case = load(case_path/'report.json')
        assert case['solver_qualified'] and not case['fidelity_qualified']
        with np.load(case_path/'capture.npz') as f:
            target, fitted, weights, amplitude = f['target'], f['wave'][2048:-2048], f['weights'], float(f['amplitude'])
            assert np.array_equal(f['orders'], np.arange(1, 289))
        Y, yp, cov, starts = observed(target, weights, amplitude)
        E, ep, _, _ = observed(fitted-target, weights, amplitude)
        refmass, errmass = (abs(Y)**2).sum(axis=0), (abs(E)**2).sum(axis=0)
        frequency = np.arange(2049)*16
        band = np.digitize(frequency, [3000, 6000, 8000, 10000, 14000])
        split = np.array([(-1 if f < 14000 else 0 if f < 16000 else 1 if f < 18432
            else 2 if f == 18432 else 3) for f in frequency])
        with np.load(a.study/'virtual_split.npz') as f:
            arrays = {k: f[k] for k in f.files}
        for name, value in (('virtual_frequency', frequency), ('virtual_band', band), ('virtual_split', split),
            ('virtual_reference_weighted_mass', refmass), ('virtual_error_weighted_mass', errmass),
            ('virtual_reference_Welch_FS2', yp), ('virtual_error_Welch_FS2', ep),
            ('virtual_coverage', cov), ('virtual_starts', starts)):
            check(name, arrays[name], value)
        groups = [band == b for b in range(6)]+[split == b for b in range(4)]
        saved = source['virtual']['original_bands']+source['virtual']['highest_band_split']
        for j, (mask, row) in enumerate(zip(groups, saved)):
            assert row['bins'] == np.count_nonzero(mask)
            rp, err = refmass[mask].sum(axis=0), errmass[mask].sum(axis=0)
            for name, value in (('reference_weighted_mass_LR', rp), ('error_weighted_mass_LR', err),
                ('reference_Welch_FS2_LR', yp[mask].sum(axis=0)), ('error_Welch_FS2_LR', ep[mask].sum(axis=0))):
                check('group'+str(j)+'_'+name, row[name], value)
            check('group'+str(j)+'_NRMSE', row['combined_complex_NRMSE'], np.sqrt(err.sum()/rp.sum()))
        original = case['metrics']['target_supported_band_complex_NRMSE']
        check('original_all_six_NRMSE', source['original_target_NRMSE'], original, gate=2e-12)
        check('original_reproduced', [b['combined_complex_NRMSE'] for b in saved[:6]], original, gate=2e-12)
        for name, mass in (('reference', refmass), ('error', errmass)):
            fraction = mass[split == 3].sum()/mass[band == 5].sum()
            check(name+'_above_centre_fraction', source['virtual']['above_centre_'+name+'_fraction_of_highest_weighted_mass'], fraction)
            check(name+'_split_closure', sum(np.sum(mass[split == j]) for j in range(4)), np.sum(mass[band == 5]))
        assert source['virtual']['maximum_carrier_centre_Hz'] == 18432
        assert source['virtual']['maximum_carrier_centre_is_not_strict_bandwidth']
        assert source['virtual']['weighted_mass_is_not_acoustic_power']
        assert source['virtual']['virtual_rate'] == 65536 and source['virtual']['windows'] == len(starts)
        variants = []
        for j, row in enumerate(source['physical']):
            path = next(Path(path) for path in source['inputs'] if Path(path).name == row['file'])
            with np.load(path) as f:
                v = {k: f[k] for k in f.files}
            variants.append((row['file'], v))
            denominator = len(v['starts'])*4096*sum(window**2)
            for published, field in (('reference_Welch_FS2_LR', 'band_reference_power'),
                ('component_auto_Welch_FS2_LR', 'band_component_auto_power'),
                ('component_signed_cross_Welch_FS2_LR', 'band_component_signed_cross_power'),
                ('total_error_Welch_FS2_LR', 'band_error_power')):
                check(str(j)+published, row[published], v[field]/denominator)
            check(str(j)+'combined_component_NRMSE', row['combined_component_NRMSE'],
                np.sqrt(v['band_component_auto_power'].sum(axis=2)/v['band_reference_power'].sum(axis=1)[:, None]))
            check(str(j)+'combined_total_NRMSE', row['combined_total_NRMSE'],
                np.sqrt(v['band_error_power'].sum(axis=1)/v['band_reference_power'].sum(axis=1)))
            assert row['auto_and_signed_cross_powers_are_not_additive_percentages']
        physical_bands = np.digitize(np.arange(2049)*48000/4096, [3000, 6000, 8000, 10000, 14000])
        assert len(source['sensitivity']) == 6
        for j, ((an, av), (bn, bv)) in enumerate(combinations(variants, 2)):
            row = source['sensitivity'][j]
            assert (an, bn) == (row['first'], row['second'])
            delta = av['components']-bv['components']
            power = np.zeros((6, 4))
            for start in av['starts']:
                for component in range(4):
                    X = np.fft.rfft(delta[start:start+4096, component]*window[:, None], axis=0)
                    for b in range(6):
                        mask = physical_bands == b
                        power[b, component] += np.sum(abs(X[mask])**2*endpoints[mask, None])
            check(str(j)+'sensitivity_allbands', row['combined_component_band_NRMSE_relative_raw'],
                np.sqrt(power/av['band_reference_power'].sum(axis=1)[:, None]))
            check(str(j)+'sensitivity_whole', row['component_whole_NRMSE_relative_raw'],
                [np.linalg.norm(delta[:, component])/np.linalg.norm(av['raw']) for component in range(4)])
            check(str(j)+'sensitivity_continuous', row['continuous_whole_NRMSE_relative_raw'],
                np.linalg.norm(av['continuous_OSC']-bv['continuous_OSC'])/np.linalg.norm(av['raw']))
        r.update(result='independent_native_error_assessment_verified', all_publication_fields_verified=True,
            verification_passed=True, original_fidelity_failure_retained=True,
            all_bins_all_LR_all_four_variants_and_six_pairwise_sensitivities=True,
            source_fidelity_qualified=False, eligible_for_later_source_statistics=False)
        save(a.out/'report.json', r)
        print(r['result'], len(r['checks']), flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error)); save(a.out/'report.json', r); raise


if __name__ == '__main__':
    main()
