"""Independent sample power, scalar exponential KKT and complete direct lag checks."""
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
from scipy import signal, linalg
from research_archive_v1 import load, save, sha


def features(z, expanded):
    real, imag = z.real, z.imag
    if expanded:
        real = np.column_stack((real, z[:, 1].real*z[:, 0].real+z[:, 1].imag*z[:, 0].imag,
                                z[:, 2].real*z[:, 0].real+z[:, 2].imag*z[:, 0].imag,
                                z[:, 2].real*z[:, 1].real+z[:, 2].imag*z[:, 1].imag))
        imag = np.column_stack((imag, z[:, 1].imag*z[:, 0].real-z[:, 1].real*z[:, 0].imag,
                                z[:, 2].imag*z[:, 0].real-z[:, 2].real*z[:, 0].imag,
                                z[:, 2].imag*z[:, 1].real-z[:, 2].real*z[:, 1].imag))
    return np.column_stack((np.ones(len(z)), real, imag))[12000:-12000]


def block_mean(x):
    return np.array([[math.fsum(x[start:start+48, j])/48 for j in range(4)]
                     for start in range(0, len(x), 48)])


def lag_covariance(x, y, scale):
    x, y = x.astype(np.longdouble), y.astype(np.longdouble)
    pairs = [(i, j) for i in range(4) for j in range(i, 4)]
    values = []
    for lag in range(-40, 41):
        u, v = (x[:len(x)-lag], y[lag:]) if lag >= 0 else (x[-lag:], y[:len(y)+lag])
        mu, mv = u.sum(axis=0)/len(u), v.sum(axis=0)/len(v)
        values.append([(np.sum(u[:, i]*v[:, j])/len(u)-mu[i]*mv[j])/scale[i]/scale[j] for i, j in pairs])
    return np.asarray(values, dtype=float).T


def scores(target, prediction):
    mean = lambda x: np.array([math.fsum(v)/len(v) for v in x.T])
    mse, before = mean((target-prediction)**2), mean((target-1)**2)
    correlation = []
    for u, v in zip(target.T, prediction.T):
        u, v = u-math.fsum(u)/len(u), v-math.fsum(v)/len(v)
        correlation.append(math.fsum(u*v)/math.sqrt(math.fsum(u*u)*math.fsum(v*v)))
    return dict(mse=mse, constant_mse=before, improvement_over_train_constant=1-mse/before,
                correlation=np.array(correlation), mean_target=mean(target), mean_prediction=mean(prediction),
                mean_residual=mean(target-prediction), minimum_prediction=prediction.min(axis=0))


a.out.mkdir(parents=True, exist_ok=False); shutil.copy2(__file__, a.out/'executed_auditor.py')
r = dict(result='running', maximum_filter_error_FS=0., maximum_filter_relative_RMS_error=0.,
         maximum_reference_relative_error=0.,
         maximum_prediction_error=0., maximum_gradient_error=0., maximum_hessian_error=0.,
         maximum_KKT_gradient=0., maximum_curve_error=0., models=0, band_fits=0, curves=0,
         minimum_hessian_eigenvalue=1e30)
