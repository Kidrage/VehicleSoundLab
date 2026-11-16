"""Independent every-query22k source and full real objective preparation audit."""
import argparse
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
    from c1_source_prepare_v1.audit_sampling import verify as sampling, bandwidth
    from c1_source_prepare_v1.audit_objective import verify as objective
    from clock_c1_v1.audit_geometry import verify as geometry
    repo = Path(__file__).resolve().parents[1]; a.out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, a.out/'executed_audit.py')
    r = dict(result='running', producer_sha256=sha(a.study/'report.json'), cases=[], inputs={}, maximum_errors={})
    def check(name, actual, expected, gate=2e-12, scale=None):
        actual, expected = np.asarray(actual), np.asarray(expected)
        assert actual.shape == expected.shape and np.isfinite(actual).all() and np.isfinite(expected).all(), name
        error = float(np.max(abs(actual-expected))) if actual.size else 0.
        if scale is None: scale = max(1., float(np.max(abs(expected))) if expected.size else 0.)
        error = error/scale if scale else error
        if not scale: assert error == 0
        assert error <= gate, (name, error, gate)
        r['maximum_errors'][name] = max(error, r['maximum_errors'].get(name, 0.))
    def arrays(path):
        path = Path(path); r['inputs'][str(path)] = sha(path)
        with np.load(path) as f: return {k:f[k] for k in f.files}
    try:
        info = load(a.study/'report.json')
        assert info['result'] == 'c1_source_one_real_prepared' and info['prerequisites_independently_qualified']
        assert info['new_source_identity'] == 'vsl.c1-22k-source-preparation/1' and info['no_inverse_fit']
        assert len(info['cases']) == 1 and info['label'] == 'F3 Fifth First Late'
        for name, expected in info['sources'].items(): assert sha(repo/name) == sha(a.study/'exact_sources'/name) == expected
        for path, expected in info['inputs'].items(): assert sha(path) == expected; r['inputs'][path] = expected
        guard = load(a.study/'protected_before.json'); assert guard == load(a.study/'protected_after.json')
        assert guard['label'] == info['label'] and guard['original124sources101inputs151conditionalbindings_verified']
        for spec in guard['namespaces']:
            root = Path(spec['root']); state = load(root/'report.json')
            assert state['result'] == spec['report_result'] == 'failed'
            assert not (root/info['label']).exists() and not (root/(info['label']+'_audit')).exists()
            assert sorted(p.name for p in root.iterdir() if p.is_dir()) == spec['existing_directories']
        assert not list(Path(guard['D_storage_root']).rglob('run_spec.json'))
        for row in info['cases']:
            path = a.study/row['file']; assert sha(path) == row['sha256']
            z, old, context = arrays(path), arrays(row['original_preparation']), arrays(row['original_context'])
            for key in ('positions', 'original_positions', 'orders', 'scale', 'weights', 'band_power',
                'floor_active', 'sigma', 'amplitude', 'native', 'source_start', 'aperture', 'clock_times', 'root_hz', 'probe_q'):
                assert np.array_equal(z[key], old[key]), key
            for target, original in (('metric_target', 'target'), ('legacy_audio', 'audio'), ('legacy_target', 'target'),
                ('legacy_source_coordinates', 'source_coordinates'), ('legacy_target_source_coordinates', 'target_source_coordinates')):
                assert np.array_equal(z[target], old[original]), target
            assert np.array_equal(z['legacy_source_coordinates'], context['positions'])
            assert np.array_equal(z['native'], context['native'])
            assert np.array_equal(z['target'], z['audio'][2048:-2048])
            assert np.array_equal(z['target_source_coordinates'], z['source_coordinates'][2048:-2048])
            clock = {k.removeprefix('clock_'):v for k,v in z.items() if k.startswith('clock_')}
            centers = context['observed_centers']
            p1, p2 = np.searchsorted(context['observed_indices'], centers), np.searchsorted(context['coarse_indices'], centers)
            assert np.array_equal(context['observed_indices'][p1], centers) and np.array_equal(context['coarse_indices'][p2], centers)
            x, y = 1024*context['observed_phase'][p1], context['coarse_positions'][p2]
            assert np.array_equal(z['observed_clock_x'], x) and np.array_equal(clock['x'], x)
            assert np.array_equal(z['observed_clock_y'], y) and np.array_equal(clock['y'], y)
            assert np.array_equal(z['phase_grid_indices'], context['sample_indices'])
            gr = geometry(dict(clock, query=z['phase_grid_indices'], positions=z['source_coordinates']))
            metadata = row['metadata']
            assert metadata['schema'] == 'vsl.c1-source-input/1'
            assert metadata['objective_metric_origin'] == 'explicit unchanged legacy metric_target'
            bw = bandwidth(clock, z['orders'], metadata['bandwidth'], check)
            sam = dict(audio=z['audio'], filtered=z['source_filtered'], query=z['source_query'],
                taps=z['source_filter_taps'], crop=z['source_crop'], radius=z['source_radius'], beta=z['source_beta'])
            sp = sampling(sam, z['native'], float(z['source_start']), z['source_coordinates'], check)
            assert float(z['source_nominal_cutoff_Hz']) == 22000. and int(z['native_rate_Hz']) == 48000
            op = objective(z, check)
            assert op['full_shape'] == info['full_probe_shape'] and (op['orders'], op['nodes'], op['original_nodes']) == (288, 73, 57)
            r['cases'].append(dict(label=row['label'], original_calibration_and_full_geometry_exact=True,
                geometry=gr, sampling=sp, bandwidth=bw, full_objective=op,
                original14k_legacy_and_new22k_C1_audio_explicitly_distinct=True))
        r.update(result='independent_c1_source_preparation_verified', verification_passed=True,
            source_fidelity_not_evaluated=True, eligible_for_later_source_statistics=False,
            no_producer_adapter_source_objective_fixtures_solver_imports=True,
            no_fit_or_runtime_or_hearing_qualification=True)
        save(a.out/'report.json', r); print('C1_SOURCE_PREPARATION_INDEPENDENT', r['cases'][0]['full_objective'], flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error)); save(a.out/'report.json', r); raise


if __name__ == '__main__': main()
