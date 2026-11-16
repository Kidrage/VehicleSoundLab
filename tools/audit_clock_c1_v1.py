"""Independent Hermite, source render and saved-wave counterfactual audit."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'study', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[key] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from clock_c1_v1.audit_geometry import verify as geometry
    from clock_c1_v1.audit_known import verify_analytic, verify_recorded
    from clock_c1_v1.audit_stereo import verify as stereo, compare
    from locked_source_tail_v1.audit_kernel import sinc_sum
    from locked_source_tail_v1.audit_measure import verify as spectra
    from locked_source_diagnostics_v1.native_identity import verify as identity
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, a.out/'executed_audit.py')
    r = dict(result='running', inputs={}, producer_sha256=sha(a.study/'report.json'))
    def bind(path):
        path = Path(path); r['inputs'][str(path)] = sha(path)
        return load(path) if path.suffix == '.json' else path
    def array(path):
        with np.load(path) as z:
            return {k:z[k] for k in z.files}
    try:
        info = bind(a.study/'report.json'); mode = info['mode']
        assert info['result'] == 'clock_c1_'+mode+'_measured'
        for name, expected in info['sources'].items():
            assert sha(repo/name) == sha(a.study/'exact_sources'/name) == expected
        for name, expected in info['inputs'].items():
            assert sha(name) == expected
            r['inputs'][name] = expected
        if mode == 'known':
            r['analytic'], r['recorded'] = [], []
            for row in info['analytic']['cases']:
                path = bind(a.study/row['file']); assert sha(path) == row['sha256']
                r['analytic'].append(dict(file=row['file'], **verify_analytic(array(path), row)))
            for row in info['recorded']['cases']:
                path = bind(a.study/row['file']); assert sha(path) == row['sha256']
                original = array(bind(row['source']))
                r['recorded'].append(dict(label=row['label'], **verify_recorded(array(path), original, row)))
                print('C1_INDEPENDENT', row['label'], 'PASS', flush=True)
            assert len(r['analytic']) == len(r['recorded']) == 8 and info['all_known_qualified']
            assert info['analytic']['rejections'] == ['complex', 'nonfinite', 'duplicate', 'reverse_x',
                'flat_y', 'reverse_y', 'too_short', 'left', 'right', 'nan_query', 'complex_query', 'empty_query']
            r['all_known_qualified'] = True
        else:
            capture = bind(a.study/'capture.npz'); assert sha(capture) == info['capture_sha256']
            d = array(capture); r['geometry'] = geometry(d)
            ka = bind(Path(info['known_audit'])/'report.json')
            assert ka['verification_passed'] and ka['all_known_qualified']
            assert ka['producer_sha256'] == sha(Path(info['known_study'])/'report.json')
            tail = a.workspace/'references/analysis/locked_source_tail_v1'
            prior = bind(tail/'real1/report.json')
            old = array(bind(tail/'real1/capture.npz'))
            assert sha(tail/'real1/capture.npz') == prior['capture_sha256']
            source_study = Path(prior['source_study']); source = bind(source_study/'report.json')
            z, _ = identity(source, source_study, repo, r['inputs'])
            original = array(bind(info['context_file']))
            q = array(bind(prior['query_file']))
            nodes = original['observed_centers']
            assert np.array_equal(d['x'], 1024*original['observed_phase'][np.searchsorted(original['observed_indices'], nodes)])
            assert np.array_equal(d['y'], original['coarse_positions'][np.searchsorted(original['coarse_indices'], nodes)])
            assert np.array_equal(d['query'], original['sample_indices'])
            assert np.array_equal(d['old_positions'], original['positions'])
            assert np.array_equal(d['old_positions'], z['source_coordinates'])
            for key in ('filtered', 'crop', 'taps', 'weights', 'amplitude', 'source_start'):
                assert np.array_equal(d[key], q[key]) and np.array_equal(d[key], old[key])
            assert np.array_equal(d['weights'], z['weights']) and np.array_equal(d['amplitude'], z['amplitude'])
            assert np.array_equal(d['signal__original'], old['signal__reference2048'])
            query = (d['positions']-float(d['source_start'])-int(d['crop'][0])/48000)*48000
            assert np.array_equal(query, d['source_query'])
            rebuilt = sinc_sum(d['filtered'], query, 2048)
            error = float(np.max(abs(rebuilt-d['signal__C1']))/np.max(abs(d['filtered'])))
            assert error < 2e-12
            r['independent_all_query_kernel_max_relative_source_peak'] = error
            values = {name:d['signal__'+name] for name in ('original', 'C1')}
            r['spectra'] = spectra(values, d, info['observations'], d['weights'], float(d['amplitude']))
            so, co = stereo(values['original'], d, 'original'); sn, cn = stereo(values['C1'], d, 'C1')
            r['stereo'] = dict(original_checks=co, C1_checks=cn, report=compare(so, sn, info['stereo']))
            assert info['original_highest_NRMSE'] > .02
            assert not info['original_source_fidelity_qualified'] and not info['eligible_for_later_source_statistics']
        r.update(result='independent_clock_c1_'+mode+'_verified', verification_passed=True,
            no_new_producer_algorithm_imports=True, no_source_or_sustained_C_or_hearing_promotion=True)
        save(a.out/'report.json', r)
        print('C1_INDEPENDENT_COMPLETE', mode, flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error)); save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
