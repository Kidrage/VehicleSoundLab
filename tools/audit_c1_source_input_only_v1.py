"""Explicit limited input proof; complete objective audit remains failed."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('workspace', 'study', 'failed-audit', 'out'): p.add_argument('--'+key, type=Path, required=True)
    a = p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'): os.environ[key] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from clock_c1_v1.audit_geometry import verify as geometry
    from c1_source_prepare_v1.audit_sampling import verify as sampling, bandwidth
    a.out.mkdir(parents=True, exist_ok=False); shutil.copy2(__file__, a.out/'executed_audit.py')
    r = dict(result='running', producer_sha256=sha(a.study/'report.json'), inputs={}, maximum_errors={})
    def check(name, actual, expected, gate=2e-12, scale=None):
        actual, expected = np.asarray(actual), np.asarray(expected)
        assert actual.shape == expected.shape and np.isfinite(actual).all() and np.isfinite(expected).all(), name
        error = float(np.max(abs(actual-expected))) if actual.size else 0.
        if scale is None: scale = max(1., float(np.max(abs(expected))) if expected.size else 0.)
        error = error/scale if scale else error
        if not scale: assert error == 0
        assert error <= gate, (name, error, gate)
        r['maximum_errors'][name] = error
    def arrays(path):
        path = Path(path); r['inputs'][str(path)] = sha(path)
        with np.load(path) as f: return {k:f[k] for k in f.files}
    try:
        info = load(a.study/'report.json'); failure = load(a.failed_audit/'report.json')
        r['inputs'][str(a.failed_audit/'report.json')] = sha(a.failed_audit/'report.json')
        assert info['result'] == 'c1_source_one_real_prepared' and failure['result'] == 'failed'
        assert failure['producer_sha256'] == r['producer_sha256']
        for path, expected in info['inputs'].items(): assert sha(path) == expected; r['inputs'][path] = expected
        row = info['cases'][0]; z = arrays(a.study/row['file']); assert sha(a.study/row['file']) == row['sha256']
        old, context = arrays(row['original_preparation']), arrays(row['original_context'])
        for key in ('positions', 'original_positions', 'orders', 'scale', 'weights', 'band_power', 'floor_active',
                    'sigma', 'amplitude', 'native', 'source_start', 'aperture', 'clock_times', 'root_hz'):
            assert np.array_equal(z[key], old[key]), key
        for new, original in (('legacy_audio', 'audio'), ('legacy_target', 'target'), ('metric_target', 'target'),
            ('legacy_source_coordinates', 'source_coordinates'), ('legacy_target_source_coordinates', 'target_source_coordinates')):
            assert np.array_equal(z[new], old[original]), new
        assert np.array_equal(z['native'], context['native']) and np.array_equal(z['legacy_source_coordinates'], context['positions'])
        assert np.array_equal(z['target'], z['audio'][2048:-2048])
        assert np.array_equal(z['target_source_coordinates'], z['source_coordinates'][2048:-2048])
        c = {k.removeprefix('clock_'):v for k,v in z.items() if k.startswith('clock_')}
        centers = context['observed_centers']
        x = 1024*context['observed_phase'][np.searchsorted(context['observed_indices'], centers)]
        y = context['coarse_positions'][np.searchsorted(context['coarse_indices'], centers)]
        for key, v in (('x', x), ('y', y)):
            assert np.array_equal(c[key], v) and np.array_equal(z['observed_clock_'+key], v)
        assert np.array_equal(z['phase_grid_indices'], context['sample_indices'])
        gr = geometry(dict(c, query=z['phase_grid_indices'], positions=z['source_coordinates']))
        bw = bandwidth(c, z['orders'], row['metadata']['bandwidth'], check)
        sam = dict(audio=z['audio'], filtered=z['source_filtered'], query=z['source_query'],
            taps=z['source_filter_taps'], crop=z['source_crop'], radius=z['source_radius'], beta=z['source_beta'])
        sp = sampling(sam, z['native'], float(z['source_start']), z['source_coordinates'], check)
        r.update(result='independent_c1_source_input_only_verified', input_verification_passed=True,
            label=row['label'], geometry=gr, bandwidth=bw, sampling=sp,
            original_calibration_geometry_and_raw_exact=True, full_objective_verification_passed=False,
            original_failed_audit_retained=True, source_fidelity_not_evaluated=True,
            eligible_for_later_source_statistics=False, no_fit_admission_or_runtime_promotion=True)
        save(a.out/'report.json', r); print('C1_SOURCE_INPUT_ONLY', gr, sp, flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error)); save(a.out/'report.json', r); raise


if __name__ == '__main__': main()
