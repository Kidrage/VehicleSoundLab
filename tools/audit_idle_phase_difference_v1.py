"""Independent real products, scalar means, pivoted QR and every direct lag budget."""
import argparse
import math
import shutil
import sys
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
for key in ['workspace', 'input', 'out']:
    p.add_argument('--'+key, type=Path, required=True)
a = p.parse_args(); repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(a.workspace/'tools/python_deps'))
import numpy as np
from scipy import linalg
from research_archive_v1 import load, save, sha


def feature_oracle(z, expanded):
    real, imag = z.real, z.imag
    if expanded:
        pairs = [(0, 1), (0, 2), (1, 2)]
        real = np.column_stack((real, *[z[:, j].real*z[:, i].real+z[:, j].imag*z[:, i].imag for i, j in pairs]))
        imag = np.column_stack((imag, *[z[:, j].imag*z[:, i].real-z[:, j].real*z[:, i].imag for i, j in pairs]))
    f = np.column_stack((real, imag))[12000:-12000]
    return np.array([[math.fsum(f[start:start+48, k])/48 for k in range(f.shape[1])]
                     for start in range(0, len(f), 48)])


def lag_oracle(x, y, scale):
    # Direct raw overlap moments in extended precision, rather than centered arrays.
    x, y = x.astype(np.longdouble), y.astype(np.longdouble)
    pairs = [(i, j) for i in range(4) for j in range(i, 4)]
    result = []
    for lag in range(-40, 41):
        u, v = (x[:len(x)-lag], y[lag:]) if lag >= 0 else (x[-lag:], y[:len(y)+lag])
        mu, mv = u.sum(axis=0)/len(u), v.sum(axis=0)/len(v)
        result.append([(np.sum(u[:, i]*v[:, j])/len(u)-mu[i]*mv[j])/scale[i]/scale[j] for i, j in pairs])
    return np.asarray(result, dtype=float).T


def scalar_assessment(model, f, e):
    coefficient = np.asarray(model['coefficients'])
    target = e/np.asarray(model['reference_power'])
    prediction = coefficient[0]+sum(f[:, k, None]*coefficient[k+1] for k in range(f.shape[1]))
    residual = target-prediction
    mean = lambda x: np.array([math.fsum(column)/len(column) for column in x.T])
    error, before = mean(residual**2), mean((target-coefficient[0])**2)
    corr = []
    for u, v in zip(target.T, prediction.T):
        u, v = u-math.fsum(u)/len(u), v-math.fsum(v)/len(v)
        corr.append(math.fsum(u*v)/math.sqrt(math.fsum(u*u)*math.fsum(v*v)))
    return target, prediction, dict(constant_mse=before, mse=error,
        improvement_over_own_constant=1-error/before, correlation=np.array(corr),
        minimum_prediction=prediction.min(axis=0), mean_target=mean(target),
        mean_prediction=mean(prediction), mean_residual=mean(residual),
        residual_variance=mean((residual-mean(residual))**2))


a.out.mkdir(parents=True, exist_ok=False)
shutil.copy2(__file__, a.out/'executed_auditor.py')
r = dict(result='running', maximum_feature_error=0., maximum_coefficient_error=0.,
         maximum_assessment_error=0., maximum_curve_error=0., curves=0, observations=0)
