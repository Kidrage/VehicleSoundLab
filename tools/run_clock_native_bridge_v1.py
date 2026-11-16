"""Known-first supported C1 inverse and physical48k reconstruction study."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('workspace', 'out'):
        p.add_argument('--'+key, type=Path, required=True)
    p.add_argument('--mode', choices=('known', 'real'), required=True)
    p.add_argument('--known-study', type=Path); p.add_argument('--known-audit', type=Path)
    a = p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[key] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy import signal
    from clock_c1_v1.geometry import evaluate
    from clock_native_bridge_v1.inverse import roundtrip
    from clock_native_bridge_v1.render import render
    from clock_native_bridge_v1.controls import generate
    from clock_native_bridge_v1.observation import observe, compare_all, convergence
    from locked_source_tail_v1.known import evaluate as tones
    from locked_source_diagnostics_v1.native_identity import verify as identity
    repo = Path(__file__).resolve().parents[1]; a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', mode=a.mode, sources={}, inputs={}, cases=[])
    def read(path, expected=None):
        path = Path(path); r['inputs'][str(path)] = sha(path)
        if expected is not None: assert sha(path) == expected
        return load(path) if path.suffix == '.json' else path
    def arrays(path):
        with np.load(path) as z: return {k:z[k] for k in z.files}
    def source_model(d):
        return {k:d[k] for k in ('x', 'y', 'origin', 'coefficients', 'interval_minimum_derivative', 'node_preservation_max_seconds')}
    try:
        prior = a.workspace/'references/analysis/clock_c1_v1'
        old = read(prior/('known1' if a.mode == 'known' else 'real1')/'report.json')
        proof = read(prior/('known_audit1' if a.mode == 'known' else 'audit1')/'report.json')
        assert proof['verification_passed'] and proof['producer_sha256'] == sha(prior/('known1' if a.mode == 'known' else 'real1')/'report.json')
        names = set(old['sources']) | {'tools/run_clock_native_bridge_v1.py', 'tools/audit_clock_native_bridge_v1.py',
            'research/clock_native_bridge_v1_plan.json'}
        for folder in ('clock_native_bridge_v1', 'native_error_budget_v1', 'native_clock_render_v1',
                       'native_clock_case_v1', 'native_clock_case_audit_v1', 'extraction_sound_v1'):
            names.update(path.relative_to(repo).as_posix() for path in (repo/'tools'/folder).glob('*.py'))
        for name in sorted(names):
            dest = a.out/'exact_sources'/name; dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, dest); r['sources'][name] = sha(dest)
        for name, expected in old['sources'].items(): assert sha(repo/name) == expected
        gates = read(repo/'research/native_clock_case_v1_plan.json')['gates']
        r.update(gates=gates, no_source_fit_clock_target_or_runtime_change=True,
            original_source_fidelity_qualified=False, eligible_for_later_source_statistics=False)
        if a.mode == 'known':
            for fixture in generate(a.workspace, read, arrays):
                label = fixture['label']; out = a.out/label; out.mkdir()
                model, q = source_model(fixture['model']), fixture['query']
                count = fixture['count']
                start = fixture.get('native_start', float(np.ceil(evaluate(model, q[4096:4097])[0]*48000)/48000))
                source = dict(model, query=q, positions=evaluate(model, q), source=fixture['source'],
                    native_start=np.array(start), count=np.array(count), source_taps=fixture['source_taps'])
                outputs = {}
                for up in (16, 32):
                    z = render(model, fixture['source'], q, start, count, up)
                    np.savez_compressed(out/('up'+str(up)+'.npz'), **z)
                    outputs['C1_'+str(up)] = z['native']
                if fixture['family'] == 'analytic':
                    truth = tones(z['dense_times']-fixture['source_origin'], fixture['frequencies'],
                                  fixture['coefficients'], fixture['source_taps'])
                    reference = signal.fftconvolve(truth, z['taps'][:, None], mode='valid', axes=0)[::32]
                    source.update(tone_frequencies=fixture['frequencies'], tone_coefficients=fixture['coefficients'],
                        source_origin=np.array(fixture['source_origin']), source_peak=np.array(np.max(abs(truth))))
                else:
                    reference = fixture['reference']
                    source.update(raw=fixture['raw'], source_native=fixture['source_native'], first=np.array(fixture['first']))
                outputs['reference'] = reference
                source['reference'] = reference
                np.savez_compressed(out/'source.npz', **source)
                measured, observed = observe(outputs)
                np.savez_compressed(out/'sound.npz', **observed)
                comparisons = compare_all(outputs, measured, [('C1_16', 'reference'), ('C1_32', 'reference'), ('C1_16', 'C1_32')])
                wave = comparisons['C1_16_vs_reference']['wave_NRMSE']
                if label == 'pure_stopband':
                    peak = float(np.max(abs(outputs['C1_16']))/float(source['source_peak']))
                    passed = peak <= 1e-5
                elif label == 'path_zero':
                    peak = 0.; passed = not np.count_nonzero(outputs['C1_16']) and not np.count_nonzero(outputs['C1_32'])
                else:
                    peak = None; passed = wave is not None and wave < (.005 if fixture['family'] == 'recorded' else .003)
                if label == 'path_mono':
                    assert np.array_equal(outputs['C1_16'][:, 0], outputs['C1_16'][:, 1])
                    assert np.array_equal(outputs['C1_32'][:, 0], outputs['C1_32'][:, 1])
                row = dict(label=label, family=fixture['family'], original_model=fixture['original_model'],
                    original_source=fixture.get('original_source'), spec=fixture.get('spec'),
                    native_start=start, count=count, inverse_roundtrip=roundtrip(model, q), comparisons=comparisons,
                    pure_stop_peak_relative=peak, known_wave_qualified=bool(passed),
                    native16_32_all_six_bands_converged=convergence(comparisons['C1_16_vs_C1_32'], gates),
                    files={name:sha(out/name) for name in ('source.npz', 'up16.npz', 'up32.npz', 'sound.npz')})
                r['cases'].append(row); save(a.out/'report.json', r)
                print('BRIDGE_KNOWN', label, 'wave', wave, 'qualified', passed, 'allBandConvergence', row['native16_32_all_six_bands_converged'], flush=True)
            assert len(r['cases']) == 22
            r['all_known_qualified'] = all(c['known_wave_qualified'] for c in r['cases'])
        else:
            assert a.known_study is not None and a.known_audit is not None
            known = read(a.known_study/'report.json'); ka = read(a.known_audit/'report.json')
            assert known['all_known_qualified'] and ka['all_known_qualified'] and ka['verification_passed']
            assert ka['producer_sha256'] == sha(a.known_study/'report.json') and known['sources'] == r['sources']
            d = arrays(read(prior/'real1/capture.npz', old['capture_sha256']))
            tail = read(a.workspace/'references/analysis/locked_source_tail_v1/real1/report.json')
            native_study = Path(tail['source_study']); native_report = read(native_study/'report.json')
            z, native = identity(native_report, native_study, repo, r['inputs'])
            model = source_model(d); q = d['query']; count = len(native['raw_native_target']); start = float(native['native_start'])
            assert np.array_equal(d['old_positions'], z['source_coordinates'])
            outputs = dict(raw=native['raw_native_target'], FIR_only=native['source_FIR_only_target'])
            source = dict(model, query=q, positions=d['positions'], old_positions=d['old_positions'],
                C1_source=d['signal__C1'], PL_source=d['signal__original'],
                source_native=z['native'], source_start=z['source_start'], first=native['first'], stop=native['stop'],
                source_taps=native['source_FIR_taps'], native_start=native['native_start'], count=np.array(count))
            for kind in ('C1', 'PL'):
                for up in (16, 32):
                    name = kind+'_'+str(up)
                    rendered = render(model, source[kind+'_source'], q, start, count, up,
                        old_positions=source['old_positions'] if kind == 'PL' else None)
                    path = a.out/(name+'.npz'); np.savez_compressed(path, **rendered)
                    outputs[name] = rendered['native']
                    r['cases'].append(dict(label=name, file=path.name, sha256=sha(path)))
                    save(a.out/'report.json', r); print('BRIDGE_REAL', name, count, flush=True)
            np.savez_compressed(a.out/'source.npz', **source)
            measured, observed = observe(outputs); np.savez_compressed(a.out/'sound.npz', **observed)
            pairs = [(name, reference) for name in ('C1_16', 'C1_32', 'PL_16', 'PL_32') for reference in ('raw', 'FIR_only')]
            pairs += [('C1_16', 'C1_32'), ('PL_16', 'PL_32'), ('C1_16', 'PL_16'), ('C1_32', 'PL_32'), ('FIR_only', 'raw')]
            comparisons = compare_all(outputs, measured, pairs)
            r.update(comparisons=comparisons, native_start=start, count=count, label=old['label'],
                C1_native16_32_converged=convergence(comparisons['C1_16_vs_C1_32'], gates),
                PL_native16_32_converged=convergence(comparisons['PL_16_vs_PL_32'], gates),
                known_study=str(a.known_study), known_audit=str(a.known_audit),
                inverse_roundtrip=roundtrip(model, q), original_highest_NRMSE=old['original_highest_NRMSE'],
                files={name:sha(a.out/name) for name in ('source.npz', 'sound.npz')})
        r['result'] = 'clock_native_bridge_'+a.mode+'_measured'
        save(a.out/'report.json', r); print('BRIDGE_COMPLETE', a.mode, flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error)); save(a.out/'report.json', r); raise


if __name__ == '__main__':
    main()
