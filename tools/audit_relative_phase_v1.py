"""Independent stereo reconstruction, ranks, moments and copula decoding checks."""
import argparse
import hashlib
import math
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for n in ('workspace', 'study', 'out'):
        p.add_argument('--'+n, type=Path, required=True)
    a = p.parse_args(); repo = Path(__file__).resolve().parents[1]
    for n in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[n] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy import special
    from scipy.stats import qmc
    a.out.mkdir(parents=True, exist_ok=False); shutil.copy2(__file__, a.out/'executed_audit.py')
    report = dict(result='running', cases=[], QMC_cases=0, maximum_roundtrip_FS=0.,
                  maximum_power_relative_error=0., maximum_covariance_normalized_error=0.,
                  maximum_phase_budget_error=0.)
    try:
        producer = load(a.study/'report.json')
        assert producer['result'] in ('relative_phase_known_controls_passed', 'six_source_relative_phase_evidence_ready')
        for name, h in producer['sources'].items():
            assert sha(repo/name) == sha(a.study/'exact_sources'/name) == h
        for name, h in producer['inputs'].items():
            assert sha(name) == h
        plan = load(a.study/'exact_sources/research/relative_phase_v1_plan.json')
        def inverse(table, normal):
            probability = .5+.5*special.erf(normal/math.sqrt(2))
            count = len(table); positions = np.r_[0, (np.arange(count)+.5)/count, 1]
            return np.column_stack([np.interp(probability[:, j], positions,
                np.r_[table[0, j], table[:, j], table[-1, j]]) for j in range(table.shape[1])])
        def reconstruct(profile, normal):
            h = len(profile['fixed_phase']); k = len(profile['rho'])
            features = np.einsum('nk,dk->nd', normal[:, :k], profile['basis'], optimize=False)
            features += normal[:, k:]*profile['residual_std']
            amplitude = inverse(profile['amplitude'], features[:, :2*h]).reshape(len(normal), h, 2)
            coordinate = inverse(profile['phase'], features[:, 2*h:])
            phase = np.empty_like(amplitude)
            phase[..., 0] = coordinate[:, :h]+coordinate[:, h:]/2
            phase[..., 1] = coordinate[:, :h]-coordinate[:, h:]/2
            return amplitude, phase
        def moments(amplitude, phase, root):
            power = []; coherence = []; hz = np.arange(1, amplitude.shape[1]+1)*root
            for lo, hi in plan['bands_Hz']:
                orders = np.flatnonzero((hz>=lo)&(hz<hi))
                for c in (0, 1):
                    power.append(np.einsum('nh,nh->n', amplitude[:, orders, c], amplitude[:, orders, c], optimize=False)/2)
                d = phase[:, orders, 0]-phase[:, orders, 1]
                product = amplitude[:, orders, 0]*amplitude[:, orders, 1]
                cross = np.sum(product*(np.cos(d)+1j*np.sin(d)))/len(amplitude)
                e = [np.sum(amplitude[:, orders, c]**2)/len(amplitude) for c in (0, 1)]
                coherence.append(cross/math.sqrt(e[0]*e[1]))
            power = np.array(power).T; mean = power.mean(axis=0)
            centered = power-mean
            covariance = np.einsum('ni,nj->ij', centered, centered, optimize=False)/len(power)
            return power, mean, covariance, np.array(coherence)
        summary_errors = {k: [] for k in ('old_fixed', 'old_absolute', 'relative', 'new_fixed')}
        cvs = {k: [] for k in ('source', 'old', 'new')}
        prior = None
        if producer['stage'] == 'real':
            prior_path = a.workspace/'baselines/radial_copula_v1/evidence/real2/report.json'
            assert sha(prior_path) == producer['inputs'][str(prior_path)]
            prior = load(prior_path)
        for row in producer['cases']:
            folder = a.study/row['label']
            assert sha(folder/'profile.npz') == row['profile_sha256']
            assert sha(folder/'training.npz') == row['training_sha256']
            model = dict(np.load(folder/'profile.npz')); training = np.load(folder/'training.npz')
            raw = training['source_rows']; n = len(raw); h = raw.shape[1]//4
            parts = raw.reshape(n, h, 2, 2); source = parts[..., 0]+1j*parts[..., 1]
            coordinate = training['coordinates']; common = coordinate[:, :h]; delta = coordinate[:, h:]
            phi = np.stack([common+delta/2, common-delta/2], axis=-1)
            error = float(abs(abs(source)*np.exp(1j*phi)-source).max())
            assert error <= plan['checks']['source_coordinate_roundtrip_FS']
            report['maximum_roundtrip_FS'] = max(report['maximum_roundtrip_FS'], error)
            # Verify both circular coordinates and the selected branches from source.
            relative = np.angle(source[..., 0]*source[..., 1].conj())
            for j in range(h):
                angles = sorted(float(x) for x in relative[:, j])
                gaps = [angles[i+1]-angles[i] for i in range(n-1)]+[angles[0]+2*math.pi-angles[-1]]
                at = int(np.argmax(gaps)); cut = angles[at]+gaps[at]/2
                assert abs(cut-model['phase_cuts'][h+j]) < 2e-12
                expected = cut+np.mod(relative[:, j]-cut, 2*math.pi)
                assert abs(expected-delta[:, j]).max() < 2e-12
            # Silence has no identifiable phase; signed complex zeros can choose
            # different angles. Its actual reconstruction and amplitude remain
            # strictly checked, rather than treating angle(0) as source evidence.
            nonzero = abs(source[..., 0])>0
            assert abs(np.exp(1j*common[nonzero])-np.exp(1j*(np.angle(source[..., 0])[nonzero]-delta[nonzero]/2))).max(initial=0) < 2e-12
            assert np.array_equal(model['phase'], np.sort(coordinate, axis=0))
            amplitude = abs(source).reshape(n, 2*h)
            second = np.mean(amplitude**2, axis=0)
            table = model['amplitude']; x, y = table[:-1], table[1:]
            integrated = (.5*table[0]**2+.5*table[-1]**2+np.sum((x*x+x*y+y*y)/3, axis=0))/n
            assert np.all(abs(integrated-second) <= 2e-12*np.maximum(second, 1e-30))
            assert np.array_equal(table, np.sort(amplitude, axis=0)*training['normalization'])
            # Independent pairwise midranks, not the compiler's sorting routine.
            feature = np.column_stack([amplitude, coordinate]); scores = np.zeros_like(feature)
            for j in np.flatnonzero(model['active']):
                value = feature[:, j]
                rank = (value[:, None]>value[None, :]).sum(axis=1)+(.5+.5*(value[:, None]==value[None, :]).sum(axis=1))
                normal = math.sqrt(2)*special.erfinv(2*(rank-.5)/n-1)
                normal -= normal.mean(); scores[:, j] = normal/math.sqrt(np.mean(normal**2))
            assert abs(scores-training['scores']).max(initial=0) < 2e-12
            assert abs(training['pc']@model['basis'].T+training['residual']-scores).max(initial=0) < 2e-12
            assert abs(np.sum(model['basis']**2, axis=1)+model['residual_std']**2-model['active']).max(initial=0) < 2e-12
            for values, expected in [(training['pc'], model['rho']), (training['residual'], model['residual_rho'])]:
                actual = []
                for column in values.T:
                    denominator = math.fsum(float(v*v) for v in column[:-1])
                    v = math.fsum(float(x*y) for x, y in zip(column[:-1], column[1:]))/denominator if denominator>1e-20 else 0
                    actual.append(max(-.95, min(.95, v)))
                assert abs(np.array(actual)-expected).max(initial=0) < 2e-12
            if producer['stage'] == 'known':
                normal = np.random.Generator(np.random.PCG64(1)).standard_normal((4096, model['basis'].shape[0]+len(model['rho'])))
                amp, phase = reconstruct(model, normal)
                if row['label'] in ('common_PM', 'relative_PM', 'wrap', 'rotated', 'swapped'):
                    assert abs(amp-.1).max() < 2e-14
                if row['label'] in ('identical_stereo', 'common_PM', 'opposed_AM', 'fixed_relative'):
                    target = .7 if row['label'] == 'fixed_relative' else 0
                    assert abs(np.angle(np.exp(1j*(phase[..., 0]-phase[..., 1]-target)))).max() < 2e-12
                if row['label'] == 'silence': assert np.count_nonzero(amp) == 0
            def check_descriptor(descriptor, power, mean, cov, coherence):
                encoded = np.array(descriptor['complex_coherence'])
                assert abs(encoded[:, 0]+1j*encoded[:, 1]-coherence).max() < 2e-12
                assert abs(np.array(descriptor['mean'])/mean-1).max() < 2e-12
                assert (abs(np.array(descriptor['covariance'])-cov)/np.outer(mean,mean)).max() < 2e-10
                assert abs(np.array(descriptor['CV'])-np.sqrt(np.diag(cov))/mean).max() < 2e-12
            relative_coherences, fixed_coherences, generated_cvs = [], [], []
            if prior:
                source_power, source_mean, source_cov, source_coherence = moments(abs(source), np.angle(source), row['root_hz'])
                check_descriptor(row['source'], source_power, source_mean, source_cov, source_coherence)
            for q in row.get('QMC', []):
                path = folder/f'QMC_{q["seed"]}.npz'; assert sha(path) == q['sha256']
                saved = np.load(path)
                uniform = qmc.Sobol(d=model['basis'].shape[0]+len(model['rho']), scramble=True, seed=q['seed']).random_base2(plan['QMC']['power'])
                assert hashlib.sha256(uniform.tobytes()).hexdigest() == q['uniform_bytes_sha256']
                normal = math.sqrt(2)*special.erfinv(2*uniform-1)
                amp, phase = reconstruct(model, normal)
                power, mean, cov, coherence = moments(amp, phase, row['root_hz'])
                relative = float((abs(power-saved['relative_power'])/mean).max())
                covariance = float((abs(cov-saved['relative_covariance'])/np.outer(mean, mean)).max())
                assert relative < 2e-10 and covariance < 2e-10
                assert abs(coherence-saved['relative_complex_coherence']).max() < 2e-12
                check_descriptor(q['relative'], power, mean, cov, coherence)
                fixed_power, fixed_mean, fixed_cov, fixed_coherence = moments(amp, np.broadcast_to(model['fixed_phase'], phase.shape), row['root_hz'])
                check_descriptor(q['fixed'], fixed_power, fixed_mean, fixed_cov, fixed_coherence)
                assert abs(saved['fixed_complex_coherence']-fixed_coherence).max() < 2e-12
                relative_coherences.append(coherence); fixed_coherences.append(fixed_coherence)
                generated_cvs.append(np.sqrt(np.diag(cov))/mean)
                report['maximum_power_relative_error'] = max(report['maximum_power_relative_error'], relative)
                report['maximum_covariance_normalized_error'] = max(report['maximum_covariance_normalized_error'], covariance)
                for prefix, A, P in [('budget_', amp, phase), ('source_budget_', abs(source), np.angle(source))]:
                    d = P[..., 0]-P[..., 1]; turn = np.cos(d)+1j*np.sin(d); product = A[..., 0]*A[..., 1]
                    phase_moment = turn.mean(axis=0); product_mean = product.mean(axis=0)
                    association = np.mean(product*turn, axis=0)-product_mean*phase_moment
                    for key, value in [('relative_phase_moment', phase_moment), ('amplitude_product', product_mean), ('amplitude_phase_association', association)]:
                        e = float(abs(value-saved[prefix+key]).max()); assert e < 2e-12
                        report['maximum_phase_budget_error'] = max(report['maximum_phase_budget_error'], e)
                report['QMC_cases'] += 1
            if prior:
                old = next(r for r in prior['cases'] if r['label'] == row['label'])
                decode_complex = lambda x: np.asarray(x)[...,0]+1j*np.asarray(x)[...,1]
                values = dict(old_fixed=np.mean([decode_complex(q['fixed']['complex_coherence']) for q in old['QMC']],axis=0),
                              old_absolute=np.mean([decode_complex(q['joint']['complex_coherence']) for q in old['QMC']],axis=0),
                              relative=np.mean(relative_coherences,axis=0),new_fixed=np.mean(fixed_coherences,axis=0))
                for key, value in values.items(): summary_errors[key].extend(abs(value-source_coherence))
                cvs['source'].extend(np.sqrt(np.diag(source_cov))/source_mean)
                cvs['old'].extend(np.mean([q['joint']['CV'] for q in old['QMC']],axis=0))
                cvs['new'].extend(np.mean(generated_cvs,axis=0))
            report['cases'].append(dict(label=row['label'], source_coordinates_quantiles_ranks_AR_and_moments_verified=True))
        if prior:
            summary = producer['stereo_comparison']
            for key, values in summary_errors.items():
                assert abs(np.asarray(summary['per_coordinate_errors'][key])-values).max() < 2e-12
                assert abs(np.mean(values)-summary['mean_absolute_complex_error'][key]) < 2e-12
            for old, field in [('old_fixed','relative_better_than_old_fixed'),('old_absolute','relative_better_than_old_absolute')]:
                assert int(np.sum(np.array(summary_errors['relative'])<summary_errors[old])) == summary[field]
            assert abs(np.linalg.norm(np.array(cvs['new'])-cvs['source'])-producer['CV_error_L2']['relative_phase']) < 2e-12
            assert abs(np.linalg.norm(np.array(cvs['old'])-cvs['source'])-producer['CV_error_L2']['old_radial']) < 2e-12
            report['all_JSON_descriptors_and_aggregate_decision_recomputed'] = True
        report.update(result='independent_relative_phase_audit_passed', producer_sha256=sha(a.study/'report.json'),
                      auditor_sha256=sha(a.out/'executed_audit.py'), phase_budget_not_physical_source_separation=True)
        save(a.out/'report.json', report); print(report['result'])
    except BaseException as exc:
        report.update(result='failed', error=repr(exc)); save(a.out/'report.json', report)
        raise


if __name__ == '__main__':
    main()
