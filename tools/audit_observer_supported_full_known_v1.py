"""Independently audit one full288 known fit, preserving every failed gate."""
import argparse, os, shutil, sys
from pathlib import Path
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'study', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
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
    r = dict(result='running', maximum_errors={}, material_read=False)

    def check(name, x, y, scale=1., gate=2e-9):
        x, y = np.asarray(x), np.asarray(y)
        assert x.shape == y.shape, name
        err = float(np.max(abs(x-y))/scale)
        assert err < gate, (name, err)
        r['maximum_errors'][name] = err

    try:
        source = load(a.study/'report.json')
        assert source['result'] == 'observer_supported_full_known_measured'
        assert source['only_one_attempt']
        assert sha(a.study/'capture.npz') == source['capture_sha256']
        for n, d in source['sources'].items():
            assert sha(repo/n) == sha(a.study/'exact_sources'/n) == d
        for n, d in source['inputs'].items():
            assert sha(n) == d
        with np.load(a.study/'capture.npz') as z:
            assert np.array_equal(z['orders'], np.arange(1, 289))
            assert np.array_equal(z['positions'], np.arange(49)*256)
            assert z['audio'].shape == (12289, 2)
            assert z['nodes'].shape == (49, 288, 2)
            scale = (np.arange(1., 289)**-1.15*np.where(np.arange(1, 289) >= 126, .1, 1.))[:, None]
            assert np.array_equal(scale, z['scale'])
            # Reconstruct declared truth without the producer's einsum.
            truth = np.zeros((49, 288, 2), complex)
            for j, index in enumerate(range(-8, 41)):
                for c in range(2):
                    env = np.ones(288, complex)
                    for k in range(1, 13):
                        h = np.arange(1, 289)
                        loading = (np.cos(h*k*.113+c*.47)+.3j*np.sin(h*(k+1)*.079+c*.91))/np.sqrt(12)
                        env += .12*np.sin(index*k*.071)*loading
                    phase = np.arange(1, 289)*.173+c*.37
                    truth[j, :, c] = (np.cos(phase)+1j*np.sin(phase))*env*scale[:, 0]
            check('declared12factor_truth', truth, z['nodes'])
            check('whole_scalar_truth', synthesize(truth, z['positions'], z['orders'], 12289), z['audio'])
            oracle = FullOracle(z['audio'], z['positions'], z['orders'], scale)
            profile = oracle.profile
            check('weights', profile['weights'], z['weights'], max(profile['weights']))
            check('band_power', profile['band_power'], z['band_power'])
            assert np.array_equal(profile['floor_active'], z['floor_active'])
            check('full_system_forward', oracle.forward(z['probe_u']), z['forward'], max(1., abs(z['forward']).max()))
            check('full_system_adjoint', oracle.backward(z['probe_v']), z['backward'], max(1., abs(z['backward']).max()))
            blocks = oracle.direct_blocks()
            check('all288_direct_preconditioner_blocks', blocks, z['right_matrix'], max(1., abs(blocks).max()))
            q = oracle.nodes(z['probe_u'])
            pair = np.concatenate((q.real, q.imag)).transpose(1, 0, 2)
            for tag, matrix in (('right_u', blocks), ('right_v', blocks.transpose(0, 2, 1))):
                result = (matrix@pair).transpose(1, 0, 2)
                check(tag, vec(result[:49]+1j*result[49:]), z[tag], max(1., abs(z[tag]).max()))
            wave = synthesize(z['fitted'], z['positions'], z['orders'], 12289)
            check('full_scalar_fitted_wave', wave, z['wave'])
            residual = wave-z['audio']
            rows, reference = oracle.spectral(residual), oracle.spectral(z['audio'])
            starts = np.arange(0, 12289-4096+1, 256)
            central = (starts >= 2048)&(starts+4096 <= 10241)
            ids = np.searchsorted([3000, 6000, 8000, 10000, 14000], np.arange(2049)*16, side='right')
            stats = dict(whole_wave_NRMSE=float(np.linalg.norm(residual)/np.linalg.norm(z['audio'])),
                target_wave_NRMSE=float(np.linalg.norm(residual[2048:10241])/np.linalg.norm(z['audio'][2048:10241])),
                target_supported_band_complex_NRMSE=[float(np.linalg.norm(rows[central][:, ids==b])/np.linalg.norm(reference[central][:, ids==b])) for b in range(6)],
                whole_supported_band_complex_NRMSE=[float(np.linalg.norm(rows[:, ids==b])/np.linalg.norm(reference[:, ids==b])) for b in range(6)],
                whole_wave_regions_NRMSE=[float(np.linalg.norm(residual[s])/np.linalg.norm(z['audio'][s])) for s in (slice(0, 2048), slice(2048, 10241), slice(10241, None))])
            for n, v in stats.items():
                check(n, v, source['metrics'][n])
            x = vec(z['fitted']/scale[None])
            data_residual = oracle.data_forward(x)-oracle.target()
            p = oracle.nodes(oracle.data_adjoint(data_residual))
            q = oracle.nodes(x)
            gradient = vec(p + (oracle.R@q.reshape(49, -1)).reshape(q.shape))
            relative = float(np.linalg.norm(gradient)/np.linalg.norm(oracle.data_adjoint(oracle.target())))
            check('original_space_gradient', relative, source['solver']['relative_stationarity'])
            cert = oracle.gap(x, source['certificate']['residual_dual_scale'])
            for n, v in cert.items():
                check(n, v, source['certificate'][n], max(1., abs(v)), 2e-8)
            assert abs(cert['primal']-cert['dual_lower_bound']-cert['gap_upper_bound']) < 2e-8*max(1., cert['primal'])
            gap_pass = cert['gap_upper_bound'] <= 1e-6*cert['primal']+1e-10
            solver = source['solver']['stop'] in (1, 2, 4, 5) and relative < 2e-7 and gap_pass
            fidelity = stats['target_wave_NRMSE'] < .02 and max(stats['target_supported_band_complex_NRMSE']) < .02
            assert bool(solver) == source['solver_qualified'] and bool(fidelity) == source['fidelity_qualified']
            r.update(result='independent_observer_supported_full_known_passed', metrics=stats,
                original_space_gradient=relative, certificate=cert, gap_gate_passed=bool(gap_pass),
                solver_qualified=bool(solver), fidelity_qualified=bool(fidelity),
                producer_sha256=sha(a.study/'report.json'), auditor_sha256=sha(__file__),
                oracles_sha256={n:sha(repo/n) for n in helpers},
                no_dense_full_inverse_or_exact_full_condition_claim=True, no_material_or_runtime_promotion=True)
        save(a.out/'report.json', r)
        print(r['result'], 'solver', r['solver_qualified'], 'fidelity', r['fidelity_qualified'], flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error))
        save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
