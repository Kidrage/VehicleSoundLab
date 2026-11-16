"""Bind one later extraction to its existing paired claim and known proof."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    from c1_registered_source_v1.binding import registration
    from c1_fit_registration_v1.registry import encoded, exclusive, ledger_lock
    from waveform_file_real_v1.resources import preflight
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', sources={}, inputs={}, no_launch_or_fit_by_registration=True)
    def read(path):
        r['inputs'][str(path)] = sha(path)
        return load(path)
    try:
        pair = registration(a.workspace, repo)
        original = pair['spec']
        e, d = Path(original['canonical_claim']), Path(original['storage_claim'])
        known_path = a.workspace/'references/analysis/c1_registered_source_v1/known1/report.json'
        known = read(known_path)
        assert known['verification_passed'] and known['all_qualified']
        assert (known['full_terminal_cases'], known['exact_zero_cases'], known['corruptions_rejected']) == (3, 1, 6)
        launch_path = a.workspace/'references/analysis/c1_registered_source_v1/launch_known1/report.json'
        launch = read(launch_path)
        assert launch['verification_passed'] and (launch['successes'], launch['rejected']) == (1, 6)
        r['inputs'].update(original['input_closure'])
        for item in (known, launch):
            for name, expected in item['sources'].items():
                assert sha(repo/name) == expected
            for name, expected in item.get('inputs', {}).items():
                assert sha(name) == expected
                r['inputs'][name] = expected
        for name, expected in known['known_factor_files_sha256'].items():
            assert sha(name) == expected
        for root in (e, d):
            for filename in ('run_spec.json', 'pair_receipt.json'):
                r['inputs'][str(root/filename)] = sha(root/filename)
        names = set(original['source_closure']) | set(known['sources']) | set(launch['sources']) | {
            'tools/register_c1_source_execution_v1.py', 'tools/run_c1_registered_source_v1.py',
            'tools/audit_c1_registered_source_v1.py', 'research/c1_registered_source_v1_plan.json'}
        names.update(p.relative_to(repo).as_posix() for p in (repo/'tools/c1_registered_source_v1').glob('*.py'))
        for name in sorted(names):
            dest = a.out/'exact_sources'/name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, dest)
            r['sources'][name] = sha(dest)
        resources = preflight(d, 18430, 73, 288, 1024)
        assert resources['memory_passed'] and resources['disk_passed']
        expected = original['resource_preflight']
        for name in ('major_phase_panel_arithmetic', 'resident_misc_allowance', 'required_available',
            'native_temporary_allowance', 'headroom_guard', 'full_factor_file_bytes',
            'required_available_disk', 'disk_guard', 'disk_output_allowance'):
            assert resources[name] == expected[name]
        spec = dict(schema='vsl.c1-registered-source-execution/1',
            registration_sha256=pair['registration_sha256'], source_identity=original['source_identity'],
            measurement_identity=original['measurement_identity'], only_label=original['original_label'],
            geometry=original['geometry'], block=1024, output=str(d/'run1'),
            input_file=original['input_file'], input_sha256=original['input_sha256'],
            terminal_known_audit=str(known_path), launch_known_audit=str(launch_path),
            source_closure=r['sources'], input_closure=r['inputs'], resource_preflight=resources,
            exact_sources_root=str((a.out/'exact_sources').resolve()),
            one_actual_run_only=True, no_restart_or_automatic_remaining4=True,
            no_source_fidelity_or_sustained_or_C_or_hearing_promotion=True)
        with ledger_lock(e.parent):
            assert all(not (root/filename).exists() for root in (e, d)
                       for filename in ('execution_spec.json', 'launch_intent.json'))
            assert not (d/'run1').exists()
            for root in (e, d):
                exclusive(root/'execution_spec.json', encoded(spec))
        assert (e/'execution_spec.json').read_bytes() == (d/'execution_spec.json').read_bytes()
        r.update(result='c1_single_execution_registered', verification_passed=True,
            execution_spec_sha256=sha(e/'execution_spec.json'),
            canonical_execution=str(e/'execution_spec.json'), storage_execution=str(d/'execution_spec.json'),
            output=spec['output'], full_known_terminal_audit_passed=True,
            actual_launch_NOT_started=True, original_registration_unchanged=True)
        save(a.out/'report.json', r)
        print('C1_EXECUTION_REGISTERED', r['execution_spec_sha256'], len(r['sources']), len(r['inputs']), flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error))
        save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
