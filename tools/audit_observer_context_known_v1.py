"""Independent dense audit of every genuine-context known case, including ends."""
import argparse, os, shutil, sys
from pathlib import Path
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'study', 'original', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace / 'tools/python_deps'))
    import numpy as np
    from scipy import linalg
    from observer_supported_v1.audit_oracle import metric, matrices, block_right
    from observer_frequency_v1.reduced_oracle import carrier_table
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, a.out / 'executed_audit.py')
    helpers = ('tools/observer_supported_v1/audit_oracle.py',
               'tools/observer_frequency_v1/reduced_oracle.py',
               'tools/observer_complete_v1/audit_oracle.py')
    for j, name in enumerate(helpers):
        shutil.copy2(repo / name, a.out / f'executed_oracle_{j}.py')
    r = dict(result='running', cases=[], maximum_errors={}, material_read=False)

    def check(name, x, y, scale=1., gate=2e-9):
        x, y = np.asarray(x), np.asarray(y)
        assert x.shape == y.shape, name
        err = float(np.max(abs(x - y)) / scale)
        assert err < gate, (name, err)
        r['maximum_errors'][name] = max(err, r['maximum_errors'].get(name, 0.))

    def vec(z):
        return np.r_[z.real.ravel(), z.imag.ravel()]

    try:
        source, original = load(a.study / 'report.json'), load(a.original / 'report.json')
        assert source['result'] == 'observer_context_known_measured'
        assert original['result'] == 'observer_supported_known_measured'
        assert not original['all_fidelity_qualified']
        for name, digest in source['sources'].items():
            assert sha(repo / name) == sha(a.study / 'exact_sources' / name) == digest
        for name, digest in source['inputs'].items():
            assert sha(name) == digest
        assert len(source['cases']) == len(original['cases']) == 8
        for case, old in zip(source['cases'], original['cases']):
            assert case['label'] == old['label']
            path = a.study / case['file']
            assert sha(path) == case['sha256']
            with np.load(path) as z, np.load(a.original / old['file']) as zz:
                assert sha(a.original / old['file']) == old['sha256']
                assert np.array_equal(z['target_audio'], zz['audio'])
                assert np.array_equal(z['target_source_nodes'], zz['source_nodes'])
                assert np.array_equal(z['no_context_nodes'], zz['supported_nodes'])
                assert np.array_equal(z['orders'], [7, 211])
                assert np.array_equal(z['scale'], [[1.], [case['weak_amplitude']]])
                assert case['offset'] == 2176 and case['node_step'] == 544
                assert case['padding_nodes'] == 4 and case['frames'] == 8705
                assert case['target_frames'] == 4353
                assert np.array_equal(z['positions'], np.arange(17) * 544)
                indices = np.arange(-4, 13)
                truth = np.ones((17, 2, 1), complex)
                truth[:, 0, 0] = 1. + .15j
                truth[:, 1, 0] = (1. + .3j if case['law'] == 'constant' else
                    1. + .8 * (-1.)**indices + .3j * np.sin(.9 * indices))
                rotation = carrier_table((7, 211))[(-2176) % 1024]
                truth *= z['scale'][None] * rotation[None, :, None]
                check('declared_extended_truth', truth, z['source_nodes'])
                check('phase_rotation', rotation, z['rotation'])
                m = metric(z['audio'], 64.)
                A, b, Phi, R, data_rows = matrices(z['positions'], z['orders'], z['scale'], z['audio'], m)
                qtruth = vec(truth / z['scale'][None])
                check('whole_genuine_observations', Phi @ qtruth, z['audio'].ravel())
                crop = slice(2176, 6529)
                check('original_target_observations', (Phi @ qtruth)[crop], zz['audio'].ravel())
                check('target_nine_nodes', truth[4:13] / rotation[None, :, None], zz['source_nodes'])
                check('weights', m['weights'], z['weights'], max(m['weights']))
                check('powers', m['band_power'], z['band_power'])
                assert np.array_equal(m['floor_active'], z['floor_active'])
                dense = linalg.lstsq(A, b, lapack_driver='gelsd')[0]
                check('normal_matrix', A.T @ A, z['normal_matrix'], max(1., abs(z['normal_matrix']).max()))
                check('normal_rhs', A.T @ b, z['normal_rhs'], max(1., abs(z['normal_rhs']).max()))
                size = 17 * 2
                high_ids = np.r_[np.arange(17) * 2 + 1, size + np.arange(17) * 2 + 1]
                high = Phi[:, high_ids] @ qtruth[high_ids]
                blocks = block_right(z['positions'], z['orders'], z['scale'], m)
                P = np.zeros((2 * size, 2 * size))
                for h in range(2):
                    ids = np.r_[np.arange(17) * 2 + h, size + np.arange(17) * 2 + h]
                    P[np.ix_(ids, ids)] = blocks[h]
                check('right_blocks', blocks, z['right_matrix'], max(1., abs(blocks).max()))
                check('right_map', P, z['right'], max(1., abs(P).max()))
                condition = float(np.linalg.cond(A @ P))
                check('condition', condition, case['preconditioned_dense_condition'], condition, 2e-7)
                row = dict(label=case['label'], condition=condition, variants={})
                for tag in ('dense', 'iterative'):
                    x = vec(z[tag + '_nodes'] / z['scale'][None])
                    err = float(np.linalg.norm(x - dense) / np.linalg.norm(dense))
                    assert err < 2e-7
                    diff = Phi @ x - z['audio'].ravel()
                    hd = Phi[:, high_ids] @ (x - qtruth)[high_ids]
                    stats = dict(whole_wave_NRMSE=float(np.linalg.norm(diff) / np.linalg.norm(z['audio'])),
                        whole_high_NRMSE=float(np.linalg.norm(hd) / np.linalg.norm(high)),
                        target_wave_NRMSE=float(np.linalg.norm(diff[crop]) / np.linalg.norm(z['target_audio'])),
                        target_high_NRMSE=float(np.linalg.norm(hd[crop]) / np.linalg.norm(high[crop])),
                        whole_high_region_NRMSE=[float(np.linalg.norm(hd[s]) / np.linalg.norm(high[s]))
                            for s in (slice(0, 544), slice(544, -544), slice(-544, None))])
                    for k, value in stats.items():
                        check(tag + '_' + k, value, case[tag + '_metrics'][k])
                    residual = A @ x - b
                    gradient = float(np.linalg.norm(A.T @ residual) / np.linalg.norm(A.T @ b))
                    assert gradient < 2e-7
                    B, y = A[:data_rows], b[:data_rows]
                    e = B @ x - y
                    v = linalg.solve(R, B.T @ e, assume_a='pos')
                    cert = case[tag + '_certificate']
                    t = cert['residual_dual_scale']
                    primal = float(residual @ residual)
                    dual = float(-t*t*(e@e + (B.T@e)@v) - 2*t*(y@e))
                    gap = float((1-t)**2*(e@e) + (x+t*v)@R@(x+t*v))
                    assert abs(primal - dual - gap) < 2e-8 * max(1., primal)
                    for k, value in dict(primal=primal, dual_lower_bound=dual, gap_upper_bound=gap).items():
                        check('certificate_' + k, value, cert[k], max(1., abs(value)), 2e-8)
                    assert (gap <= 1e-6*primal + 1e-10) == cert['additional_gap_gate_passed']
                    assert cert['additional_gap_gate_passed']
                    row['variants'][tag] = dict(metrics=stats, gradient=gradient, gap=gap)
                    if tag == 'iterative':
                        info = case['iterative_solve']
                        check('iterative_dense_error', err, case['iterative_dense_relative_error'])
                        check('iterative_gradient', gradient, info['relative_stationarity'])
                        assert info['stop'] in (1, 2, 4, 5) and info['converged']
                row['target_fidelity_qualified'] = row['variants']['dense']['metrics']['target_high_NRMSE'] < .02
                row['solver_qualified'] = condition < 1e6
                assert row['target_fidelity_qualified'] == case['target_fidelity_qualified']
                assert row['solver_qualified'] == case['solver_qualified']
                check('old_failure_preserved', case['no_context_target_high_NRMSE'], old['variants']['supported']['high_component_NRMSE'])
                assert case['full_context_not_reclassified_as_pass']
                r['cases'].append(row)
                print('AUDITED CONTEXT', case['label'], row['target_fidelity_qualified'], flush=True)
        weakest = r['cases'][-1]['variants']['dense']['metrics']
        assert weakest['whole_high_NRMSE'] > .02
        assert original['cases'][-1]['variants']['supported']['high_component_NRMSE'] > .02
        r.update(result='independent_observer_context_known_passed',
            all_target_fidelity_qualified=all(c['target_fidelity_qualified'] for c in r['cases']),
            all_solver_qualified=all(c['solver_qualified'] for c in r['cases']),
            original_failure_and_outer_end_loss_retained=True,
            producer_sha256=sha(a.study / 'report.json'), auditor_sha256=sha(__file__),
            oracles_sha256={n: sha(repo / n) for n in helpers})
        save(a.out / 'report.json', r)
        print(r['result'], flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error))
        save(a.out / 'report.json', r)
        raise


if __name__ == '__main__':
    main()
