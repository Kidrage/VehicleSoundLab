"""Audit one terminal new-method capture using the independently qualified oracle."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'study', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(args.workspace/'tools/python_deps'))
    from locked_source_fit_v1.complete import verify

    repo = Path(__file__).resolve().parents[1]
    args.out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, args.out/'executed_audit.py')
    report = dict(result='running', sources={}, inputs={})
    try:
        spec = load(args.study.parent/'run_spec.json')
        report['inputs'][str(args.study.parent/'run_spec.json')] = sha(args.study.parent/'run_spec.json')
        assert spec['schema'] == 'vsl.locked_source_real_spec/1' and spec['only_one_finite_case']
        assert spec['declared_cases'] == [args.study.name] and spec['block'] == 1024
        assert args.study.name != 'F3 Fifth First Early' and spec['original_first_case_excluded']
        assert spec['stop_after_terminal_case_before_later_fits']
        for name, wanted in spec['sources'].items():
            assert sha(repo/name) == sha(args.study.parent/'exact_sources'/name) == wanted
            report['sources'][name] = wanted
        for path, wanted in spec['inputs'].items():
            assert sha(path) == wanted; report['inputs'][path] = wanted
        known = load(spec['known_audit'])
        assert known['result'] == 'independent_locked_source_known_verified' and known['all_qualified']
        assert len(known['cases']) == 4
        bound = spec['sources']
        # Same complete mathematical auditor already passed three dense-QR controls.
        for name in ('complete.py', 'oracle.py'):
            relative = 'tools/locked_source_fit_v1/'+name
            original = Path(spec['known_audit']).parent.parent/'known1/exact_sources'/relative
            assert sha(original) == bound[relative]
        case = verify(args.study)
        assert case['verification_passed']
        report.update(result='independent_locked_source_real_verified', verification_passed=True,
            all_qualified=case['all_qualified'], case=case,
            all_original_gates_unchanged=True, no_C_or_sustained_or_hearing_promotion=True)
        save(args.out/'report.json', report)
        print('AUDIT_LOCKED_REAL', args.study.name, 'solver', case['solver_qualified'],
              'fidelity', case['fidelity_qualified'], flush=True)
    except BaseException as error:
        report.update(result='failed', error=repr(error)); save(args.out/'report.json', report)
        raise


if __name__ == '__main__': main()
