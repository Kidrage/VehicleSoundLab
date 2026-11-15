"""Independent weak-tail audit, without new interpolation/known/meter imports."""
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
    from locked_source_diagnostics_v1.native_identity import verify
    from locked_source_tail_v1.audit_kernel import sinc_sum, analytic
    from locked_source_tail_v1.audit_measure import verify as verify_meter, observe
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', inputs={}, interpolation={}, analytic={})
    try:
        info = load(a.study/'report.json')
        mode = info['mode']
        assert info['result'] == 'locked_source_tail_'+mode+'_measured'
        for name, expected in info['sources'].items():
            assert sha(repo/name) == sha(a.study/'exact_sources'/name) == expected
        for name, expected in info['inputs'].items():
            assert sha(name) == expected
        shutil.copytree(a.study/'exact_sources', a.out/'exact_sources')
        r.update(producer_sha256=sha(a.study/'report.json'), capture_sha256=sha(a.study/'capture.npz'),
                 study=str(a.study), mode=mode)
        assert r['capture_sha256'] == info['capture_sha256']
        source_study = Path(info['source_study'])
        source = load(source_study/'report.json')
        source_audit = load(Path(info['source_audit'])/'report.json')
        assert source_audit['verification_passed']
        assert source_audit['producer_sha256'] == sha(source_study/'report.json')
        z, _ = verify(source, source_study, repo, r['inputs'])
        query_file = Path(info['query_file'])
        r['query_file_sha256'] = sha(query_file)
        with np.load(query_file) as f:
            q = {key: f[key] for key in f.files}
        with np.load(a.study/'capture.npz') as f:
            saved = {key: f[key] for key in f.files}
        for key in ('query', 'coordinates', 'crop', 'taps'):
            assert np.array_equal(saved[key], q['source_coordinates' if key == 'coordinates' else key])
        for key in ('weights', 'amplitude', 'source_start'):
            assert np.array_equal(saved[key], z[key])
        values = {key[8:]: value for key, value in saved.items() if key.startswith('signal__')}
        if mode == 'known':
            frequencies = np.array([0., 100., 1000., 5000., 9000., 13000., 13950., 14000.])
            coefficients = np.array([[.02, -.01], [.13, .09], [.03, -.05j], [.02j, .04],
                [.01, .015j], [.008j, -.004], [.004, .006j], [.003j, .002]], complex)
            assert np.array_equal(saved['frequencies'], frequencies)
            assert np.array_equal(saved['coefficients'], coefficients)
            l1 = float(np.sum(abs(coefficients)))
            grid = np.arange(len(z['native']), dtype=np.longdouble)/48000
            samples = analytic(grid, frequencies, coefficients)
            original = samples[int(q['crop'][0]):int(q['crop'][1])]
            filtered = np.column_stack([np.convolve(original[:, c], q['taps'], mode='same') for c in (0, 1)])
            r['analytic']['native_max_FS'] = float(np.max(abs(samples-saved['native'])))
            r['analytic']['FIR_max_FS'] = float(np.max(abs(filtered-saved['filtered'])))
            registered = np.asarray(q['source_coordinates'], np.longdouble)-np.longdouble(z['source_start'])
            qt = (np.longdouble(q['crop'][0])+np.asarray(q['query'], np.longdouble))/48000
            affine = registered[0]+(registered[-1]-registered[0])*np.arange(len(registered), dtype=np.longdouble)/(len(registered)-1)
            for name, t in (('exact_registered', registered), ('exact_query', qt), ('exact_affine', affine)):
                error = float(np.max(abs(analytic(t, frequencies, coefficients, q['taps'])-values[name]))/l1)
                assert error < 2e-12, (name, error)
                r['analytic'][name] = error
            ideal_time = np.arange(int(q['crop'][0]), int(q['crop'][1]), dtype=np.longdouble)/48000
            assert np.max(abs(analytic(ideal_time, frequencies, coefficients, q['taps'])-saved['ideal_filtered']))/l1 < 2e-12
            assert max(r['analytic']['native_max_FS'], r['analytic']['FIR_max_FS'])/l1 < 2e-12
            assert info['qualification']['source_L1'] == l1
            for name in ('nominal128', 'reference512', 'reference1024', 'reference2048'):
                error = float(np.max(abs(values[name]-values['exact_registered']))/l1)
                gate = 2e-6 if name == 'nominal128' else 2e-10
                assert error < gate
                expected = info['qualification']['nominal_error'] if name == 'nominal128' else info['qualification']['reference_errors'][name]
                assert error == expected
            assert info['qualification']['invalid_rejections'] == ['left_support', 'right_support', 'nonfinite', 'complex', 'radius']
            probe = sinc_sum(saved['probe_source'], saved['probe_query'], 2048)
            assert np.max(abs(probe-saved['probe_output']))/l1 < 2e-12
            assert np.array_equal(probe[:, 0], probe[:, 1]) and not np.count_nonzero(probe[:, 2:4])
        else:
            assert np.array_equal(saved['filtered'], q['filtered'])
            for key, value in (('legacy', q['legacy']), ('nominal64', q['sinc64']), ('nominal128', q['sinc128']),
                               ('nominal256', q['sinc256']), ('saved_fit', z['wave'])):
                assert np.array_equal(values[key], value)
            ka = load(Path(info['known_audit'])/'report.json')
            known = load(Path(info['known_study'])/'report.json')
            assert ka['verification_passed'] and ka['result'] == 'independent_locked_source_tail_known_verified'
            assert ka['producer_sha256'] == sha(Path(info['known_study'])/'report.json')
            assert ka['query_file_sha256'] == sha(query_file)
            assert known['qualification']['all_qualified']
            assert not info['source_fidelity_qualified'] and not info['eligible_for_later_source_statistics']
            rows, _ = observe((z['wave']-z['audio'])[2048:-2048], z['weights'], float(z['amplitude']))
            ref, _ = observe(z['target'], z['weights'], float(z['amplitude']))
            from locked_source_tail_v1.audit_measure import masks
            errors = [float(np.linalg.norm(rows[:, mask])/np.linalg.norm(ref[:, mask])) for mask in masks()[:6]]
            assert np.max(abs(np.asarray(errors)-info['original_metrics']['target_supported_band_complex_NRMSE'])) < 2e-12
            assert errors[-1] > .02
            r.update(original_virtual_target_band_NRMSE=errors, original_source_fidelity_qualified=False,
                     eligible_for_later_source_statistics=False)
        scale = max(float(np.max(abs(saved['filtered']))), np.finfo(float).tiny)
        for radius in (512, 1024, 2048):
            expected = sinc_sum(saved['filtered'], saved['query'], radius)
            error = float(np.max(abs(expected-values['reference'+str(radius)]))/scale)
            assert error < 2e-12, (radius, error)
            r['interpolation'][str(radius)] = dict(all_query_all_channel_max_FS=float(np.max(abs(expected-values['reference'+str(radius)]))),
                relative_source_peak=error, samples=int(expected.size))
            print('INDEPENDENT_REFERENCE_VERIFIED', mode, radius, error, flush=True)
        r['observation_audit'] = verify_meter(values, saved, info['observations'], z['weights'], float(z['amplitude']))
        r.update(result='independent_locked_source_tail_'+mode+'_verified', verification_passed=True,
            full_query_context_and_original_clock_verified=True,
            numerical_reference_not_certified_infinite_interpolator=True,
            all_new_producer_algorithm_modules_not_imported=True,
            no_source_admission_or_sustained_C_hearing_promotion=True)
        save(a.out/'report.json', r)
        print('INDEPENDENT_TAIL_COMPLETE', mode, flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error)); save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
