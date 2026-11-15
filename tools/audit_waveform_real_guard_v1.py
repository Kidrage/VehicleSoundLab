"""Separate complete real-case audit with a qualified locked band-root guard.

Never edits or restarts the original extraction. Keep its failed audit intact.
"""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('workspace', 'study', 'controls', 'out'):
        p.add_argument('--'+key, type=Path, required=True)
    p.add_argument('--known-check', action='store_true')
    p.add_argument('--known-audit', type=Path)
    a = p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[key] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    from waveform_real_guard_v1.complete import verify
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', cases=[], sources={}, inputs={})
    try:
        control = load(a.controls/'report.json')
        assert control['result']=='independent_locked_metric_direct_DFT_controls_verified' and control['all_qualified']
        r['inputs'][str(a.controls/'report.json')] = sha(a.controls/'report.json')
        for name, digest in control['sources'].items():
            assert sha(repo/name)==sha(a.controls/'exact_sources'/name)==digest
        if a.known_check:
            source = load(a.study/'report.json')
            oldpath = a.study.parent/'known_audit1/report.json'
            old = load(oldpath)
            assert old['all_qualified']
            r['inputs'][str(oldpath)] = sha(oldpath)
            directories = [a.study/c['label'] for c in source['cases'] if c['label']!='both_zero']
            spec_path = a.study/'report.json'
        else:
            assert a.known_audit is not None
            known = load(a.known_audit/'report.json')
            assert known['result']=='independent_waveform_file_real_known_auditor_verified'
            assert known['verification_passed'] and known['all_qualified'] and len(known['cases'])==3
            r['inputs'][str(a.known_audit/'report.json')] = sha(a.known_audit/'report.json')
            for name, digest in known['sources'].items():
                assert sha(repo/name)==sha(a.known_audit/'exact_sources'/name)==digest
            spec_path = a.study.parent/'run_spec.json'
            source = load(spec_path)
            assert len(source['declared_cases'])==6 and source['only_one_sequential_run']
            assert a.study.name in source['declared_cases']
            directories = [a.study]
            for name, digest in source['sources'].items():
                assert sha(repo/name)==sha(a.study.parent/'exact_sources'/name)==digest
            for name, digest in source['inputs'].items():
                assert sha(name)==digest
        r['inputs'][str(spec_path)] = sha(spec_path)
        names = set(source['sources']) | {
            'tools/audit_waveform_real_guard_v1.py', 'tools/check_waveform_real_guard_v1.py',
            'tools/waveform_real_guard_v1/__init__.py', 'tools/waveform_real_guard_v1/locked.py',
            'tools/waveform_real_guard_v1/complete.py', 'research/waveform_real_guard_v1_plan.json'}
        for name in sorted(names):
            dest = a.out/'exact_sources'/name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, dest)
            r['sources'][name] = sha(dest)
            if name in source['sources']:
                assert r['sources'][name]==source['sources'][name]
        save(a.out/'run_spec.json', dict(sources=r['sources'], inputs=r['inputs'],
            cases=[p.name for p in directories], new_auditor_only=True))
        for directory in directories:
            row = verify(directory)
            if a.known_check:
                earlier = next(c for c in old['cases'] if c['label']==directory.name)
                assert row['all_qualified'] and row['metrics']==earlier['metrics']
            r['cases'].append(dict(label=directory.name, **row))
            save(a.out/'report.json', r)
            print('LOCKED_GUARD_AUDIT', directory.name, 'solver', row['solver_qualified'],
                  'fidelity', row['fidelity_qualified'], flush=True)
        for name, digest in r['sources'].items():
            assert sha(repo/name)==sha(a.out/'exact_sources'/name)==digest
        r.update(result='independent_waveform_file_real_known_auditor_verified' if a.known_check
            else 'independent_waveform_file_real_verified', verification_passed=True,
            all_qualified=all(c['all_qualified'] for c in r['cases']),
            base_guard_operator_comparison_corrected=True, all_original_gates_unchanged=True,
            no_C_or_hearing_or_sustained_qualification=True)
        save(a.out/'report.json', r)
    except BaseException as error:
        r.update(result='failed', error=repr(error))
        save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