try:
    observed = load(a.input/'report.json')
    assert observed['result'] == 'all_positive_sample_power_models_observed'
    for name, digest in observed['sources'].items():
        assert sha(a.input/'exact_sources'/name) == digest
    tables = {}
    for name, digest in observed['parent_manifests'].items():
        root = a.workspace/'baselines'/name; assert sha(root/'manifest.json') == digest
        tables[name] = {v['path']: v['sha256'] for v in load(root/'manifest.json')['files']}
    for path, digest in observed['inputs'].items():
        relative = Path(path).relative_to(a.workspace/'baselines')
        assert sha(path) == digest == tables[relative.parts[0]][Path(*relative.parts[1:]).as_posix()]
    root = a.workspace/'baselines/idle_conditioned_detail_v1/evidence/observe1'
    old = load(a.workspace/'baselines/idle_phase_difference_v1/evidence/observe2/report.json')
    originals = {}
    for part in ['train', 'check']:
        with np.load(root/(part+'.npz')) as archive: originals[part] = archive['audio']
    increments, old_increments = [], []
    for row, previous in zip(observed['observations'], old['observations']):
        assert row['group'] == previous['group'] and row['seed'] == previous['seed']
        assert sha(a.input/row['file']) == row['sha256']
        with np.load(a.input/row['file']) as archive: saved = {key: archive[key] for key in archive.files}
        assert np.array_equal(saved['lags_ms'], np.arange(-40, 41))
        data = {}
        for part in ['train', 'check']:
            audio = originals[part]
            if row['seed'] is not None:
                spectrum = np.fft.rfft(audio, axis=0)
                angle = np.random.default_rng(row['seed']).uniform(-np.pi, np.pi, len(spectrum)); angle[0] = angle[-1] = 0
                audio = np.fft.irfft(spectrum*(np.cos(angle)+1j*np.sin(angle))[:, None], n=len(audio), axis=0)
            suffix = '' if row['seed'] is None else '_phase_'+str(row['seed'])
            with np.load(root/(part+suffix+'.npz')) as archive:
                z, original_power = archive['phasors'], archive['power']
            independent = []
            for index, band in enumerate(observed['bands_hz']):
                sos = signal.butter(4, band, btype='bandpass', fs=48000, output='sos')
                assert np.array_equal(sos, saved['sos'][index])
                b, c = signal.sos2tf(sos)
                filtered = signal.lfilter(b, c, audio[:, 0])[12000:-12000]
                exact = saved[part+'_filtered'][:, index]
                error = float(abs(filtered-exact).max())
                relative = float(np.linalg.norm(filtered-exact)/np.linalg.norm(exact))
                assert error < 1e-8 and relative < 1e-5, (band, error, relative)
                r['maximum_filter_error_FS'] = max(r['maximum_filter_error_FS'], error)
                r['maximum_filter_relative_RMS_error'] = max(r['maximum_filter_relative_RMS_error'], relative)
                independent.append(filtered)
            power = saved[part+'_filtered']**2
            averaged = block_mean(power)
            assert abs(averaged-original_power).max() < 1e-18
            assert abs(averaged-saved[part+'_power']).max() < 1e-18
            data[part] = dict(power=power, averaged=averaged,
                              native=features(z, False), expanded=features(z, True))
        reference = np.array([math.fsum(v)/len(v) for v in data['train']['power'].T])
        errors = {}
        for kind in ['native', 'expanded']:
            model = row['models'][kind]; coefficient = np.asarray(model['coefficients'])
            # The producer sums 120000 nonnegative samples. Compare its floating
            # sum with fsum using the standard gamma_n forward-error bound.
            reference_error = float((abs(reference-model['reference_power'])/reference).max())
            terms = len(data['train']['power'])+2
            gamma_n = terms*np.finfo(float).eps/(1-terms*np.finfo(float).eps)
            assert reference_error <= gamma_n
            r['maximum_reference_relative_error'] = max(r['maximum_reference_relative_error'], reference_error)
            x = data['train'][kind]
            singular = linalg.svdvals(x); rank = np.linalg.matrix_rank(x)
            assert np.allclose(singular, model['singular_values'], rtol=1e-12, atol=1e-10)
            assert rank == model['rank'] and bool(rank == x.shape[1]) == model['full_rank']
            assert math.isclose(singular[0]/singular[-1], model['condition'], abs_tol=1e-10)
            count = (len(coefficient)-1)//2
            radius = np.array([math.fsum(math.hypot(coefficient[k+1, band], coefficient[k+1+count, band])
                                        for k in range(count)) for band in range(4)])
            low, high = coefficient[0]-radius, coefficient[0]+radius
            bound = model['bounds']
            for key, expected in [('exponent_lower', low), ('exponent_upper', high),
                                  ('power_lower', np.array([math.exp(v) for v in low])),
                                  ('power_upper', np.array([math.exp(v) for v in high]))]:
                assert abs(expected-bound[key]).max() < 1e-11
            assert bound['finite_normal_bounds'] == bool(np.all(low > math.log(np.finfo(float).tiny)) and
                                                       np.all(high < math.log(np.finfo(float).max)))
            scale = (data['train']['averaged']/reference).std(axis=0)
            assert abs(scale-saved[kind+'_scale']).max() < 1e-12
            errors[kind] = {}
            for part in ['train', 'check']:
                x = data[part][kind]
                # Scalar exp applied to every full-resolution model value.
                eta = np.column_stack([sum(x[:, k]*coefficient[k, band] for k in range(len(coefficient))) for band in range(4)])
                q = np.fromiter((math.exp(v) for v in eta.ravel()), dtype=float, count=eta.size).reshape(eta.shape)
                target = data[part]['averaged']/reference
                prediction = block_mean(q)
                prefix = kind+'_'+part+'_'
                pred_error = float(abs(prediction-saved[prefix+'prediction']).max())
                assert pred_error < 1e-11
                r['maximum_prediction_error'] = max(r['maximum_prediction_error'], pred_error)
                assert abs(target-saved[prefix+'target']).max() < 1e-11
                assert np.all(q.min(axis=0) >= bound['power_lower']) and np.all(q.max(axis=0) <= bound['power_upper'])
                result = scores(target, prediction)
                for key, value in result.items():
                    assert abs(value-row['assessment'][kind][part][key]).max() < 1e-10
                for key, value in [('sample_minimum_prediction', q.min(axis=0)), ('sample_maximum_prediction', q.max(axis=0))]:
                    assert abs(value-row['assessment'][kind][part][key]).max() < 1e-11
                errors[kind][part] = result['mse']
                if part == 'train':
                    t = data['train']['power']/reference
                    for band in range(4):
                        difference = q[:, band]-t[:, band]
                        gradient = np.array([math.fsum(x[:, k]*difference)/len(x) for k in range(x.shape[1])])
                        hessian = np.array([[np.sum(x[:, j].astype(np.longdouble)*x[:, k]*q[:, band])/len(x)
                                             for k in range(x.shape[1])] for j in range(x.shape[1])], dtype=float)
                        ge = float(abs(gradient-model['final_gradients'][band]).max())
                        he = float(abs(hessian-model['final_hessians'][band]).max())
                        assert ge < 1e-11 and he < 1e-10
                        assert abs(gradient).max() <= 1e-9
                        eigenvalues = linalg.eigvalsh(hessian)
                        assert np.allclose(eigenvalues, model['fits'][band]['hessian_eigenvalues'], atol=1e-10, rtol=1e-10)
                        assert eigenvalues[0] > 0
                        r['minimum_hessian_eigenvalue'] = min(r['minimum_hessian_eigenvalue'], float(eigenvalues[0]))
                        r['maximum_gradient_error'] = max(r['maximum_gradient_error'], ge)
                        r['maximum_hessian_error'] = max(r['maximum_hessian_error'], he)
                        r['maximum_KKT_gradient'] = max(r['maximum_KKT_gradient'], float(abs(gradient).max()))
                        loss = math.fsum(np.expm1(eta[:, band])-t[:, band]*eta[:, band])/len(x)
                        assert abs(loss-model['fits'][band]['loss']) < 1e-11
                        assert model['fits'][band]['status'] == 'converged'
                        trace = model['traces'][band]
                        assert trace[-1]['step'] == 0 and trace[-1]['gradient_infinity'] <= 1e-9
                        for left, right in zip(trace[:-1], trace[1:]):
                            assert 0 < left['step'] <= 1 and 0 <= left['backtracks'] < 30
                            assert math.isclose(left['step'], .5**left['backtracks'], abs_tol=1e-16)
                            assert right['loss'] <= left['loss']+1e-4*left['step']*left['directional_derivative']+1e-14
                        r['band_fits'] += 1
                residual = target-prediction
                terms = {}
                for term, u, v in [('TT', target, target), ('PP', prediction, prediction),
                                   ('PR', prediction, residual), ('RP', residual, prediction), ('RR', residual, residual)]:
                    terms[term] = lag_covariance(u, v, scale)
                    error = float(abs(terms[term]-saved[prefix+term]).max())
                    assert error < 1e-10
                    r['maximum_curve_error'] = max(r['maximum_curve_error'], error); r['curves'] += 10
                assert abs(terms['TT']-terms['PP']-terms['PR']-terms['RP']-terms['RR']).max() < 1e-10
                stats = row['time_budget'][kind][part]
                assert stats['maximum_closure_error'] < 1e-10
                assert abs(np.sqrt(np.mean((terms['TT']-terms['PP'])**2, axis=1))-stats['prediction_curve_rmse']).max() < 1e-10
                assert abs(np.sqrt(np.mean(terms['TT']**2, axis=1))-stats['target_curve_rms']).max() < 1e-10
            assert model['converged']
            r['models'] += 1
        increment = 1-errors['expanded']['check']/errors['native']['check']
        old_increment = 1-errors['expanded']['check']/np.asarray(previous['assessment']['native']['check']['mse'])
        assert abs(increment-row['incremental_check_improvement']).max() < 1e-10
        assert abs(old_increment-row['check_improvement_over_old_native_OLS']).max() < 1e-10
        assert row['old_native_OLS_check_mse'] == previous['assessment']['native']['check']['mse']
        assert row['old_expanded_OLS_check_mse'] == previous['assessment']['expanded']['check']['mse']
        increments.append(increment); old_increments.append(old_increment)
        print(dict(group=row['group'], models=r['models'], band_fits=r['band_fits'], curves=r['curves']), flush=True)
    supported = (increments[0] > 0) & (old_increments[0] > 0) & np.all(increments[0] > increments[1:], axis=0)
    assert supported.tolist() == observed['supported_bands']
    eligible = all(m['converged'] and m['full_rank'] and m['bounds']['finite_normal_bounds'] for m in observed['observations'][0]['models'].values())
    assert bool(eligible and supported.sum() >= 3) == observed['future_synthesis_prerequisite']
    for name, count in [('C_files_sha256.json', 612), ('voice_files_sha256.json', 67)]:
        values = load(a.workspace/'baselines/idle_microtexture_c_v1/inputs'/name); assert len(values) == count
        for path, digest in values.items(): assert sha(repo/path) == digest, path
    assert r['models'] == 8 and r['band_fits'] == 32 and r['curves'] == 800
    r.update(result='all8_positive_models32_KKT_fits_and800_lag_curves_verified',
             input_report_sha256=sha(a.input/'report.json'), full_resolution_exp_before_average=True,
             unchanged_C_H=612, unchanged_old_voices=67, runtime_changed=False,
             waveform_budget_proven=False, audio_or_runtime_profile_exported=False)
except Exception as exc:
    r.update(result='failed', error=repr(exc)); raise
finally:
    save(a.out/'report.json', r)
print(r, flush=True)
