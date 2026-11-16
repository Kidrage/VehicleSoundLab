"""Independent supported inverse/reconstruction/native/stereo bridge audit."""
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
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'): os.environ[key] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy import signal
    from clock_c1_v1.audit_geometry import verify as geometry
    from clock_native_bridge_v1.audit_inverse import invert
    from clock_native_bridge_v1.audit_render import verify as render
    from clock_native_bridge_v1.audit_observation import verify as observe, comparisons
    from native_clock_case_audit_v1.clock import kernel
    from locked_source_tail_v1.audit_kernel import analytic
    from locked_source_diagnostics_v1.native_identity import verify as identity
    repo = Path(__file__).resolve().parents[1]; a.out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, a.out/'executed_audit.py')
    r = dict(result='running', inputs={}, cases=[], maximum_errors={}, producer_sha256=sha(a.study/'report.json'))
    def check(name, got, expected, scale, gate):
        got, expected = np.asarray(got), np.asarray(expected)
        assert got.shape == expected.shape and np.isfinite(got).all() and np.isfinite(expected).all(), name
        error = float(np.max(abs(got-expected))) if got.size else 0.
        value = error/scale if scale else error
        if not scale: assert not error
        assert value <= gate, (name, value, gate)
        r['maximum_errors'][name] = max(value, r['maximum_errors'].get(name, 0.))
    def read(path):
        path = Path(path); r['inputs'][str(path)] = sha(path)
        if path.suffix == '.json': return load(path)
        with np.load(path) as z: return {k:z[k] for k in z.files}
    def sound(root, row, values, pairs):
        s = read(root/'sound.npz'); assert sha(root/'sound.npz') == row['files']['sound.npz']
        result = {}
        for name, audio in values.items():
            assert np.array_equal(s[name+'_audio'], audio)
            result[name] = observe(name, audio, s, check, info['gates'])
        for candidate, reference in pairs:
            comparisons(candidate, reference, s, row['comparisons'][candidate+'_vs_'+reference], check, info['gates'])
        return result
    def convergence(c):
        return bool(c['wave_NRMSE'] is not None and c['wave_NRMSE'] <= .003 and
            all(v is not None and v <= .003 for v in c['band_complex_NRMSE']))
    try:
        info = read(a.study/'report.json'); mode = info['mode']
        assert info['result'] == 'clock_native_bridge_'+mode+'_measured'
        for name, expected in info['sources'].items():
            assert sha(repo/name) == sha(a.study/'exact_sources'/name) == expected
        for name, expected in info['inputs'].items(): assert sha(name) == expected
        if mode == 'known':
            assert len(info['cases']) == 22
            for row in info['cases']:
                root = a.study/row['label']; source = read(root/'source.npz')
                assert sha(root/'source.npz') == row['files']['source.npz']
                gr = geometry(source)
                back = invert(source, source['positions'])
                secant = np.max(np.diff(source['y'])/np.diff(source['x']))
                assert np.max(abs(back-source['query']))*secant < 2e-12
                if row['original_model']:
                    original = read(row['original_model'])
                    for key in ('x', 'y', 'origin', 'coefficients', 'query', 'positions'):
                        assert np.array_equal(original[key], source[key])
                    variant = row['label'][5:] if row['label'].startswith('path_') else 'stereo'
                    field = 'audio' if row['family'] == 'recorded' else 'signal__'+variant
                    assert np.array_equal(source['source'], original[field])
                rendered = {}; checks = {}
                for up in (16, 32):
                    path = root/('up'+str(up)+'.npz'); z = read(path); assert sha(path) == row['files'][path.name]
                    checks[str(up)] = render(source, z, up, check)
                    rendered['C1_'+str(up)] = z['native']
                if row['family'] == 'analytic':
                    ideal = analytic(z['dense_times']-float(source['source_origin']), source['tone_frequencies'], source['tone_coefficients'], source['source_taps'])
                    expected = signal.upfirdn(kernel(32), ideal, down=32, axis=0)[256:256+row['count']]
                    scale = float(np.max(abs(ideal)))
                    check('analytic_reference32', source['reference'], expected, scale, 2e-11)
                else:
                    original = read(row['original_source']); native = original['native']; taps = source['source_taps']
                    first = int(source['first']); count = int(source['count'])
                    assert np.array_equal(native, source['source_native']) and np.array_equal(source['raw'], native[first:first+count])
                    cut = next(c for c in read(a.workspace/'references/analysis/clock_c1_v1/known1/report.json')['recorded']['cases'] if c['label'] == row['label'][9:])['cutoff']
                    k = np.arange(1025)-512
                    expected_taps = 2*cut/48000*np.sinc(2*cut/48000*k)*np.i0(12*np.sqrt(1-(k/512)**2))/np.i0(12)
                    expected_taps /= sum(expected_taps)
                    check('recorded_explicit_source_FIR', taps, expected_taps, float(np.max(abs(expected_taps))), 2e-11)
                    expected = np.column_stack([np.convolve(native[:, c], expected_taps, mode='same')[first:first+count] for c in (0, 1)])
                    check('recorded_source_FIR_native', source['reference'], expected, float(np.max(abs(native))), 2e-11)
                rendered['reference'] = source['reference']
                obs = sound(root, row, rendered, [('C1_16', 'reference'), ('C1_32', 'reference'), ('C1_16', 'C1_32')])
                wave = row['comparisons']['C1_16_vs_reference']['wave_NRMSE']
                if row['label'] == 'pure_stopband':
                    peak = float(np.max(abs(rendered['C1_16']))/float(source['source_peak']))
                    assert abs(row['pure_stop_peak_relative']-peak) < 2e-11
                    passed = peak <= 1e-5
                elif row['label'] == 'path_zero':
                    passed = not np.count_nonzero(rendered['C1_16']) and not np.count_nonzero(rendered['C1_32'])
                else:
                    passed = wave is not None and wave < (.005 if row['family'] == 'recorded' else .003)
                if row['label'] == 'path_mono':
                    assert np.array_equal(rendered['C1_16'][:, 0], rendered['C1_16'][:, 1]) and np.array_equal(rendered['C1_32'][:, 0], rendered['C1_32'][:, 1])
                assert passed == row['known_wave_qualified']
                assert convergence(row['comparisons']['C1_16_vs_C1_32']) == row['native16_32_all_six_bands_converged']
                r['cases'].append(dict(label=row['label'], geometry=gr, renders=checks, observations=obs, known_qualified=passed))
                print('BRIDGE_INDEPENDENT_KNOWN', row['label'], passed, flush=True)
            r['all_known_qualified'] = all(c['known_qualified'] for c in r['cases'])
            assert r['all_known_qualified'] == info['all_known_qualified']
        else:
            known = read(Path(info['known_audit'])/'report.json')
            assert known['verification_passed'] and known['all_known_qualified']
            assert known['producer_sha256'] == sha(Path(info['known_study'])/'report.json')
            source = read(a.study/'source.npz'); assert sha(a.study/'source.npz') == info['files']['source.npz']
            r['geometry'] = geometry(source)
            prior = a.workspace/'references/analysis/clock_c1_v1/real1'
            old_report = read(prior/'report.json'); old = read(prior/'capture.npz')
            assert sha(prior/'capture.npz') == old_report['capture_sha256']
            for key in ('x', 'y', 'origin', 'coefficients', 'query', 'positions', 'old_positions'):
                assert np.array_equal(source[key], old[key])
            assert np.array_equal(source['C1_source'], old['signal__C1']) and np.array_equal(source['PL_source'], old['signal__original'])
            tail = read(a.workspace/'references/analysis/locked_source_tail_v1/real1/report.json')
            ns = Path(tail['source_study']); z, native = identity(read(ns/'report.json'), ns, repo, r['inputs'])
            assert np.array_equal(source['source_native'], z['native']) and np.array_equal(source['source_taps'], native['source_FIR_taps'])
            sound_file = read(a.study/'sound.npz')
            assert np.array_equal(sound_file['raw_audio'], native['raw_native_target']) and np.array_equal(sound_file['FIR_only_audio'], native['source_FIR_only_target'])
            r['renders'] = []
            for row in info['cases']:
                rendered = read(a.study/row['file']); assert sha(a.study/row['file']) == row['sha256']
                kind, up = row['label'].split('_'); up = int(up)
                r['renders'].append(dict(label=row['label'], **render(source, rendered, up, check, kind=kind)))
                assert np.array_equal(rendered['native'], sound_file[row['label']+'_audio'])
            values = {name:sound_file[name+'_audio'] for name in ('raw', 'FIR_only', 'C1_16', 'C1_32', 'PL_16', 'PL_32')}
            pairs = [(name, ref) for name in ('C1_16', 'C1_32', 'PL_16', 'PL_32') for ref in ('raw', 'FIR_only')]
            pairs += [('C1_16', 'C1_32'), ('PL_16', 'PL_32'), ('C1_16', 'PL_16'), ('C1_32', 'PL_32'), ('FIR_only', 'raw')]
            r['observations'] = sound(a.study, info, values, pairs)
            assert convergence(info['comparisons']['C1_16_vs_C1_32']) == info['C1_native16_32_converged']
            assert convergence(info['comparisons']['PL_16_vs_PL_32']) == info['PL_native16_32_converged']
            assert not info['original_source_fidelity_qualified'] and not info['eligible_for_later_source_statistics']
            assert info['original_highest_NRMSE'] > .02
        r.update(result='independent_clock_native_bridge_'+mode+'_verified', verification_passed=True,
            no_new_producer_algorithm_imports=True, no_actual_target_or_source_admission_or_runtime_promotion=True)
        save(a.out/'report.json', r); print('BRIDGE_INDEPENDENT_COMPLETE', mode, flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error)); save(a.out/'report.json', r); raise


if __name__ == '__main__':
    main()