try:
    observed = load(a.input/'report.json')
    assert observed['result'] == 'all_nested_phase_difference_observations_complete'
    for name, digest in observed['sources'].items():
        assert sha(a.input/'exact_sources'/name) == digest
    tables = {}
    for name, digest in observed['parent_manifests'].items():
        root = a.workspace/'baselines'/name
        assert sha(root/'manifest.json') == digest
        tables[name] = {v['path']: v['sha256'] for v in load(root/'manifest.json')['files']}
    for path, digest in observed['inputs'].items():
        relative = Path(path).relative_to(a.workspace/'baselines')
        assert sha(path) == digest == tables[relative.parts[0]][Path(*relative.parts[1:]).as_posix()]
    parent = a.workspace/'baselines/idle_conditioned_detail_v1/evidence/observe1'
    source_model = load(parent/'report.json')
    assert source_model['frequencies_hz'] == observed['frequencies_hz']
    expected_differences = [source_model['frequencies_hz'][j]-source_model['frequencies_hz'][i]
                            for i, j in [(0, 1), (0, 2), (1, 2)]]
    assert expected_differences == observed['difference_frequencies_hz']
    incrementals = []
    for row in observed['observations']:
        assert sha(a.input/row['file']) == row['sha256']
        with np.load(a.input/row['file']) as archive:
            saved = {key: archive[key] for key in archive.files}
        assert np.array_equal(saved['lags_ms'], np.arange(-40, 41))
        original = {}
        for part in ['train', 'check']:
            suffix = '' if row['seed'] is None else '_phase_'+str(row['seed'])
            with np.load(parent/(part+suffix+'.npz')) as archive:
                original[part] = dict(phasors=archive['phasors'], power=archive['power'], native=archive['feature'])
        mse = {}
        for kind in ['native', 'expanded']:
            features = {part: feature_oracle(original[part]['phasors'], kind == 'expanded') for part in original}
            model = row['models'][kind]
            e = original['train']['power']
            reference = np.array([math.fsum(column)/len(column) for column in e.T])
            assert abs(reference-model['reference_power']).max() < 1e-18
            design = np.column_stack((np.ones(len(e)), features['train']))
            coefficient, _, rank, _ = linalg.lstsq(design, e/reference, lapack_driver='gelsy')
            coefficient_error = float(abs(coefficient-model['coefficients']).max())
            assert coefficient_error < 1e-11
            singular = linalg.svdvals(design)
            assert np.allclose(singular, model['singular_values'], atol=1e-12, rtol=1e-12)
            assert rank == model['rank'] and bool(rank == len(coefficient)) == model['full_rank']
            assert math.isclose(singular[0]/singular[-1], model['condition'], abs_tol=1e-10)
            count = (len(coefficient)-1)//2
            radius = np.array([math.fsum(math.hypot(coefficient[k+1, b], coefficient[k+1+count, b])
                                        for k in range(count)) for b in range(4)])
            lower, upper = coefficient[0]-radius, coefficient[0]+radius
            assert abs(lower-model['lower_bound']).max() < 1e-11
            assert abs(upper-model['upper_bound']).max() < 1e-11
            assert bool(np.all(lower > 0)) == model['positive_sufficient_bound']
            r['maximum_coefficient_error'] = max(r['maximum_coefficient_error'], coefficient_error)
            scale = (original['train']['power']/reference).std(axis=0)
            assert abs(scale-saved[kind+'_scale']).max() < 1e-12
            mse[kind] = {}
            for part in ['train', 'check']:
                prefix = kind+'_'+part+'_'
                feature_error = float(abs(features[part]-saved[prefix+'feature']).max())
                assert feature_error < 1e-12
                r['maximum_feature_error'] = max(r['maximum_feature_error'], feature_error)
                if kind == 'native':
                    assert abs(features[part]-original[part]['native']).max() < 1e-12
                target, prediction, assessed = scalar_assessment(model, features[part], original[part]['power'])
                for key, value in assessed.items():
                    error = float(abs(value-row['assessment'][kind][part][key]).max())
                    assert error < 1e-11, (row['group'], kind, part, key, error)
                    r['maximum_assessment_error'] = max(r['maximum_assessment_error'], error)
                assert abs(target-saved[prefix+'target']).max() < 1e-12
                assert abs(prediction-saved[prefix+'prediction']).max() < 1e-11
                assert abs(assessed['mean_target']-assessed['mean_prediction']-assessed['mean_residual']).max() < 1e-12
                mse[kind][part] = assessed['mse']
                residual = target-prediction
                terms = {}
                for key, x, y in [('TT', target, target), ('PP', prediction, prediction),
                                  ('PR', prediction, residual), ('RP', residual, prediction), ('RR', residual, residual)]:
                    terms[key] = lag_oracle(x, y, scale)
                    error = float(abs(terms[key]-saved[prefix+key]).max())
                    assert error < 1e-11, (row['group'], kind, part, key, error)
                    r['maximum_curve_error'] = max(r['maximum_curve_error'], error)
                    r['curves'] += 10
                closure = float(abs(terms['TT']-terms['PP']-terms['PR']-terms['RP']-terms['RR']).max())
                assert closure < 1e-11
                for key, value in [('prediction_curve_rmse', np.sqrt(np.mean((terms['TT']-terms['PP'])**2, axis=1))),
                                   ('target_curve_rms', np.sqrt(np.mean(terms['TT']**2, axis=1)))]:
                    assert abs(value-row['time_budget'][kind][part][key]).max() < 1e-11
                assert row['time_budget'][kind][part]['maximum_closure_error'] < 1e-11
                r['observations'] += 1
        incremental = 1-mse['expanded']['check']/mse['native']['check']
        assert abs(incremental-row['incremental_check_improvement']).max() < 1e-11
        incrementals.append(incremental)
        print(dict(group=row['group'], curves_verified=r['curves']), flush=True)
    supported = (incrementals[0] > 0) & np.all(incrementals[0] > incrementals[1:], axis=0)
    assert supported.tolist() == observed['supported_bands']
    real = observed['observations'][0]['models']['expanded']
    assert bool(supported.sum() >= 3 and real['full_rank'] and real['positive_sufficient_bound']) == observed['future_synthesis_prerequisite']
    # Inspect the original interrupted attempt and exact summation-only correction.
    failure = load(a.input.parent/'observe1/report.json')
    assert failure['result'] == 'failed' and failure['error'] == 'AssertionError()'
    for name, digest in failure['sources'].items():
        assert sha(a.input.parent/'observe1/exact_sources'/name) == digest
    changed = [name for name in observed['sources'] if failure['sources'][name] != observed['sources'][name]]
    assert changed == ['tools/idle_phase_difference_v1/features.py']
    for name, count in [('C_files_sha256.json', 612), ('voice_files_sha256.json', 67)]:
        values = load(a.workspace/'baselines/idle_microtexture_c_v1/inputs'/name)
        assert len(values) == count
        for path, digest in values.items():
            assert sha(repo/path) == digest, path
    r.update(result='all_nested_features_models_and_800_direct_lag_curves_verified',
             input_report_sha256=sha(a.input/'report.json'), failed_attempt_preserved=True,
             original_native_model_reproduced=True, check_used_for_fit=False,
             audio_or_runtime_profile_exported=False, runtime_changed=False,
             unchanged_C_H=612, unchanged_old_voices=67)
except Exception as exc:
    r.update(result='failed', error=repr(exc))
    raise
finally:
    save(a.out/'report.json', r)
print(r, flush=True)
