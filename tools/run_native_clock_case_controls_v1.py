"""Exercise independent audit equations on qualified controls and raw intervals.

No terminal real-case admission is fabricated or claimed. Original real fitting
continues unchanged; these checks do not replace actual fitted-case auditing.
"""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'known-study', 'known-audit', 'native-study', 'native-audit', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace / 'tools/python_deps'))
    import numpy as np
    from native_clock_render_v1.filter import render
    from native_clock_case_v1.diagnostics import comparison
    from extraction_sound_v1.measure import measure
    from native_clock_case_audit_v1.clock import verify as clock
    from native_clock_case_audit_v1.sound import verify as sound, comparisons
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', sources={}, inputs={}, cases=[], maximum_errors={})

    def check(name, left, right, scale, gate):
        left, right = np.asarray(left), np.asarray(right)
        assert left.shape == right.shape, (name, left.shape, right.shape)
        assert np.isfinite(left).all() and np.isfinite(right).all(), name
        if scale == 0:
            assert np.count_nonzero(left) == np.count_nonzero(right) == 0, name
            error = 0.
        else:
            error = float(np.max(abs(left - right)) / scale) if left.size else 0.
        r['maximum_errors'][name] = max(error, r['maximum_errors'].get(name, 0.))
        assert error <= gate, (name, error, gate)

    try:
        names = {'tools/run_native_clock_case_controls_v1.py', 'tools/run_native_clock_case_v1.py',
                 'tools/audit_native_clock_case_v1.py', 'research/native_clock_case_v1_plan.json'}
        for directory in ('native_clock_case_v1', 'native_clock_case_audit_v1', 'native_clock_render_v1', 'extraction_sound_v1'):
            names.update(p.relative_to(repo).as_posix() for p in (repo / 'tools' / directory).glob('*.py'))
        for name in sorted(names):
            dest = a.out / 'exact_sources' / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo / name, dest)
            r['sources'][name] = sha(dest)
        gates = load(repo / 'research/native_clock_case_v1_plan.json')['gates']
        known = load(a.known_study / 'report.json')
        ka = load(a.known_audit / 'report.json')
        native = load(a.native_study / 'report.json')
        na = load(a.native_audit / 'report.json')
        assert ka['all_known_qualified'] and ka['producer_sha256'] == sha(a.known_study / 'report.json')
        assert len(known['cases']) == len(ka['cases']) == 13
        assert na['all_preparation_qualified'] and na['producer_sha256'] == sha(a.native_study / 'report.json')
        assert len(native['cases']) == len(na['cases']) == 6
        for directory in (a.known_study, a.known_audit, a.native_study, a.native_audit):
            r['inputs'][str(directory / 'report.json')] = sha(directory / 'report.json')
        for c in known['cases']:
            path = a.known_study / c['file']
            assert sha(path) == c['sha256']; r['inputs'][str(path)] = sha(path)
            with np.load(path) as f:
                z = {k: f[k] for k in f.files}
            model = dict(fitted=z['nodes'], positions=z['positions'], source_coordinates=z['source_seconds'])
            interval = dict(raw_native_target=z['native'], native_start=z['native_start'], query16=z['query'])
            high, _ = render(z['nodes'], z['positions'], z['orders'], z['source_seconds'],
                             float(z['native_start']), int(z['count']), up=32)
            interval['query32'] = high['query']
            for up, arrays in ((16, z), (32, high)):
                clock(model, interval, arrays, up, check, gates)
            audio = dict(low=z['native'], high=high['native'], zero=np.zeros_like(z['native']))
            measured = {name: measure(value, 48000) for name, value in audio.items()}
            saved = {name + '_audio': value for name, value in audio.items()}
            saved.update({name + '_' + key: value for name, result in measured.items() for key, value in result.items()})
            for name, value in audio.items():
                sound(name, value, saved, check, gates)
            compared = {}
            for left, right in (('low', 'high'), ('low', 'low'), ('low', 'zero'), ('zero', 'low')):
                value = comparison(audio[left], audio[right], measured[left], measured[right])
                comparisons(left, right, saved, value, check, gates)
                compared[left + '_vs_' + right] = value
            output = a.out / (c['label'] + '.npz')
            np.savez_compressed(output, **saved, native32=high['native'])
            r['cases'].append(dict(label=c['label'],kind='qualified_analytic_control', all_checks_passed=True,
                file=output.name, sha256=sha(output), comparisons=compared))
            save(a.out / 'report.json', r)
            print('NATIVE_CASE_AUDIT_CONTROL', c['label'], 'PASS', flush=True)
        for c in native['cases']:
            path = a.native_study / c['file']
            assert sha(path) == c['sha256']; r['inputs'][str(path)] = sha(path)
            with np.load(path) as f:
                raw, filtered = f['raw_native_target'], f['source_FIR_only_target']
            audio = dict(raw=raw, filtered=filtered)
            measured = {name: measure(value, 48000) for name, value in audio.items()}
            saved = {name + '_audio': value for name, value in audio.items()}
            saved.update({name + '_' + key: value for name, result in measured.items() for key, value in result.items()})
            for name, value in audio.items():
                sound(name, value, saved, check, gates)
            value = comparison(filtered, raw, measured['filtered'], measured['raw'])
            comparisons('filtered', 'raw', saved, value, check, gates)
            output = a.out / (c['label'] + '.npz'); np.savez_compressed(output, **saved)
            r['cases'].append(dict(label=c['label'], kind='actual_raw_and_source_FIR_only',
                all_checks_passed=True, file=output.name, sha256=sha(output), comparison=value))
            save(a.out / 'report.json', r)
            print('NATIVE_CASE_AUDIT_RAW_CONTROL', c['label'], 'PASS', flush=True)
        r.update(result='native_clock_case_audit_equations_controls_verified', all_controls_passed=True,
            analytic_controls=13, actual_raw_interval_controls=6, no_actual_fit_binding_or_render_qualification=True,
            no_C_or_hearing_or_sustained_source_promotion=True)
        save(a.out / 'report.json', r)
    except BaseException as error:
        r.update(result='failed', error=repr(error)); save(a.out / 'report.json', r); raise


if __name__ == '__main__':
    main()
