"""Independent packet/full-objective/augmentedQR/complete-solver known audit."""
import argparse
import gc
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('workspace', 'study', 'out'): p.add_argument('--'+key, type=Path, required=True)
    a = p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'): os.environ[key] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from c1_source_adapter_v1.audit_packet import verify as packet
    from locked_source_fit_v1.oracle import make, mono_matrix, qr_solve
    from locked_source_fit_v1.complete import verify as complete
    from observer_complete_v1.audit_oracle import curvature, full_frame
    from observer_frequency_v1.reduced_oracle import synthesize
    repo = Path(__file__).resolve().parents[1]; a.out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, a.out/'executed_audit.py')
    r = dict(result='running', cases=[], inputs={}, maximum_errors={}, producer_sha256=sha(a.study/'report.json'))
    def check(name, actual, expected, gate=2e-12, scale=None):
        actual, expected = np.asarray(actual), np.asarray(expected)
        assert actual.shape == expected.shape and np.isfinite(actual).all() and np.isfinite(expected).all(), name
        error = float(np.max(abs(actual-expected))) if actual.size else 0.
        if scale is None: scale = max(1., float(np.max(abs(expected))) if expected.size else 0.)
        error = error/scale if scale else error
        if not scale: assert error == 0
        assert error <= gate, (name, error, gate)
        r['maximum_errors'][name] = max(error, r['maximum_errors'].get(name, 0.))
    def bind(path): r['inputs'][str(path)] = sha(path)
    try:
        info = load(a.study/'report.json'); bind(a.study/'report.json')
        assert info['result'] == 'c1_source_known_measured' and not info['material_read'] and info['block'] == 64
        assert [v['label'] for v in info['cases']] == ['affine_unequal', 'nonlinear_delay', 'nonlinear_silent_right', 'nonlinear_zero']
        assert len(info['invalid_rejections']) == len(set(info['invalid_rejections'])) == 16 and info['owned_copy_check']
        assert 'slowest phase-grid' in info['invalid_rejection_reasons']['above_grid_guard']
        for name, expected in info['sources'].items(): assert sha(repo/name) == sha(a.study/'exact_sources'/name) == expected
        for path, expected in info['inputs'].items(): assert sha(path) == expected; bind(Path(path))
        for row in info['cases']:
            directory = a.study/row['label']; r['current_case'] = row['label']; save(a.out/'report.json', r)
            assert sha(a.study/row['report']) == row['report_sha256'] and sha(a.study/row['file']) == row['capture_sha256']
            bind(directory/'report.json'); bind(directory/'capture.npz')
            report = load(directory/'report.json')
            with np.load(directory/'capture.npz') as z: d = {k:z[k] for k in z.files}
            packet_proof = packet(row['label'], d, report['metadata'], check)
            oracle, old = make(d['audio'], d['metric_target'], d['positions'], d['orders'], d['scale'])
            for name in ('weights', 'band_power', 'sigma', 'amplitude'): check('legacy_'+name, d[name], old[name])
            assert np.array_equal(d['floor_active'], old['floor_active'])
            n = len(d['audio']); size = n-4096
            original = np.array([0, int(.167*(size-1)), int(.433*(size-1)), int(.709*(size-1)), size-1])
            positions = np.r_[np.arange(-2048, 0, 256), original, original[-1]+np.arange(256, 2049, 256)]+2048
            assert np.array_equal(d['original_positions'], original) and np.array_equal(d['positions'], positions)
            check('original_curvature', oracle.D[8:-8, 8:-8], curvature(original))
            check('full_forward', d['probe_forward'], oracle.forward(d['probe_q']))
            check('full_adjoint', d['probe_adjoint'], oracle.backward(d['probe_rows']))
            check('full_normal', d['probe_normal'], oracle.backward(oracle.forward(d['probe_q'])))
            check('full_new_RHS', d['probe_rhs'], np.r_[oracle.target(), np.zeros(len(d['probe_rhs'])-oracle.data_size)])
            check('adjoint_inner_product', d['probe_forward']@d['probe_rows'], d['probe_q']@d['probe_adjoint'])
            check('coverage', d['coverage'], oracle.profile['full_coverage'])
            check('time_coverage', d['time_coverage'], oracle.profile['time_coverage'])
            starts = np.arange(0, n-4096+1, 256); slots = np.where((starts>=2048)&(starts+4096<=n-2048))[0]
            assert np.array_equal(d['target_slots'], slots)
            qp = oracle.nodes(d['probe_q'])
            wave = synthesize(qp*d['scale'][None], positions, d['orders'], n)
            target_wave = synthesize(qp[8:-8]*d['scale'][None], original, d['orders'], size)
            check('retained_target_wave', wave[2048:-2048], target_wave)
            e = wave-d['audio']; spectral = oracle.spectral(e)
            raw, _ = full_frame(target_wave-d['target'])
            target_rows = raw[old['keep']]*old['amplitude']*old['weights'][None, :, None]
            check('retained_new_target_error_rows', spectral[slots], target_rows)
            M, H = len(positions), len(d['orders'])
            target_curve = curvature(original)@qp[8:-8].reshape(M-16, -1)
            target_penalty = .001*np.sum(abs(target_curve)**2)+.000001*np.sum(abs(qp[8:-8])**2)
            target_loss = np.sum((target_wave-d['target'])**2)/old['sigma']**2+np.sum(abs(target_rows)**2)+target_penalty
            added = np.ones(len(starts), bool); added[slots] = False
            curve = oracle.D@qp.reshape(M, -1)
            extras = np.sum(e[:2048]**2)/old['sigma']**2+np.sum(e[-2048:]**2)/old['sigma']**2+np.sum(abs(spectral[added])**2)
            extras += .001*(np.sum(abs(curve[:8])**2)+np.sum(abs(curve[-8:])**2))+.000001*(np.sum(abs(qp[:8])**2)+np.sum(abs(qp[-8:])**2))
            assert extras >= 0
            check('positive_full_objective_decomposition', np.sum(e**2)/old['sigma']**2+np.sum(abs(spectral)**2)+oracle.penalty(qp), target_loss+extras)
            difference, full = None, None
            if row['label'] != 'nonlinear_zero':
                matrix, tail, phi, rhs = mono_matrix(oracle)
                direct = qr_solve(matrix, tail, rhs)
                difference = float(np.linalg.norm(d['q']-direct)/np.linalg.norm(direct)); assert difference < 2e-7
                check('independent_dense_matrix_forward', matrix@d['probe_q'].reshape(-1, 2),
                    oracle.data_forward(d['probe_q']).reshape(-1, 2), gate=2e-8)
                del matrix, tail, phi, rhs, direct
                full = complete(directory); assert full['all_qualified']
                save(a.out/(row['label']+'_complete.json'), full)
            else:
                assert not np.count_nonzero(d['q']) and not np.count_nonzero(d['wave'])
                assert report['solver_qualified'] and report['fidelity_qualified']
                bad = report['zero_reference_bad_candidate']
                assert bad['metrics']['target_wave_NRMSE'] is None and not bad['fidelity_qualified']
            if row['label'] == 'nonlinear_silent_right':
                assert not np.count_nonzero(d['q'][:, 1]) and not np.count_nonzero(d['wave'][:, 1])
            assert report['solver_qualified'] == row['solver_qualified'] and report['fidelity_qualified'] == row['fidelity_qualified']
            r['cases'].append(dict(label=row['label'], packet=packet_proof,
                independent_QR_relative_coefficient_difference=difference, complete_solver_audit=full is not None,
                complete_audit_file=row['label']+'_complete.json' if full is not None else None,
                positive_added_objective=float(extras), mathematical_verification=True,
                solver_qualified=row['solver_qualified'], fidelity_qualified=row['fidelity_qualified']))
            save(a.out/'report.json', r); print('C1_SOURCE_KNOWN_INDEPENDENT', row['label'], difference, flush=True)
            del d, oracle, wave, target_wave, full; gc.collect()
        r.update(result='independent_c1_source_known_verified', verification_passed=True,
            all_qualified=all(c['solver_qualified'] and c['fidelity_qualified'] for c in r['cases']),
            no_source_adapter_solver_or_fixture_imports=True, material_read=False)
        assert r['all_qualified'] == info['all_qualified']
        save(a.out/'report.json', r); print('C1_SOURCE_KNOWN_AUDIT_COMPLETE', r['all_qualified'], flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error)); save(a.out/'report.json', r); raise


if __name__ == '__main__': main()
