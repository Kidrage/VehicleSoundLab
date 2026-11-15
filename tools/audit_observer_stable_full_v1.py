"""Independent full288 waveform, stable-residual, basis and original-gap audit."""
import argparse, os, shutil, sys
from pathlib import Path
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'study', 'original', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy import linalg
    from observer_supported_v1.full_oracle import FullOracle, vec
    from observer_frequency_v1.reduced_oracle import synthesize
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, a.out/'executed_audit.py')
    helpers = ('tools/observer_supported_v1/full_oracle.py', 'tools/observer_supported_v1/audit_oracle.py',
        'tools/observer_frequency_v1/reduced_oracle.py', 'tools/observer_frequency_v1/audit_oracle.py',
        'tools/observer_complete_v1/audit_oracle.py')
    for j, name in enumerate(helpers):
        shutil.copy2(repo/name, a.out/f'executed_oracle_{j}.py')
    r = dict(result='running', maximum_errors={}, extra_inputs={})
    def check(name, x, y, scale=1., gate=2e-8):
        x, y = np.asarray(x), np.asarray(y)
        error = float(np.max(abs(x-y))/scale)
        assert x.shape == y.shape and error < gate, (name, error)
        r['maximum_errors'][name] = error
    try:
        source, original = load(a.study/'report.json'), load(a.original/'report.json')
        assert source['result'] == 'observer_stable_full_known_measured' and source['only_one_attempt']
        assert sha(a.study/'capture.npz') == source['capture_sha256']
        assert sha(a.original/'capture.npz') == original['capture_sha256']
        for name, digest in source['sources'].items():
            assert sha(repo/name) == sha(a.study/'exact_sources'/name) == digest
        for name, digest in source['inputs'].items():
            assert sha(name) == digest
        with np.load(a.study/'capture.npz') as z, np.load(a.original/'capture.npz') as o:
            for name in ('audio', 'positions', 'orders', 'scale', 'nodes', 'factors', 'loadings'):
                assert np.array_equal(z[name], o[name])
            oracle = FullOracle(z['audio'], z['positions'], z['orders'], z['scale'])
            shape = z['fitted'].shape
            L = np.linalg.cholesky(oracle.R)
            def root(v, transpose):
                q = oracle.nodes(v)
                return vec(linalg.solve_triangular(L if transpose else L.T, q.reshape(49, -1),
                    lower=transpose).reshape(shape))
            nsize, ysize = z['primal_probe'].size, oracle.data_size
            forward = np.r_[oracle.data_forward(root(z['primal_probe'], False)), z['primal_probe']]
            backward = root(oracle.data_adjoint(z['primal_test'][:ysize]), True)+z['primal_test'][ysize:]
            check('primal_full_forward', forward, z['primal_forward'], max(1., abs(forward).max()))
            check('primal_full_adjoint', backward, z['primal_backward'], max(1., abs(backward).max()))
            def forward_fn(v):
                return np.r_[oracle.data_forward(root(v, False)), v]
            def backward_fn(v):
                return root(oracle.data_adjoint(v[:ysize]), True)+v[ysize:]
            shapes = source['solver']['basis_shapes']
            for name, digest in source['basis_files'].items():
                assert sha(a.study/name) == digest
            U = np.memmap(a.study/'basis/U.bin', dtype='float64', mode='r', shape=tuple(shapes['U']), order='F')
            V = np.memmap(a.study/'basis/V.bin', dtype='float64', mode='r', shape=tuple(shapes['V']), order='F')
            for label, basis in (('U', U), ('V', V)):
                gram = np.zeros((basis.shape[1], basis.shape[1]))
                for first in range(0, len(basis), 4096):
                    block = basis[first:first+4096]
                    gram += block.T@block
                check(label+'_full_Gram', gram, z[label+'_gram'])
                check(label+'_all_orthogonality', gram, np.eye(len(gram)), gate=2e-12)
                print('FULL BASIS AUDIT', label, basis.shape, flush=True)
            H = z['H']
            complement = linalg.null_space(H.T)
            assert complement.shape[1] == H.shape[0]-H.shape[1]
            small_b = np.zeros(len(H)); small_b[0] = np.linalg.norm(z['rhs'])
            coefficients = -complement@(complement.T@small_b)
            check('stable_coefficients_SVD', coefficients, z['residual_coefficients'], max(1., np.linalg.norm(z['rhs'])))
            stable_residual = U@coefficients
            stable_normal = backward_fn(stable_residual)
            check('stable_full_residual', stable_residual, z['stable_residual'])
            check('stable_full_normal', stable_normal, z['stable_normal'], max(1., np.linalg.norm(H)*np.linalg.norm(z['rhs'])))
            outside = stable_normal-V@(V.T@stable_normal)
            check('stable_outside_normal', outside, z['outside_normal'], max(1., np.linalg.norm(H)*np.linalg.norm(z['rhs'])))
            direct_residual = forward_fn(z['z'])-z['rhs']
            backward_discrepancy = float(np.linalg.norm(direct_residual-stable_residual)/np.linalg.norm(z['rhs']))
            stable_ratio = float(np.linalg.norm(stable_normal)/max(np.linalg.norm(H)*np.linalg.norm(coefficients), 1e-300))
            stable_pass = bool(stable_ratio <= 1e-11 and backward_discrepancy <= 1e-11)
            if source['solver']['accepted']:
                assert stable_pass
            projection_columns = np.unique(np.linspace(0, V.shape[1]-1, min(64, V.shape[1]), dtype=int))
            for column in projection_columns:
                v = forward_fn(V[:, column])
                check('selected_basis_projection', v, U@H[:, column], max(1., np.linalg.norm(v)))
            check('restore_z', root(z['z'], False), vec(z['fitted']/z['scale'][None]))
            r.update(independent_stable_normal_relative=stable_ratio,
                independent_backward_discrepancy=backward_discrepancy,
                independent_stable_pass=stable_pass, full_basis_Grams_verified=True,
                independently_checked_projection_columns=projection_columns.tolist())
            wave = synthesize(z['fitted'], z['positions'], z['orders'], 12289)
            check('full_scalar_fitted_wave', wave, z['wave'])
            diff = wave-z['audio']
            rows, reference = oracle.spectral(diff), oracle.spectral(z['audio'])
            starts = np.arange(0, 8193, 256)
            central = (starts >= 2048)&(starts+4096 <= 10241)
            bands = np.searchsorted([3000, 6000, 8000, 10000, 14000], np.arange(2049)*16, side='right')
            stats = dict(whole_wave_NRMSE=float(np.linalg.norm(diff)/np.linalg.norm(z['audio'])),
                target_wave_NRMSE=float(np.linalg.norm(diff[2048:10241])/np.linalg.norm(z['audio'][2048:10241])),
                target_supported_band_complex_NRMSE=[float(np.linalg.norm(rows[central][:, bands==b])/np.linalg.norm(reference[central][:, bands==b])) for b in range(6)],
                whole_supported_band_complex_NRMSE=[float(np.linalg.norm(rows[:, bands==b])/np.linalg.norm(reference[:, bands==b])) for b in range(6)],
                whole_wave_regions_NRMSE=[float(np.linalg.norm(diff[s])/np.linalg.norm(z['audio'][s])) for s in (slice(0, 2048), slice(2048, 10241), slice(10241, None))])
            for name, value in stats.items():
                check(name, value, source['metrics'][name])
            for name, value in original['metrics'].items():
                check('old_'+name, value, source['old_results'][name])
            q = z['fitted']/z['scale'][None]
            x = vec(q)
            e = oracle.data_forward(x)-oracle.target()
            p = oracle.nodes(oracle.data_adjoint(e))
            reg = (oracle.R@q.reshape(49, -1)).reshape(shape)
            grad = float(np.linalg.norm(vec(p+reg))/np.linalg.norm(oracle.data_adjoint(oracle.target())))
            check('original_space_gradient', grad, source['solver']['relative_stationarity'])
            cert = oracle.gap(x, source['residual_certificate']['residual_dual_scale'])
            for name, value in cert.items():
                check('residual_'+name, value, source['residual_certificate'][name], max(1., abs(value)))
            u = z['u']
            restored = linalg.solve(oracle.R, oracle.nodes(oracle.data_adjoint(u)).reshape(49, -1), assume_a='pos').reshape(shape)
            repr_cert = dict(primal=float(e@e)+oracle.penalty(q),
                dual_lower_bound=float(2*oracle.target()@u-u@u)-oracle.penalty(restored),
                gap_upper_bound=float((e+u)@(e+u))+oracle.penalty(q-restored))
            for name, value in repr_cert.items():
                check('representer_'+name, value, source['representer_certificate'][name], max(1., abs(value)))
            gates = [bool(c['gap_upper_bound'] <= 1e-6*c['primal']+1e-10) for c in (cert, repr_cert)]
            for tag, passed in zip(('residual', 'representer'), gates):
                assert passed == source[tag+'_certificate']['additional_gap_gate_passed']
            qualified = bool(grad < 2e-7 and source['solver']['stop'] in (1, 2, 4, 5) and all(gates) and stable_pass and source['solver']['accepted'])
            fidelity = stats['target_wave_NRMSE'] < .02 and max(stats['target_supported_band_complex_NRMSE']) < .02
            assert qualified == source['solver_qualified'] and fidelity == source['fidelity_qualified']
            r.update(result='independent_observer_stable_full_passed', metrics=stats,
                original_space_gradient=grad, residual_certificate=cert, representer_certificate=repr_cert,
                residual_gap_passed=gates[0], representer_gap_passed=gates[1], solver_qualified=qualified,
                fidelity_qualified=bool(fidelity), no_material_or_runtime_or_hearing_promotion=True,
                producer_sha256=sha(a.study/'report.json'), auditor_sha256=sha(__file__),
                oracles_sha256={name:sha(repo/name) for name in helpers})
        save(a.out/'report.json', r)
        print(r['result'], 'solver', r['solver_qualified'], 'fidelity', r['fidelity_qualified'], flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error))
        save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
