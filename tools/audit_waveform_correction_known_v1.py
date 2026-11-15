"""Independent original equations and full two-step correction trajectories.

Small known fixtures only. Uses the independent full-frame/carrier oracle,
scalar Householder maps and dense audit matrices, never the producer restore,
correction or inverse modules. Full Q here is audit-only and size bounded.
"""
import argparse
import os
import shutil
import sys
from pathlib import Path
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'study', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace / 'tools/python_deps'))
    import numpy as np
    from scipy import linalg
    from observer_supported_v1.audit_oracle import matrices, metric
    from observer_complete_v1.audit_oracle import full_frame
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, a.out / 'executed_audit.py')
    helpers = ('tools/observer_supported_v1/audit_oracle.py',
               'tools/observer_complete_v1/audit_oracle.py',
               'tools/observer_frequency_v1/reduced_oracle.py')
    for j, name in enumerate(helpers):
        shutil.copy2(repo / name, a.out / ('executed_oracle_%d.py' % j))
    r = dict(result='running', cases=[], maximum_errors={}, inputs={})

    def check(name, x, y, scale=None, gate=2e-12):
        x, y = np.asarray(x), np.asarray(y)
        assert x.shape == y.shape, (name, x.shape, y.shape)
        denominator = max(1., float(np.max(abs(y)))) if scale is None else max(float(scale), 1e-300)
        error = float(np.max(abs(x-y)) / denominator)
        r['maximum_errors'][name] = max(error, r['maximum_errors'].get(name, 0.))
        assert error < gate, (name, error, gate)

    def qmap(raw, tau, value, transpose=False):
        result = np.array(value, copy=True)
        for j in (range(len(tau)) if transpose else range(len(tau)-1, -1, -1)):
            v = np.r_[1., raw[j+1:, j]]
            result[j:] -= v[:, None] * (tau[j] * (v @ result[j:]))[None]
        return result

    def read(path):
        r['inputs'][str(path)] = sha(path)
        return load(path)

    try:
        source = read(a.study / 'report.json')
        assert source['result'] == 'waveform_original_operator_correction_known_measured'
        shared = source['kind'] == 'shared8'
        expected = 8 if shared else 12
        assert source['fixed_correction_steps'] == 2 and len(source['cases']) == expected
        for name, digest in source['sources'].items():
            assert sha(a.study / 'exact_sources' / name) == digest
        for name, digest in source['inputs'].items():
            assert sha(name) == digest
        for case in source['cases']:
            path = a.study / case['file']
            assert sha(path) == case['sha256']
            r['inputs'][str(path)] = sha(path)
            base_path = Path(case['base_file'])
            base_report = read(base_path.parent / 'report.json')
            parent = next(c for c in base_report['cases']
                          if c['label'] == case['label'] and c['kind'] == case['kind'])
            assert sha(base_path) == parent['sha256'] == source['inputs'][str(base_path)]
            with np.load(base_path) as f:
                base = {name: f[name] for name in f.files}
            with np.load(path) as f:
                z = {name: f[name] for name in f.files}
            audio = z['audio']; C = audio.shape[1]
            for name in ('audio', 'positions', 'orders', 'scale', 'original'):
                assert np.array_equal(z[name], base[name]), name
            if case['kind'] == 'algebra':
                original_file = Path(parent['original_file'])
                r['inputs'][str(original_file)] = sha(original_file)
                with np.load(original_file) as old:
                    A, b, Phi, R, W = (old[n] for n in ('A', 'b', 'Phi', 'R', 'H'))
                count = len(Phi); rootwave = np.linalg.cholesky(W).T
                data_map = lambda wave: rootwave @ np.asarray(wave).ravel()
            else:
                profile = metric(audio, 64.)
                A, b, Phi, R, count = matrices(z['positions'], z['orders'], z['scale'], audio, profile)

                def data_map(wave):
                    wave = np.asarray(wave).reshape(audio.shape)
                    rows, _ = full_frame(wave)
                    rows = rows[profile['keep']] * profile['amplitude'] * profile['weights'][None, :, None]
                    return np.r_[wave.ravel()/profile['sigma'], rows.real.ravel(), rows.imag.ravel()]

            if len(R) > 512:
                raise ValueError('Independent dense known audit must not become a full/source runner')
            B, target = A[:count], b[:count]
            check('independent_original_target', data_map(audio), target, gate=2e-8)
            if shared:
                check('independent_original_A', A, base['original_A'], gate=2e-8)
                check('independent_original_rhs', b, base['original_rhs'], gate=2e-8)
            reference = linalg.lstsq(A, b, lapack_driver='gelsd')[0]
            check('preserved_dense_reference', base['original'], reference,
                  scale=max(np.linalg.norm(reference), 1e-300), gate=2e-7)
            L = np.linalg.cholesky(R)
            inv = linalg.solve_triangular(L.T, np.eye(len(R)))
            Gdata = B @ inv
            G = np.vstack((Gdata, np.eye(len(R))))
            rhs = np.r_[target, np.zeros(len(R))]
            normG = float(np.linalg.norm(G))
            check('complete_original_Frobenius', normG, case['original_root_Frobenius'])
            n, channels = (len(R)//C, C) if shared else (len(R), 1)
            assert base['x_raw'].shape[1] == n
            ids = [np.arange(c, len(R), channels) for c in range(channels)]
            Ln = L[np.ix_(ids[0], ids[0])]
            if shared:
                for c in range(C):
                    check('same_LR_node_penalty', L[np.ix_(ids[c], ids[c])], Ln)
                    check('same_LR_synthesis', Phi[c::C, ids[c]], Phi[::C, ids[0]])
                    assert np.count_nonzero(Phi[c::C, ids[1-c]]) == 0
                    assert np.count_nonzero(R[np.ix_(ids[c], ids[1-c])]) == 0
            raw, tau = base['x_raw'], base['x_tau']; k = len(tau)
            F = np.triu(raw[:k])
            Qx = qmap(raw, tau, np.eye(len(raw), k))
            check('base_Q_orthogonality', Qx.T @ Qx, np.eye(k))
            gram = B[:, ids[0]].T @ B[:, ids[0]] if shared else B.T @ B
            check('original_unwhitened_quadratic', Ln @ (F.T @ F) @ Ln.T, gram, gate=2e-8)
            right, rtau = z['inverse_right_raw'], z['inverse_right_tau']
            assert right.shape == (n, k) and len(rtau) == k
            Z = qmap(right, rtau, np.eye(n))
            Rt = np.triu(right[:k])
            check('full_right_basis_orthogonality', Z.T @ Z, np.eye(n))
            check('right_QR_identity', Z[:, :k] @ Rt, F.T)
            inner, itau = z['inverse_inner_raw'], z['inverse_inner_tau']
            assert ('inverse_inner_T' in z) == (source.get('inverse_backend', 'copy') == 'copy')
            T = z['inverse_inner_T'] if 'inverse_inner_T' in z else np.triu(inner[:k])
            assert inner.shape == (2*k, k) and len(itau) == k and T.shape == (k, k)
            assert np.array_equal(T, np.triu(inner[:k]))
            U = qmap(inner, itau, np.eye(2*k, k))
            check('inner_QR_identity', U @ T, np.vstack((np.eye(k), -Rt.T)))
            check('inner_Q_orthogonality', U.T @ U, np.eye(k))
            assert case['factor']['source_columns'] == n
            assert case['factor']['retained_inner_directions'] == k
            assert case['factor']['identity_complement_directions'] == n-k

            def inverse(value):
                coords = Z.T @ value
                coords[:k] = linalg.solve_triangular(T, linalg.solve_triangular(T, coords[:k], trans='T'))
                return Z @ coords

            zs, es, gs = (z[name] for name in ('history_z', 'history_wave', 'history_original_normal'))
            assert zs.shape == gs.shape == (3, n, channels) and z['delta_z'].shape == (2, n, channels)
            assert es.shape == (3, len(Phi)//channels, channels)
            assert np.array_equal(zs[0].ravel(), base['z'].ravel())
            assert np.array_equal(es[0].ravel(), base['wave_model_residual'].ravel())
            if source.get('pipeline'):
                import hashlib
                info = case['pipeline_info']
                assert info['source_QR_sha256'] == hashlib.sha256(memoryview(base['x_raw'].ravel(order='F'))).hexdigest()
                assert all(info['released_before_new_factors'].values())
                assert info['source_QR_released_before_correction'] and info['native_triangle_has_no_square_copy']
                for name in ('q', 'z', 'wave_model_residual'):
                    assert np.array_equal(z['pipeline_base_'+name], base[name])
            stable_history = []
            for j in range(3):
                packed = zs[j].ravel()
                data = data_map(es[j])
                normal = Gdata.T @ data + packed
                denominator = max(normG * np.linalg.norm(np.r_[data, packed]), 1e-300)
                check('all_original_normals', gs[j].ravel(), normal, scale=max(denominator, 1.), gate=2e-12)
                stable_history.append(float(np.linalg.norm(normal)/denominator))
                check('original_coefficient_wave_consistency', Phi @ (inv @ packed)-audio.ravel(),
                      es[j].ravel(), scale=max(np.linalg.norm(audio), 1e-300), gate=1e-11)
                if j < 2:
                    check('scalar_inverse_correction', z['delta_z'][j], -inverse(gs[j]))
                    check('exact_node_update', zs[j+1], zs[j]+z['delta_z'][j])
                    check('independent_wave_update', es[j+1].ravel(),
                          es[j].ravel()+Phi @ (inv @ z['delta_z'][j].ravel()),
                          scale=max(np.linalg.norm(audio), 1e-300), gate=2e-12)
            assert np.array_equal(z['z'].ravel(), zs[-1].ravel())
            assert np.array_equal(z['wave_model_residual'].ravel(), es[-1].ravel())
            assert np.array_equal(z['original_normal'].ravel(), gs[-1].ravel())
            q = z['q'].ravel()
            assert np.array_equal(q, z['q_interleaved'])
            check('complete_coefficient_recovery', inv @ z['z'].ravel(), q)
            original_z = L.T @ q
            model = np.r_[data_map(es[-1]), original_z]
            normal = G.T @ model
            stable = float(np.linalg.norm(normal)/max(normG*np.linalg.norm(model), 1e-300))
            backward = float(np.linalg.norm(G @ original_z-rhs-model)/max(np.linalg.norm(rhs), 1e-300))
            check('complete_model', model, z['original_model_residual'], gate=2e-8)
            check('complete_normal', normal, z['original_model_normal'],
                  scale=max(normG*np.linalg.norm(rhs), 1.), gate=2e-12)
            relative = float(np.linalg.norm(q-reference)/max(np.linalg.norm(reference), 1e-300))
            residual = A @ q-b; J = float(residual @ residual)
            gradient = float(np.linalg.norm(A.T @ residual)/max(np.linalg.norm(A.T @ b), 1e-300))
            e = B @ q-target; gaps = {}
            for tag in ('residual', 'representer'):
                saved = case[tag+'_certificate']
                if tag == 'residual':
                    factor = saved['residual_dual_scale']
                    delta = q+factor*linalg.solve(R, B.T @ e, assume_a='pos')
                    gap = float((1-factor)**2*(e @ e)+delta @ R @ delta)
                else:
                    delta = q-linalg.solve(R, B.T @ z['u'], assume_a='pos')
                    gap = float((e+z['u']) @ (e+z['u'])+delta @ R @ delta)
                passed = bool(gap <= 1e-6*J+1e-10)
                assert passed == saved['additional_gap_gate_passed']
                check(tag+'_gap', gap, saved['gap_upper_bound'], gate=2e-8)
                gaps[tag] = dict(gap=gap, passed=passed)
            if shared and case['label'] == 'silent_right':
                for name in ('q', 'z', 'wave_model_residual'):
                    assert np.count_nonzero(z[name][:, 1]) == 0
                for name in ('history_z', 'history_wave', 'history_original_normal', 'delta_z'):
                    assert np.count_nonzero(z[name][:, :, 1]) == 0
            if case['label'] == 'both_zero':
                for name in ('q', 'z', 'wave_model_residual', 'history_original_normal', 'delta_z'):
                    assert np.count_nonzero(z[name]) == 0
            qualified = bool(relative < 2e-7 and gradient < 2e-7 and stable <= 1e-11
                             and backward <= 1e-11 and all(c['passed'] for c in gaps.values()))
            assert qualified == case['qualified']
            r['cases'].append(dict(kind=case['kind'], label=case['label'], qualified=qualified,
                original_gradient=gradient, dense_relative_error=relative, stable_complete_normal=stable,
                original_backward=backward, certificates=gaps, independent_normal_history=stable_history,
                all_original_directions_and_two_updates_verified=True,
                pipeline_recomputed_base_exact=bool(source.get('pipeline')),
                complete_original_Frobenius=normG, previous_qualified=case['previous_qualified']))
            save(a.out/'report.json', r)
            print('AUDITED ORIGINAL CORRECTION', case['label'], qualified, stable, flush=True)
        r.update(result='independent_waveform_original_correction_known_verified', kind=source['kind'],
            inverse_backend=source.get('inverse_backend', 'copy'),
            pass_count=sum(c['qualified'] for c in r['cases']), all_qualified=all(c['qualified'] for c in r['cases']),
            producer_sha256=sha(a.study/'report.json'), auditor_sha256=sha(__file__),
            oracle_sha256={n: sha(repo/n) for n in helpers}, original_gate_not_changed=1e-11,
            no_full_or_real_or_runtime_or_hearing_qualification=True)
        save(a.out/'report.json', r)
        print(r['result'], r['pass_count'], flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error)); save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
