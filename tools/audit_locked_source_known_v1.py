"""Independent changed-source/legacy-calibration controls; no fitter imports."""
import argparse
import gc
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'study', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(args.workspace/'tools/python_deps'))
    import numpy as np
    from scipy import linalg
    from observer_complete_v1.audit_oracle import curvature, full_frame
    from observer_frequency_v1.reduced_oracle import synthesize
    from observer_supported_v1.audit_oracle import metric
    from locked_source_fit_v1.oracle import make, mono_matrix, qr_solve
    from locked_source_fit_v1.complete import verify

    repo = Path(__file__).resolve().parents[1]
    args.out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, args.out/'executed_audit.py')
    report = dict(result='running', cases=[], maximum_errors={}, inputs={})

    def check(name, actual, expected, gate=2e-12, scale=None):
        actual, expected = np.asarray(actual), np.asarray(expected)
        assert actual.shape == expected.shape, (name, actual.shape, expected.shape)
        denominator = max(1., float(np.max(abs(expected)))) if scale is None else max(float(scale), 1e-300)
        error = float(np.max(abs(actual-expected))/denominator)
        report['maximum_errors'][name] = max(error, report['maximum_errors'].get(name, 0.))
        assert error < gate, (name, error, gate)

    def bind(path):
        report['inputs'][str(path)] = sha(path)

    try:
        source = load(args.study/'report.json')
        bind(args.study/'report.json')
        labels = {'independent_unequal': 4609, 'phase_delay_right': 4353,
                  'silent_right': 4865, 'both_zero': 4609}
        assert source['result'] == 'locked_source_fit_known_measured'
        assert [c['label'] for c in source['cases']] == list(labels)
        assert source['block'] == 64 and not source['material_read']
        for name, digest in source['sources'].items():
            assert sha(repo/name) == sha(args.study/'exact_sources'/name) == digest, name
        assert set(source['invalid_rejections']) == {
            'missing_metric_target', 'short_metric_target', 'nonfinite_metric_target',
            'changed_target_slice', 'complex_audio', 'nonpositive_scale'}

        for case in source['cases']:
            label = case['label']
            directory = args.study/label
            assert sha(args.study/case['report']) == case['report_sha256']
            assert sha(args.study/case['file']) == case['capture_sha256']
            bind(directory/'capture.npz'); bind(directory/'report.json')
            info = load(directory/'report.json')
            with np.load(directory/'capture.npz') as saved:
                z = {name: saved[name] for name in saved.files}

            # Reconstruct BOTH distinct analytic sources, not the producer fixture.
            size = labels[label]
            orders = np.array([5, 65, 110, 140, 185, 300])
            scale = np.array([.19, .13, .09, .08, .06, .04])[:, None]
            original = np.array([0, int(.167*(size-1)), int(.433*(size-1)),
                                 int(.709*(size-1)), size-1])
            positions = np.r_[np.arange(-2048, 0, 256), original,
                              original[-1]+np.arange(256, 2049, 256)]+2048
            for name, expected in (('orders', orders), ('scale', scale),
                                   ('positions', positions), ('original_positions', original)):
                assert np.array_equal(z[name], expected), name
            frames, nodes, harmonics = size+4096, len(positions), len(orders)
            t, h = positions[:, None]/1024, np.arange(harmonics)[None, :]
            old_nodes = np.empty((nodes, harmonics, 2), complex)
            old_nodes[:, :, 0] = (1+.12*np.sin(.37*t+.43*h))*np.exp(1j*(.29*h+.08*np.cos(.51*t+.2*h)))
            old_nodes[:, :, 1] = (.31+.08*np.cos(.63*t+.73*h))*np.exp(1j*(1.1+.81*h+.19*np.sin(.41*t+.3*h)))
            if label == 'phase_delay_right':
                old_nodes[:, :, 1] = .63*old_nodes[:, :, 0]*np.exp(-2j*np.pi*orders[None, :]*(.00035*65536)/1024)
            if label == 'silent_right': old_nodes[:, :, 1] = 0
            if label == 'both_zero': old_nodes[:] = 0
            changed_nodes = old_nodes*(.72+.09*np.arange(harmonics)[None, :, None])*np.exp(.11j*np.arange(harmonics)[None, :, None])
            legacy = synthesize(old_nodes*scale[None], positions, orders, frames)
            audio = synthesize(changed_nodes*scale[None], positions, orders, frames)
            if label != 'both_zero':
                endpoint = 1e-6*(1+(-1.)**np.arange(frames))
                legacy[:, 0] += endpoint; audio[:, 0] += endpoint
                if label != 'silent_right':
                    legacy[:, 1] += .37*endpoint; audio[:, 1] += .37*endpoint
            check('original_analytic_nodes', z['source_nodes'], old_nodes)
            check('changed_analytic_nodes', z['new_source_nodes'], changed_nodes)
            check('explicit_legacy_metric_target', z['metric_target'], legacy[2048:-2048])
            check('independent_new_source_audio', z['audio'], audio)
            assert np.array_equal(z['audio'][2048:-2048], z['target'])
            if label != 'both_zero':
                assert np.linalg.norm(z['target']-z['metric_target']) > .01*np.linalg.norm(z['metric_target'])

            oracle, old = make(audio, z['metric_target'], positions, orders, scale)
            new_calibration = metric(z['target'], 64.)
            for name in ('sigma', 'amplitude', 'weights', 'band_power'):
                check('locked_legacy_'+name, z[name], old[name])
            assert np.array_equal(z['floor_active'], old['floor_active'])
            if label != 'both_zero':
                assert abs(new_calibration['sigma']/old['sigma']-1) > .01
            check('finite_context_coverage', z['coverage'], oracle.profile['full_coverage'])
            check('finite_context_time_coverage', z['time_coverage'], oracle.profile['time_coverage'])
            check('retained_target_coverage', oracle.profile['full_coverage'][2048:-2048], old['full_coverage'])
            starts = np.arange(0, frames-4096+1, 256)
            slots = np.where((starts >= 2048) & (starts+4096 <= frames-2048))[0]
            assert np.array_equal(z['target_slots'], slots)
            new_rows, _ = full_frame(z['target'])
            check('new_target_RHS_not_old_calibration_rows', oracle.profile['rows'][slots], new_rows[old['keep']]*old['amplitude'])
            check('unchanged_original_curvature', oracle.D[8:-8, 8:-8], curvature(original))
            check('complete_forward', z['probe_forward'], oracle.forward(z['probe_q']))
            check('complete_adjoint', z['probe_adjoint'], oracle.backward(z['probe_rows']))
            check('complete_new_RHS', z['probe_rhs'], np.r_[oracle.target(), np.zeros(len(z['probe_rhs'])-oracle.data_size)])
            check('adjoint_inner_product', z['probe_forward']@z['probe_rows'], z['probe_q']@z['probe_adjoint'])

            # The retained target objective uses new data and legacy calibration.
            qp = oracle.nodes(z['probe_q'])
            probe_wave = synthesize(qp*scale[None], positions, orders, frames)
            target_wave = synthesize(qp[8:-8]*scale[None], original, orders, size)
            check('retained_target_wave', probe_wave[2048:-2048], target_wave)
            error = probe_wave-audio
            spectral = oracle.spectral(error)
            raw, _ = full_frame(target_wave-z['target'])
            target_rows = raw[old['keep']]*old['amplitude']*old['weights'][None, :, None]
            check('retained_target_error_rows', spectral[slots], target_rows)
            target_curvature = curvature(original)@qp[8:-8].reshape(nodes-16, -1)
            target_penalty = .001*np.sum(abs(target_curvature)**2)+.000001*np.sum(abs(qp[8:-8])**2)
            target_loss = float(np.sum((target_wave-z['target'])**2)/old['sigma']**2+np.sum(abs(target_rows)**2)+target_penalty)
            added = np.ones(len(starts), bool); added[slots] = False
            full_curvature = oracle.D@qp.reshape(nodes, -1)
            extras = float(np.sum(error[:2048]**2)/old['sigma']**2+np.sum(error[-2048:]**2)/old['sigma']**2
                +np.sum(abs(spectral[added])**2)+.001*(np.sum(abs(full_curvature[:8])**2)+np.sum(abs(full_curvature[-8:])**2))
                +.000001*(np.sum(abs(qp[:8])**2)+np.sum(abs(qp[-8:])**2)))
            full_loss = float(np.sum(error**2)/old['sigma']**2+np.sum(abs(spectral)**2)+oracle.penalty(qp))
            assert extras >= 0
            check('positive_objective_decomposition', full_loss, target_loss+extras)

            difference, complete = None, None
            if label != 'both_zero':
                matrix, tail, phi, rhs = mono_matrix(oracle)
                reference = qr_solve(matrix, tail, rhs)
                difference = float(np.linalg.norm(z['q']-reference)/max(np.linalg.norm(reference), 1e-300))
                assert difference < 2e-7
                check('independent_dense_matrix_forward', matrix@z['probe_q'].reshape(-1, 2),
                      oracle.data_forward(z['probe_q']).reshape(-1, 2), gate=2e-8)
                root = np.linalg.cholesky(oracle.R)
                inverse = linalg.solve_triangular(root.T, np.eye(nodes))
                transform = linalg.block_diag(np.kron(inverse, np.eye(harmonics)), np.kron(inverse, np.eye(harmonics)))
                mapped = matrix@transform
                explicit_norm = np.sqrt(2*(np.sum(mapped*mapped)+2*nodes*harmonics))
                check('explicit_all_bin_root_Frobenius', info['production_original_trace']['root_Frobenius'],
                      explicit_norm, scale=explicit_norm, gate=2e-11)
                del matrix, tail, phi, rhs, mapped, transform
                complete = verify(directory)
                assert complete['all_qualified'] and all(h['original_gates_passed'] for h in complete['original_correction_history'])
                save(args.out/(label+'.json'), complete)
            else:
                assert np.count_nonzero(z['q']) == np.count_nonzero(z['wave']) == 0
                assert info['solver_qualified'] and info['fidelity_qualified']
                assert all(v == 0 for v in info['metrics']['target_supported_band_complex_NRMSE'])
                bad = info['zero_reference_bad_candidate']
                assert bad['metrics']['target_wave_NRMSE'] is None and not bad['fidelity_qualified']
                assert all(v is None for v in bad['metrics']['target_supported_band_complex_NRMSE'])
            if label == 'silent_right':
                assert np.count_nonzero(z['q'][:, 1]) == np.count_nonzero(z['wave'][:, 1]) == 0
            report['cases'].append(dict(label=label, all_qualified=True,
                calibration_sigma=old['sigma'], new_target_sigma_if_wrongly_recalibrated=new_calibration['sigma'],
                positive_added_objective=extras, independent_QR_relative_coefficient_difference=difference,
                complete_audit_file=label+'.json' if complete else None))
            save(args.out/'report.json', report)
            print('AUDIT_LOCKED_SOURCE', label, 'PASS', flush=True)
            del z, oracle, audio, legacy
            gc.collect()
        report.update(result='independent_locked_source_known_verified', all_qualified=True,
            producer_sha256=sha(args.study/'report.json'),
            no_real_fit_or_C_or_hearing_promotion=True)
        save(args.out/'report.json', report)
    except BaseException as error:
        report.update(result='failed', error=repr(error))
        save(args.out/'report.json', report)
        raise


if __name__ == '__main__': main()
