"""Supplemental control-definition/provenance checks; no producer imports."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('workspace', 'study', 'out'):
        p.add_argument('--'+key, type=Path, required=True)
    a = p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[key] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from locked_source_tail_v1.audit_kernel import analytic
    from clock_structure_v1.audit import interpolate
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    relative = Path(__file__).relative_to(repo).as_posix()
    dest = a.out/'exact_sources'/relative; dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(__file__, dest)
    r = dict(result='running', sources={relative: sha(dest)}, inputs={}, checks={})
    try:
        def read(path):
            path = Path(path); r['inputs'][str(path)] = sha(path)
            return load(path)
        def capture(path):
            path = Path(path); r['inputs'][str(path)] = sha(path)
            with np.load(path) as f:
                return {key: f[key] for key in f.files}
        known = read(a.study/'known1/report.json'); real = read(a.study/'real1/report.json')
        for stage, audit in (('known1', 'known_audit1'), ('real1', 'audit1'), ('review1', 'review_audit1')):
            proof = read(a.study/audit/'report.json')
            assert proof['verification_passed'] and proof['producer_sha256'] == sha(a.study/stage/'report.json')
        k = capture(a.study/'known1/capture.npz')
        parent = capture(Path(known['tail_study'])/'known1/capture.npz')
        for key in ('coefficients', 'frequencies', 'taps', 'weights', 'amplitude'):
            assert np.array_equal(k[key], parent[key])
        u = np.arange(len(parent['coordinates']))
        nodes = np.array([1024.25, 4096.5, 8192.125, 12288.75, 16384.3])
        jumps = np.array([1e-8, -6e-9, 4e-9, -7e-9, 3e-9])
        def law(v, smooth=False):
            out = .36+v/65536
            for node, jump in zip(nodes, jumps):
                d = v-node
                out += jump*((d+np.sqrt(d*d+256**2))/2 if smooth else np.maximum(d, 0))
            return out
        target, smooth = law(u), law(u, True)
        endpoint_delta = np.array([target[0]-smooth[0], target[-1]-smooth[-1]])
        def adjustment(v):
            return endpoint_delta[0]+(v-u[0])/(u[-1]-u[0])*(endpoint_delta[1]-endpoint_delta[0])
        expected = dict(affine=.36+u/65536, manufactured_C0=target, exact_smooth=smooth+adjustment(u))
        x = k['smooth_PL__graph_x']; y = law(x, True)+adjustment(x)
        assert np.max(abs(y-k['smooth_PL__graph_y'])) < 2e-12
        expected['sampled_smooth_PL'] = interpolate(u, x, y)
        for name, value in expected.items():
            error = float(np.max(abs(value-k['clock__'+name])))
            assert error < 2e-12
            r['checks'][name+'_clock_max_seconds'] = error
        coeff, freq, taps = parent['coefficients'], parent['frequencies'], parent['taps']
        for key, coefficients in (('mono', np.repeat(coeff[:, :1], 2, axis=1)), ('zero', coeff*0), ('weak', coeff*1e-6)):
            error = float(np.max(abs(analytic(k['clock__affine'], freq, coefficients, taps)-k[key])))
            assert error/np.sum(abs(coeff)) < 2e-12
            r['checks'][key+'_max_FS'] = error
        d = capture(real['context_file']); actual = capture(a.study/'real1/capture.npz')
        for key, original in (('rebuilt_correction', 'observed_correction'), ('rebuilt_phase', 'observed_phase'),
                              ('rebuilt_source_clock_phase', 'source_clock_phase'), ('rebuilt_coarse_positions', 'coarse_positions')):
            assert np.array_equal(actual[key], d[original])
        at = interpolate(d['sample_indices']/1024, d['observed_phase'], d['observed_indices'])
        coordinate_error = float(np.max(abs(at-actual['inverse_at']))*np.max(np.diff(d['coarse_positions'])))
        assert coordinate_error < 2e-12
        r['checks']['inverse_at_error_converted_seconds'] = coordinate_error
        r.update(result='independent_clock_structure_bindings_verified', verification_passed=True,
            coefficients_FIR_and_original_observer_exact=True,
            all_four_known_clocks_and_mono_zero_weak_verified=True,
            actual_rebuilt_arrays_bitwise_bound_to_frozen_context=True,
            no_source_admission_or_clock_replacement=True)
        save(a.out/'report.json', r)
        print('CLOCK_STRUCTURE_BINDINGS_VERIFIED', flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error)); save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
