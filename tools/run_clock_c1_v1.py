"""Known-first one node-preserving C1 clock counterfactual; no new fit."""
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
    import scipy
    from clock_c1_v1.known import analytic_suite, recorded_suite
    from clock_c1_v1.geometry import from_context, evaluate, summary
    from clock_c1_v1.stereo import measure as stereo, compare as stereo_compare
    from clock_structure_v1.spectra import measure
    from locked_source_tail_v1.kernel import reference
    from locked_source_diagnostics_v1.native_identity import verify
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', mode=a.mode, inputs={}, sources={}, numpy=np.__version__, scipy=scipy.__version__)
    def bind(path, expected=None):
        path = Path(path); r['inputs'][str(path)] = sha(path)
        if expected is not None:
            assert sha(path) == expected
        return load(path) if path.suffix == '.json' else path
    def arrays(path):
        with np.load(path) as z:
            return {k:z[k] for k in z.files}
    try:
        tail = a.workspace/'references/analysis/locked_source_tail_v1'
        prior = bind(tail/('known1' if a.mode == 'known' else 'real1')/'report.json')
        proof = bind(tail/('known_audit1' if a.mode == 'known' else 'audit1')/'report.json')
        assert proof['verification_passed'] and proof['producer_sha256'] == sha(tail/('known1' if a.mode == 'known' else 'real1')/'report.json')
        names = set(prior['sources']) | {'tools/run_clock_c1_v1.py', 'tools/audit_clock_c1_v1.py',
            'research/clock_c1_v1_plan.json', 'tools/clock_structure_v1/spectra.py',
            'tools/recorded_phase_context_v1/fixtures.py', 'tools/recorded_phase_context_v1/metrics.py'}
        names.update(path.relative_to(repo).as_posix() for path in (repo/'tools/clock_c1_v1').glob('*.py'))
        for name in sorted(names):
            dest = a.out/'exact_sources'/name; dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, dest); r['sources'][name] = sha(dest)
        for name, expected in prior['sources'].items():
            assert sha(repo/name) == expected
        r.update(no_actual_clock_or_target_replacement=True, no_refit_or_runtime_C_or_hearing_promotion=True,
            original_source_fidelity_qualified=False, eligible_for_later_source_statistics=False)
        if a.mode == 'known':
            source = bind(tail/'known1/capture.npz', prior['capture_sha256'])
            z = arrays(source)
            r['analytic'] = analytic_suite(a.out, z['coefficients'], z['frequencies'], z['taps'])
            r['recorded'] = recorded_suite(a.out, a.workspace, bind)
            assert r['analytic']['all_known_qualified'] and r['recorded']['all_known_qualified']
            r['all_known_qualified'] = True
        else:
            assert a.known_study is not None and a.known_audit is not None
            known = bind(a.known_study/'report.json'); ka = bind(a.known_audit/'report.json')
            assert known['result'] == 'clock_c1_known_measured' and known['all_known_qualified']
            assert ka['result'] == 'independent_clock_c1_known_verified' and ka['verification_passed']
            assert ka['producer_sha256'] == sha(a.known_study/'report.json')
            assert known['sources'] == r['sources']
            source_study = Path(prior['source_study'])
            source = bind(source_study/'report.json')
            z, _ = verify(source, source_study, repo, r['inputs'])
            previous = arrays(bind(tail/'real1/capture.npz', prior['capture_sha256']))
            query = arrays(bind(prior['query_file']))
            cr = a.workspace/'baselines/recorded_phase_context_v1/evidence/real1'
            context_report = bind(cr/'report.json')
            context_proof = bind(cr.parent/'real_audit1/report.json')
            assert context_proof['all_qualified'] and context_proof['producer_sha256'] == sha(cr/'report.json')
            row = next(c for c in context_report['cases'] if c['label'] == prior['label'])
            context_file = bind(cr/row['file'], row['sha256']); d = arrays(context_file)
            assert np.array_equal(d['positions'], z['source_coordinates'])
            assert np.array_equal(query['filtered'], previous['filtered'])
            assert np.array_equal(query['source_coordinates'], d['positions'])
            assert np.array_equal(query['weights'], z['weights']) and np.array_equal(previous['weights'], z['weights'])
            model = from_context(d); positions = evaluate(model, d['sample_indices'])
            new_query = (positions-float(z['source_start'])-int(query['crop'][0])/48000)*48000
            old_query = (d['positions']-float(z['source_start'])-int(query['crop'][0])/48000)*48000
            assert np.array_equal(old_query, query['query'])
            print('C1_REAL_QUERY', len(new_query), flush=True)
            audio = reference(query['filtered'], new_query, 2048)
            values = dict(original=previous['signal__reference2048'], C1=audio)
            observed, observation_info = measure(values, z['weights'], float(z['amplitude']), 'original')
            observation_info['reference_is_declared_analytic_control_not_original_recorded_clock'] = False
            observation_info['reference_is_frozen_original_long_query'] = True
            sm = {k:stereo(v) for k,v in values.items()}
            saved = dict(model, query=d['sample_indices'], positions=positions, old_positions=d['positions'],
                source_query=new_query, filtered=query['filtered'], crop=query['crop'], taps=query['taps'],
                weights=z['weights'], amplitude=z['amplitude'], source_start=z['source_start'])
            saved.update(observed)
            saved.update({'signal__'+k:v for k,v in values.items()})
            for name, fields in sm.items():
                saved.update({name+'__stereo_'+k:v for k,v in fields.items()})
            np.savez_compressed(a.out/'capture.npz', **saved)
            r.update(geometry=summary(model, d['sample_indices'], positions, d['positions']),
                observations=observation_info, stereo=stereo_compare(sm['original'], sm['C1']),
                capture_sha256=sha(a.out/'capture.npz'), context_file=str(context_file), label=prior['label'],
                known_study=str(a.known_study), known_audit=str(a.known_audit),
                original_highest_NRMSE=prior['original_metrics']['target_supported_band_complex_NRMSE'][-1],
                old_long_reference_bitwise_preserved=True, only_one_new_real_query_set=True)
        r['result'] = 'clock_c1_'+a.mode+'_measured'
        save(a.out/'report.json', r)
        print('C1_COMPLETE', a.mode, flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error)); save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
