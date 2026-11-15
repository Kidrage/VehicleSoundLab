"""Saved full-case data-null witness; no fitting, correction or material access."""
import argparse, os, shutil, sys
from pathlib import Path
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'study', 'audit', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy import linalg
    from observer_supported_v1.full_oracle import FullOracle, vec
    from observer_frequency_v1.reduced_oracle import carrier_table, synthesize
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    sources = ('tools/diagnose_observer_supported_null_v1.py',
        'tools/observer_supported_v1/full_oracle.py', 'tools/observer_supported_v1/audit_oracle.py',
        'tools/observer_frequency_v1/reduced_oracle.py', 'tools/observer_frequency_v1/audit_oracle.py',
        'tools/observer_complete_v1/audit_oracle.py')
    r = dict(result='running', sources={}, inputs={}, no_fit_or_correction=True, material_read=False)
    try:
        source, audit = load(a.study/'report.json'), load(a.audit/'report.json')
        assert audit['result'] == 'independent_observer_supported_full_known_passed'
        assert audit['producer_sha256'] == sha(a.study/'report.json')
        assert not audit['solver_qualified']
        for name in sources:
            dest = a.out/'exact_sources'/name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, dest)
            r['sources'][name] = sha(dest)
        for path in (a.study/'capture.npz', a.study/'report.json', a.audit/'report.json'):
            r['inputs'][str(path)] = sha(path)
        with np.load(a.study/'capture.npz') as z:
            N, C = z['audio'].shape
            M, H, _ = z['fitted'].shape
            unknowns = 2*M*H*C
            # Every spectral row is a linear transform of these waveform samples.
            rank_bound, nullity_bound = N*C, unknowns-N*C
            assert (unknowns, rank_bound, nullity_bound) == (56448, 24578, 31870)
            center = M//2
            active = np.arange(z['positions'][center]-255, z['positions'][center]+256)
            hat = 1-abs(active-z['positions'][center])/256
            table = carrier_table(tuple(int(h) for h in z['orders']))[active % 1024]
            local = np.column_stack((table.real*z['scale'][:, 0], -table.imag*z['scale'][:, 0]))*hat[:, None]
            assert local.shape == (511, 576)
            _, singular, vh = linalg.svd(local, full_matrices=True, lapack_driver='gesvd')
            # Last65 vectors exist by rectangular dimensions alone; no rank threshold.
            null = vh[511:].T
            null_error = float(np.max(abs(local@null)))
            assert null_error < 2e-12
            oracle = FullOracle(z['audio'], z['positions'], z['orders'], z['scale'])
            q = z['fitted']/z['scale'][None]
            reg = (oracle.R@q.reshape(M, -1)).reshape(q.shape)[center, :, 0]
            local_gradient = np.r_[reg.real, reg.imag]
            projection = null@(null.T@local_gradient)
            assert np.linalg.norm(projection) > 1e-16
            direction = -projection/np.linalg.norm(projection)
            nodes = np.zeros(q.shape, complex)
            nodes[center, :, 0] = direction[:H]+1j*direction[H:]
            wave = synthesize(nodes*z['scale'][None], z['positions'], z['orders'], N)
            assert np.max(abs(wave)) < 2e-12
            data_norm = float(np.linalg.norm(oracle.data_forward(vec(nodes))))
            assert data_norm < 2e-8
            residual = oracle.data_forward(vec(q))-oracle.target()
            data_derivative = 2*float(residual@oracle.data_forward(vec(nodes)))
            reg_derivative = 2*float(local_gradient@direction)
            assert reg_derivative < 0
            path = a.out/'witness.npz'
            np.savez_compressed(path, active=active, local=local, singular_values=singular,
                null_basis=null, direction=direction, direction_nodes=nodes, wave=wave,
                local_regularizer_gradient=local_gradient)
            r.update(result='observer_supported_data_null_diagnosed',
                normalized_real_unknowns=unknowns, waveform_data_rank_upper_bound=rank_bound,
                data_null_dimension_lower_bound=nullity_bound, independent_spectral_rows_add_no_rank=True,
                local_node=center, active_waveform_rows=511, local_real_unknowns=576,
                local_data_null_dimension_lower_bound=65, local_witness_basis_error_FS=null_error,
                witness_wave_peak_FS=float(np.max(abs(wave))), witness_weighted_data_norm=data_norm,
                saved_fit_data_directional_derivative=data_derivative,
                saved_fit_penalty_directional_derivative=reg_derivative,
                saved_fit_null_regularizer_gradient_norm=float(np.linalg.norm(projection)),
                ridge_still_makes_regularized_objective_unique=True,
                not_proof_of_physical_source_ambiguity_or_sole_solver_failure_cause=True,
                no_nodes_or_saved_solution_updated=True, witness_sha256=sha(path))
        save(a.out/'report.json', r)
        print(r['result'], 'nullity lower bound', nullity_bound,
              'data norm', data_norm, 'penalty derivative', reg_derivative, flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error))
        save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
