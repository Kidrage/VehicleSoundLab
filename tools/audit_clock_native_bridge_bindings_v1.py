"""Supplement exact native interval, tone, source-filter and setting bindings."""
import argparse
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('workspace', 'study', 'out'):
        p.add_argument('--'+key, type=Path, required=True)
    a = p.parse_args(); sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    a.out.mkdir(parents=True, exist_ok=False); shutil.copy2(__file__, a.out/'executed_audit.py')
    r = dict(result='running', inputs={}, cases=[], producer_sha256=sha(a.study/'report.json'))
    def read(path):
        path = Path(path); r['inputs'][str(path)] = sha(path)
        if path.suffix == '.json': return load(path)
        with np.load(path) as z: return {k:z[k] for k in z.files}
    try:
        info = read(a.study/'report.json'); mode = info['mode']
        assert info['result'] == 'clock_native_bridge_'+mode+'_measured'
        old_root = a.workspace/'references/analysis/clock_c1_v1'
        if mode == 'known':
            old = read(old_root/'known1/report.json')
            assert len(info['cases']) == 22
            for row in info['cases']:
                source = read(a.study/row['label']/'source.npz')
                count = 4096 if row['label'] in ('near_Nyquist', 'pure_stopband') else 8192
                assert int(source['count']) == row['count'] == count
                assert float(source['native_start']) == row['native_start']
                i = int(np.searchsorted(source['x'], source['query'][4096], side='right'))-1
                dx = source['query'][4096]-source['x'][i]; c = source['coefficients'][:, i]
                t = ((c[0]*dx+c[1])*dx+c[2])*dx+c[3]+source['origin']
                assert row['native_start'] == float(np.ceil(t*48000)/48000)
                if row['original_model']:
                    original = read(row['original_model'])
                    for key in ('x', 'y', 'origin', 'coefficients', 'query', 'positions'):
                        assert np.array_equal(source[key], original[key]), key
                    if row['family'] == 'analytic':
                        spec = next(v for v in old['analytic']['cases'] if str(old_root/'known1'/v['file']) == row['original_model'])
                        coeff = original['tone_coefficients'].copy()
                        variant = row['label'][5:] if row['label'].startswith('path_') else 'stereo'
                        if variant == 'mono': coeff[:, 1] = coeff[:, 0]
                        elif variant == 'zero': coeff *= 0
                        elif variant == 'weak': coeff *= 1e-6
                        elif variant == 'delayed': coeff[:, 1] *= np.exp(-2j*np.pi*original['frequencies']*.00035)
                        assert np.array_equal(source['tone_coefficients'], coeff)
                        assert np.array_equal(source['tone_frequencies'], original['frequencies'])
                        assert np.array_equal(source['source_taps'], original['taps'])
                        assert float(source['source_origin']) == (160. if spec['origin'] > 1 else 0.)
                    else:
                        original_native = read(row['original_source'])
                        assert np.array_equal(source['source_native'], original_native['native'])
                        first = int(round(row['native_start']*48000))
                        assert int(source['first']) == first
                        assert np.array_equal(source['raw'], original_native['native'][first:first+count])
                else:
                    assert row['label'] in ('near_Nyquist', 'pure_stopband')
                    freq = np.array([19456., 20480., 22016., 23552., 24576., 28032.]) if row['label'] == 'near_Nyquist' else np.array([25984.])
                    coeff = np.array([[.09/(1+.4*i)*np.exp(.13j*(i+1)), .61*.09/(1+.4*i)*np.exp(1j*(.13*(i+1)+.37))] for i in range(len(freq))])
                    assert np.array_equal(source['tone_frequencies'], freq) and np.array_equal(source['tone_coefficients'], coeff)
                    assert float(source['source_origin']) == 17. and np.array_equal(source['source_taps'], [1.])
                    assert np.array_equal(source['x'], np.arange(-2048, 20481, 256, dtype=float))
                    assert np.array_equal(source['y'], 17+source['x']/(1024*128))
                for up in (16, 32):
                    z = read(a.study/row['label']/('up'+str(up)+'.npz'))
                    assert len(z['native']) == count and z['dense_times'][128*up] == row['native_start']
                r['cases'].append(dict(label=row['label'], original_model_source_tones_interval_settings_exact=True))
            # Exercise rejection contracts without admitting these calls as math evidence.
            from clock_native_bridge_v1.inverse import invert
            from clock_native_bridge_v1.render import render
            model = read(a.study/info['cases'][0]['label']/'source.npz')
            rejected = []
            for name, times in (('empty', []), ('nonfinite', [np.nan]), ('infinite', [np.inf]),
                ('complex', np.asarray([float(model['y'][0])], complex)), ('matrix', [[float(model['y'][0])]]),
                ('left_support', [model['y'][0]-1]), ('right_support', [model['y'][-1]+1])):
                try: invert(model, times)
                except ValueError: rejected.append(name)
                else: raise AssertionError(name)
            for name, count, up, start in (('zero_count', 0, 16, .5), ('float_count', 1., 16, .5),
                ('unsupported_up', 8192, 8, .5), ('nonfinite_start', 8192, 16, np.nan)):
                try: render(model, model['source'], model['query'], start, count, up)
                except ValueError: rejected.append(name)
                else: raise AssertionError(name)
            r['invalid_input_rejections'] = rejected
        else:
            from locked_source_diagnostics_v1.native_identity import verify
            tail = read(a.workspace/'references/analysis/locked_source_tail_v1/real1/report.json')
            root = Path(tail['source_study'])
            z, native = verify(read(root/'report.json'), root, Path(__file__).resolve().parents[1], r['inputs'])
            source = read(a.study/'source.npz')
            for key in ('first', 'stop', 'native_start'):
                assert np.array_equal(source[key], native[key]), key
            for key in ('source_start', 'native'):
                target = 'source_native' if key == 'native' else key
                assert np.array_equal(source[target], z[key]), key
            assert int(source['count']) == info['count'] == len(native['raw_native_target']) == 10372
            assert float(source['native_start']) == info['native_start'] == 160.39166666666668
            for row in info['cases']:
                rendered = read(a.study/row['file']); up = int(row['label'].split('_')[1])
                assert len(rendered['native']) == 10372 and rendered['dense_times'][128*up] == info['native_start']
                r['cases'].append(dict(label=row['label'], original_native_interval_and_source_context_exact=True))
        r.update(result='independent_clock_native_bridge_bindings_verified', verification_passed=True, mode=mode,
            scope='Supplemental input/interval/setting contracts; original independent math audit remains required')
        save(a.out/'report.json', r); print('BRIDGE_BINDINGS', mode, len(r['cases']), flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error)); save(a.out/'report.json', r); raise


if __name__ == '__main__':
    main()
