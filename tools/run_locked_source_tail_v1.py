"""Known-first weak-tail diagnostics, keeping the fitted source and clock locked."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('workspace', 'source-study', 'source-audit', 'out'):
        p.add_argument('--'+key, type=Path, required=True)
    p.add_argument('--mode', choices=('known', 'real'), required=True)
    p.add_argument('--known-study', type=Path)
    p.add_argument('--known-audit', type=Path)
    a = p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[key] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from locked_source_diagnostics_v1.native_identity import verify
    from locked_source_tail_v1.kernel import reference
    from locked_source_tail_v1.known import qualify
    from locked_source_tail_v1.measure import measure
    from locked_source_error_v1.assessment import virtual_split
    from locked_source_guard_v1.measurement import declared, compare
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', mode=a.mode, sources={}, inputs={})
    try:
        source = load(a.source_study/'report.json')
        audit = load(a.source_audit/'report.json')
        assert source['result'] == 'locked_source_native_case_measured'
        assert audit['result'] == 'independent_locked_source_native_verified' and audit['verification_passed']
        assert audit['producer_sha256'] == sha(a.source_study/'report.json')
        names = set(source['sources']) | {'tools/run_locked_source_tail_v1.py',
            'tools/audit_locked_source_tail_v1.py', 'tools/research_archive_v1.py',
            'tools/locked_source_error_v1/assessment.py', 'tools/locked_source_guard_v1/measurement.py',
            'research/locked_source_tail_v1_plan.json'}
        names.update(path.relative_to(repo).as_posix() for path in (repo/'tools/locked_source_tail_v1').glob('*.py'))
        for name in sorted(names):
            dest = a.out/'exact_sources'/name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, dest)
            r['sources'][name] = sha(dest)
        for path in (a.source_study/'report.json', a.source_audit/'report.json'):
            r['inputs'][str(path)] = sha(path)
        z, _ = verify(source, a.source_study, repo, r['inputs'])
        query_file = Path(source['new_method_preparation']['source_query_file'])
        with np.load(query_file) as f:
            q = {key: f[key] for key in f.files}
        assert np.array_equal(q['sinc128'], z['audio'])
        assert np.array_equal(q['source_coordinates'], z['source_coordinates'])
        r.update(source_study=str(a.source_study), source_audit=str(a.source_audit),
            query_file=str(query_file), label=source['label'], source=source['source'],
            source_solver_qualified=source['source_solver_qualified'],
            source_fidelity_qualified=source['source_fidelity_qualified'],
            eligible_for_later_source_statistics=source['eligible_for_later_source_statistics'],
            diagnostic_radii=[512, 1024, 2048], diagnostic_beta=20.,
            locked_original_radius=128, locked_original_beta=12.,
            actual_clock_and_original_weights_amplitude_unchanged=True,
            new_reference_not_certified_ideal_or_replacement_target=True,
            affine_clock_not_replacement=True, no_refit_or_source_C_or_hearing_promotion=True)
        if a.mode == 'known':
            values, arrays, qualification = qualify(q['query'], q['source_coordinates'],
                float(z['source_start']), q['crop'], q['taps'], len(z['native']))
            r['qualification'] = qualification
        else:
            assert a.known_study is not None and a.known_audit is not None
            known, ka = load(a.known_study/'report.json'), load(a.known_audit/'report.json')
            assert known['result'] == 'locked_source_tail_known_measured' and known['qualification']['all_qualified']
            assert ka['result'] == 'independent_locked_source_tail_known_verified' and ka['verification_passed']
            assert ka['producer_sha256'] == sha(a.known_study/'report.json')
            assert ka['query_file_sha256'] == sha(query_file)
            for name, expected in known['sources'].items():
                assert sha(repo/name) == sha(a.known_study/'exact_sources'/name) == expected
            for path in (a.known_study/'report.json', a.known_audit/'report.json'):
                r['inputs'][str(path)] = sha(path)
            r.update(known_study=str(a.known_study), known_audit=str(a.known_audit))
            values = dict(legacy=q['legacy'], nominal64=q['sinc64'], nominal128=q['sinc128'],
                nominal256=q['sinc256'], saved_fit=z['wave'])
            arrays = dict(filtered=q['filtered'], query=q['query'], coordinates=q['source_coordinates'],
                          crop=q['crop'], taps=q['taps'])
            for radius in (512, 1024, 2048):
                values['reference'+str(radius)] = reference(q['filtered'], q['query'], radius)
                print('REAL_REFERENCE_READY', radius, flush=True)
            original = load(Path(source['paths']['case'])/'report.json')['metrics']
            metrics = declared(z['audio'], z['wave'], float(z['amplitude']), z['weights'])
            comparison = compare(metrics, original, enforce=True)
            original_arrays, original_split = virtual_split(z['target'], z['wave'][2048:-2048],
                z['weights'], float(z['amplitude']), z['orders'])
            arrays.update(original_arrays)
            r.update(original_metrics=metrics, original_metrics_comparison=comparison,
                     original_virtual_split=original_split,
                     fit_vs_diagnostic_references_is_counterfactual_not_admission=True)
        observation_arrays, info = measure(values, z['weights'], float(z['amplitude']))
        arrays.update(observation_arrays)
        arrays.update({'signal__'+name: value for name, value in values.items()})
        arrays.update(weights=z['weights'], amplitude=z['amplitude'], source_start=z['source_start'])
        np.savez_compressed(a.out/'capture.npz', **arrays)
        r.update(result='locked_source_tail_'+a.mode+'_measured', observations=info,
                 capture_sha256=sha(a.out/'capture.npz'), frames=len(q['query']))
        save(a.out/'report.json', r)
        print('TAIL_DIAGNOSTIC_COMPLETE', a.mode, r['capture_sha256'], flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error))
        save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
