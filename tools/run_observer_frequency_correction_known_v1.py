"""Dense mono/stereo controls for saved-solution block correction, no material."""
import argparse, os, shutil, sys
from pathlib import Path
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'block-known', 'block-audit', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'): os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy import linalg
    from observer_complete_v1.synthesis import WaveSynthesis
    from observer_frequency_v1.metric import FrequencyMetric
    from observer_frequency_v1.fit import WeightedSystem, infer
    from observer_frequency_v1.correction import correct
    from observer_inverse_v1.fit import real_vector, complex_array
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', cases=[], sources={}, inputs={}, material_read=False)
    try:
        known, audit = load(a.block_known/'report.json'), load(a.block_audit/'report.json')
        assert known['result'] == 'observer_frequency_block_known_ready'
        assert audit['result'] == 'independent_observer_frequency_block_known_passed' and audit['stereo_verified']
        assert audit['producer_sha256'] == sha(a.block_known/'report.json')
        for name, digest in known['sources'].items(): assert sha(repo/name) == digest
        names = tuple(known['sources'])+('tools/observer_frequency_v1/correction.py',
            'tools/run_observer_frequency_correction_known_v1.py',
            'research/observer_frequency_block_correction_v1_plan.json')
        for name in names:
            dest = a.out/'exact_sources'/name; dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, dest); r['sources'][name] = sha(dest)
        for path in (a.block_known/'report.json', a.block_audit/'report.json'):
            r['inputs'][str(path)] = sha(path)
        for row in known['cases']:
            path = a.block_known/row['file']; assert sha(path) == row['sha256']
            r['inputs'][str(path)] = sha(path)
            with np.load(path) as z:
                audio, positions, orders, scale = z['audio'], z['positions'], z['orders'], z['scale']
            synthesis = WaveSynthesis(len(audio), positions, orders, 1)
            metric = FrequencyMetric(audio, 64.)
            system = WeightedSystem(synthesis, scale, metric)
            initial, short_info, _ = infer(synthesis, audio, scale, metric, maxiter=8)
            nodes, info, right = correct(system, audio, initial)
            A = np.column_stack([system@x for x in np.eye(system.nsize)])
            b = system.rhs(audio); dense = linalg.lstsq(A, b, lapack_driver='gelsd')[0]
            error = float(np.linalg.norm(real_vector(nodes/scale[None])-dense)/np.linalg.norm(dense))
            assert info['converged'] and error < 2e-7
            dest = a.out/(row['label']+'.npz')
            np.savez_compressed(dest, audio=audio, positions=positions, orders=orders, scale=scale,
                weights=metric.weights, initial_nodes=initial, nodes=nodes, right_matrix=right.matrix,
                dense_solution=dense)
            case = dict(label=row['label'], file=dest.name, sha256=sha(dest), channels=1,
                initial_solve=short_info, solve=info, dense_relative_error=error)
            r['cases'].append(case); print('CORRECTION KNOWN', row['label'], info, flush=True)
        # Two independent channels share one metric but retain separate variables.
        rng = np.random.default_rng(543111)
        N = 4353; positions = np.rint(np.linspace(0, N-1, 9)).astype(int)
        orders = np.array([7, 211]); scale = np.array([[1.], [.0001]])
        synthesis = WaveSynthesis(N, positions, orders, 2)
        source = (rng.normal(size=synthesis.shape)+1j*rng.normal(size=synthesis.shape))*scale[None]
        audio = synthesis.synthesize(source); metric = FrequencyMetric(audio, 64.)
        system = WeightedSystem(synthesis, scale, metric)
        initial = source*.43
        nodes, info, right = correct(system, audio, initial)
        dense_channels = []
        for c in range(2):
            mono = WaveSynthesis(N, positions, orders, 1)
            shared = FrequencyMetric(audio[:, c:c+1], 64.)
            # The per-channel dense oracle must use the JOINT stereo weights.
            shared.weights = metric.weights.copy()
            sub = WeightedSystem(mono, scale, shared)
            A = np.column_stack([sub@x for x in np.eye(sub.nsize)])
            dense_channels.append(complex_array(linalg.lstsq(A, sub.rhs(audio[:, c:c+1]), lapack_driver='gelsd')[0], mono.shape))
        dense = np.concatenate(dense_channels, axis=2)
        error = float(np.linalg.norm(nodes/scale[None]-dense)/np.linalg.norm(dense))
        assert info['converged'] and error < 2e-7
        dest = a.out/'stereo.npz'
        np.savez_compressed(dest, audio=audio, positions=positions, orders=orders, scale=scale,
            weights=metric.weights, initial_nodes=initial, nodes=nodes, right_matrix=right.matrix,
            dense_solution=dense)
        r['cases'].append(dict(label='stereo', file=dest.name, sha256=sha(dest), channels=2,
            solve=info, dense_relative_error=error))
        zero_nodes, zero_info, _ = correct(system, np.zeros_like(audio), np.zeros_like(nodes))
        assert not np.any(zero_nodes) and zero_info['stop'] == 0 and zero_info['objective'] == 0
        r.update(result='observer_frequency_correction_known_ready', zero_rhs_exact=True,
            zero_stop_code=0, zero_not_claimed_by_original_nonzero_convergence_gate=True)
        save(a.out/'report.json', r); print(r['result'], flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error)); save(a.out/'report.json', r); raise


if __name__ == '__main__': main()
