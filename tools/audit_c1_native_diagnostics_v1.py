"""Independent all-query native audit of the new explicit C1 adapter."""
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
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from clock_c1_v1.audit_geometry import verify as geometry
    from clock_native_bridge_v1.audit_render import verify as render
    from clock_native_bridge_v1.audit_observation import verify as observe, comparisons
    from locked_source_tail_v1.audit_kernel import analytic
    from observer_frequency_v1.reduced_oracle import synthesize
    from scipy import signal
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, a.out/'executed_audit.py')
    r = dict(result='running', producer_sha256=sha(a.study/'report.json'), inputs={}, cases=[], maximum_errors={})

    def check(name, got, expected, scale=1., gate=2e-11):
        got, expected = np.asarray(got), np.asarray(expected)
        assert got.shape == expected.shape and np.isfinite(got).all() and np.isfinite(expected).all(), name
        error = float(np.max(abs(got-expected))) if got.size else 0.
        relative = error/max(float(scale), 1e-300)
        if not scale:
            assert error == 0, name
        assert relative <= gate, (name, relative, gate)
        r['maximum_errors'][name] = max(relative, r['maximum_errors'].get(name, 0.))

    def arrays(path):
        with np.load(path, allow_pickle=False) as f:
            return {k:f[k] for k in f.files}

    try:
        info = load(a.study/'report.json')
        assert info['schema'] == 'vsl.c1-declared-native-diagnostic/1'
        assert info['result'] == 'c1_declared_native_'+info['mode']+'_measured'
        for name, digest in info['sources'].items():
            assert sha(repo/name) == sha(a.study/'exact_sources'/name) == digest, name
        for name, digest in info['inputs'].items():
            assert sha(name) == digest, name
        r['inputs'].update(info['inputs'])
        r['inputs'][str(a.study/'report.json')] = r['producer_sha256']
        for row in info['cases']:
            root = a.study/row['label']
            for name, digest in row['files'].items():
                assert sha(root/name) == digest, name
                r['inputs'][str(root/name)] = digest
            source = arrays(root/'source.npz')
            gr = geometry(dict(source, positions=source['positions']))
            scalar = synthesize(source['fitted'], source['fit_positions'], source['orders'], len(source['query']))
            scale = float(np.max(abs(scalar)))
            check('every_fitted_scalar', source['fitted_grid_audio'], scalar, scale)
            count, start = int(source['count']), float(source['native_start'])
            if info['mode'] == 'known':
                times = start+np.arange(count)/48000
                raw = analytic(times-160., source['source_frequency'], source['source_coefficients'], np.array([1.]))
                filtered = analytic(times-160., source['source_frequency'], source['source_coefficients'], source['source_taps'])
            else:
                first, stop = int(source['native_first']), int(source['native_stop'])
                assert stop-first == count
                assert start == float(source['source_start'])+first/48000
                raw = source['source_native'][first:stop]
                d = len(source['source_taps'])//2
                context = source['source_native'][first-d:stop+d]
                # Independent explicit offset accumulation at every native output.
                filtered = np.zeros((count, 2))
                for k, tap in enumerate(source['source_taps']):
                    filtered += tap*context[2*d-k:2*d-k+count]
            reference_scale = float(np.max(abs(raw)))
            check('raw_reference', source['raw'], raw, reference_scale)
            check('native_source_FIR', source['source_FIR'], filtered, reference_scale)
            checks = []
            for name in ('source', 'candidate'):
                field = 'source_grid_audio' if name == 'source' else 'fitted_grid_audio'
                packet = dict(source, source=source[field])
                for up in (16, 32):
                    result = render(packet, arrays(root/(name+'_'+str(up)+'.npz')), up, check)
                    checks.append(dict(name=name, up=up, verification=result))
            saved = arrays(root/'sound.npz')
            sound = {}
            for name in ('raw', 'source_FIR', 'source_16', 'source_32', 'candidate_16', 'candidate_32'):
                if name in ('raw', 'source_FIR'):
                    audio = source[name]
                else:
                    audio = arrays(root/(name+'.npz'))['native']
                assert np.array_equal(saved[name+'_audio'], audio)
                sound[name] = observe(name, audio, saved, check, info['gates'])
            for label, result in row['comparisons'].items():
                left, right = label.split('_vs_')
                comparisons(left, right, saved, result, check, info['gates'])
            known_wave = row['known_wave_qualified']
            if info['mode'] == 'known':
                assert known_wave
                if row['label'] in ('nonlinear_zero', 'nonlinear_silent_right'):
                    for name in ('raw', 'source_FIR', 'source_16', 'source_32', 'candidate_16', 'candidate_32'):
                        audio = saved[name+'_audio']
                        assert not np.count_nonzero(audio if row['label'] == 'nonlinear_zero' else audio[:, 1])
            r['cases'].append(dict(label=row['label'], geometry=gr, every_query_render=checks,
                native_observations=sound, known_wave_qualified=known_wave,
                source_native16_32_converged=row['source_native16_32_converged'],
                candidate_native16_32_converged=row['candidate_native16_32_converged']))
            save(a.out/'report.json', r)
            print('C1_NATIVE_AUDIT', row['label'], flush=True)
        r.update(result='independent_c1_declared_native_'+info['mode']+'_verified', verification_passed=True,
            all_known_qualified=all(c['known_wave_qualified'] for c in r['cases']) if info['mode'] == 'known' else None,
            no_fidelity_statistics_runtime_or_hearing_promotion=True)
        save(a.out/'report.json', r)
    except BaseException as error:
        r.update(result='failed', error=repr(error))
        save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
