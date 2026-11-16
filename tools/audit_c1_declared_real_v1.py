"""Complete declared real equations only after known QR and source input proofs."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('workspace', 'known', 'out'): p.add_argument('--'+key, type=Path, required=True)
    a = p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'): os.environ[key] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from c1_declared_objective_v1.audit import verify
    from c1_declared_objective_v1.dense import matrix
    from clock_c1_v1.audit_geometry import verify as geometry
    from c1_source_prepare_v1.audit_sampling import verify as sampling, bandwidth
    repo = Path(__file__).resolve().parents[1]; a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', inputs={}, sources={}, cases=[], maximum_errors={},
        measurement_identity='vsl.c1-declared-objective/1', no_real_fit=True)
    def check(name, actual, expected, gate=2e-12, scale=None):
        actual, expected = np.asarray(actual), np.asarray(expected)
        assert actual.shape == expected.shape and np.isfinite(actual).all() and np.isfinite(expected).all(), name
        if scale is None: scale = max(1., float(np.max(abs(expected))) if expected.size else 0.)
        error = float(np.max(abs(actual-expected))) if actual.size else 0.
        error = error/scale if scale else error
        if not scale: assert error == 0
        assert error <= gate, (name, error, gate)
        r['maximum_errors'][name] = error
    def bind(path):
        path = Path(path); r['inputs'][str(path)] = sha(path); return path
    def read(path): return load(bind(path))
    def arrays(path):
        with np.load(bind(path)) as f: return {k:f[k] for k in f.files}
    try:
        known = read(a.known/'report.json')
        assert known['result'] == 'independent_c1_declared_known_verified' and known['verification_passed'] and known['all_qualified']
        assert len(known['cases']) == 4 and known['complete_augmented_QR_cases'] == 3 and len(known['invalid_rejections']) == 10
        parent = a.workspace/'references/analysis/c1_source_adapter_v1'
        info = read(parent/'prepare1/report.json'); failure = read(parent/'prepare_audit1/report.json')
        assert info['result'] == 'c1_source_one_real_prepared' and failure['result'] == 'failed'
        assert failure['producer_sha256'] == sha(parent/'prepare1/report.json')
        assert '2.5585096571438003e-12' in failure['error']
        ip = read(parent/'input_audit1/report.json')
        assert ip['input_verification_passed'] and not ip['full_objective_verification_passed']
        assert ip['producer_sha256'] == sha(parent/'prepare1/report.json')
        for item in (known, info, ip):
            for name, expected in item.get('inputs', {}).items(): assert sha(name) == expected; r['inputs'][name] = expected
            for name, expected in item.get('sources', {}).items(): assert sha(repo/name) == expected; r['sources'][name] = expected
        names = set(r['sources']) | {'tools/audit_c1_declared_real_v1.py', 'research/c1_declared_objective_v1_plan.json'}
        for name in sorted(names):
            dest = a.out/'exact_sources'/name; dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, dest); r['sources'][name] = sha(dest)
        guard = read(parent/'prepare1/protected_before.json'); assert guard == read(parent/'prepare1/protected_after.json')
        for item in guard['namespaces']:
            path = Path(item['root']); state = read(path/'report.json')
            assert state['result'] == 'failed' and not (path/info['label']).exists() and not (path/(info['label']+'_audit')).exists()
            assert sorted(v.name for v in path.iterdir() if v.is_dir()) == item['existing_directories']
        assert not list(Path(guard['D_storage_root']).rglob('run_spec.json'))
        row = info['cases'][0]; assert row['label'] == 'F3 Fifth First Late'
        path = parent/'prepare1'/row['file']; assert sha(path) == row['sha256']
        d, old, context = arrays(path), arrays(row['original_preparation']), arrays(row['original_context'])
        for key in ('positions', 'original_positions', 'orders', 'scale', 'weights', 'band_power', 'floor_active',
                    'sigma', 'amplitude', 'native', 'source_start', 'aperture', 'clock_times', 'root_hz', 'probe_q'):
            assert np.array_equal(d[key], old[key]), key
        for key, target in (('legacy_audio', 'audio'), ('legacy_target', 'target'), ('metric_target', 'target'),
            ('legacy_source_coordinates', 'source_coordinates'), ('legacy_target_source_coordinates', 'target_source_coordinates')):
            assert np.array_equal(d[key], old[target]), key
        assert np.array_equal(d['native'], context['native']) and np.array_equal(d['legacy_source_coordinates'], context['positions'])
        clock = {k.removeprefix('clock_'):v for k,v in d.items() if k.startswith('clock_')}
        centres = context['observed_centers']
        x = 1024*context['observed_phase'][np.searchsorted(context['observed_indices'], centres)]
        y = context['coarse_positions'][np.searchsorted(context['coarse_indices'], centres)]
        for key, v in (('x', x), ('y', y)):
            assert np.array_equal(clock[key], v) and np.array_equal(d['observed_clock_'+key], v)
        assert np.array_equal(d['phase_grid_indices'], context['sample_indices'])
        gr = geometry(dict(clock, query=d['phase_grid_indices'], positions=d['source_coordinates']))
        bw = bandwidth(clock, d['orders'], row['metadata']['bandwidth'], check)
        source = dict(audio=d['audio'], filtered=d['source_filtered'], query=d['source_query'], taps=d['source_filter_taps'],
            crop=d['source_crop'], radius=d['source_radius'], beta=d['source_beta'])
        sp = sampling(source, d['native'], float(d['source_start']), d['source_coordinates'], check)
        oracle, equations = verify(d, check)
        assert equations['full_shape'] == info['full_probe_shape']
        assert (equations['frames'], equations['target_frames'], equations['orders'], equations['nodes'], equations['original_nodes']) == (18430, 14334, 288, 73, 57)
        assert not equations['original_SciPy_reference_RHS_gate_passed']
        assert equations['original_SciPy_reference_RHS_error'] == 2.5585096571438003e-12
        try: matrix(oracle)
        except ValueError as error: assert 'no real-source dense fitting' in str(error)
        else: raise AssertionError('Real input admitted to known-only dense solver')
        r['cases'].append(dict(label=row['label'], complete_equations=equations, input_geometry=gr,
            input_sampling=sp, bandwidth=bw, original_full_geometry_and_calibration_exact=True))
        r.update(result='independent_c1_declared_real_preparation_verified', verification_passed=True,
            complete_declared_preparation_mathematics_passed=True, original_SciPy_preparation_audit_passed=False,
            original_failed_report_preserved=True, known_complete_proof_before_real=True,
            known_only_dense_limit_rejects_real=True, no_packet_reprepare_or_mutation=True,
            source_fidelity_not_evaluated=True, eligible_for_later_source_statistics=False,
            registration_and_resource_proof_required_before_any_fit=True, no_runtime_or_hearing_qualification=True)
        save(a.out/'report.json', r); print('C1_DECLARED_REAL_COMPLETE', equations, flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error)); save(a.out/'report.json', r); raise


if __name__ == '__main__': main()
