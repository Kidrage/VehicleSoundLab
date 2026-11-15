"""Independent full waveform/operator/gap audit of the same frozen288 problem."""
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
        assert source['result'] == 'observer_representer_full_known_measured' and source['only_one_attempt']
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
            qualified = bool(grad < 2e-7 and source['solver']['stop'] in (1, 2, 4, 5) and all(gates))
            fidelity = stats['target_wave_NRMSE'] < .02 and max(stats['target_supported_band_complex_NRMSE']) < .02
            assert qualified == source['solver_qualified'] and fidelity == source['fidelity_qualified']
            witness = a.original.parent/'null1/witness.npz'
            with np.load(witness) as w:
                direction = w['direction_nodes']
                derivative = 2*float(np.vdot(reg, direction).real)
                data_norm = float(np.linalg.norm(oracle.data_forward(vec(direction))))
            r['extra_inputs'][str(witness)] = sha(witness)
            r.update(result='independent_observer_representer_full_passed', metrics=stats,
                original_space_gradient=grad, residual_certificate=cert, representer_certificate=repr_cert,
                residual_gap_passed=gates[0], representer_gap_passed=gates[1], solver_qualified=qualified,
                fidelity_qualified=bool(fidelity), saved_null_witness_penalty_derivative=derivative,
                saved_null_witness_data_norm=data_norm, no_material_or_runtime_or_hearing_promotion=True,
                producer_sha256=sha(a.study/'report.json'), auditor_sha256=sha(__file__),
                oracles_sha256={name:sha(repo/name) for name in helpers})
        save(a.out/'report.json', r)
        print(r['result'], 'solver', r['solver_qualified'], 'fidelity', r['fidelity_qualified'], 'null derivative', derivative, flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error))
        save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
