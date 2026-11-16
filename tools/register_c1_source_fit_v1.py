"""Reserve one explicit C1 source on E and D after complete known/input proofs."""
import argparse
from pathlib import Path
import os
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    a = parser.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    from c1_fit_registration_v1.proofs import prerequisites, toolchain
    from c1_fit_registration_v1.registry import reserve, claims
    from waveform_file_real_v1.resources import preflight
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', inputs={}, sources={}, no_fit_command_or_factor_allocation=True)
    try:
        proof, row, packet, before = prerequisites(a.workspace, repo, r)
        canonical = a.workspace/'references/analysis/c1_source_registry_v1/claims'
        storage = Path(before['D_storage_root'])/'c1_22k_declared_v1/claims'
        assert a.workspace.resolve() == Path('E:/VehicleSoundLab').resolve()
        assert canonical.resolve().drive.upper() == 'E:' and storage.resolve().drive.upper() == 'D:'
        assert not claims(canonical) and not claims(storage)
        probe = Path(before['D_storage_root'])/'preflight1'
        assert probe.is_dir() and not list(probe.iterdir())
        resources = preflight(probe, row['frames'], row['nodes'], row['orders'], 1024)
        original = proof.read(a.workspace/'references/analysis/c1_declared_objective_v1/resources1/report.json')
        old = original['resources']
        for name in ('major_phase_panel_arithmetic', 'resident_misc_allowance', 'main_phase_array_allowance',
            'native_temporary_allowance', 'headroom_guard', 'required_available', 'full_factor_file_bytes',
            'full_factor_disk_bytes', 'disk_output_allowance', 'disk_guard', 'required_available_disk',
            'graph_transpose_three_owned_panels_counted'):
            assert resources[name] == old[name]
        assert resources['memory_passed'] and resources['disk_passed']
        runtime = toolchain()
        names = {'tools/register_c1_source_fit_v1.py', 'tools/audit_c1_source_registration_v1.py',
                 'research/c1_fit_registration_v1_plan.json', 'tools/research_archive_v1.py'}
        names.update(p.relative_to(repo).as_posix() for p in (repo/'tools/c1_fit_registration_v1').glob('*.py'))
        for name in names:
            r['sources'][name] = sha(repo/name)
        for name, expected in r['sources'].items():
            assert sha(repo/name) == expected
            dest = a.out/'exact_sources'/name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, dest)
        payload = dict(original_label=row['label'],
            ancestry=dict(original_preparation_sha256=sha(row['original_preparation']),
                          original_context_sha256=sha(row['original_context'])),
            original_preparation=row['original_preparation'], original_context=row['original_context'],
            input_file=str(packet), input_sha256=row['sha256'],
            source_identity='vsl.c1-22k-source-preparation/1',
            measurement_identity='vsl.c1-declared-objective/1',
            input_schema=row['metadata']['schema'], input_metadata=row['metadata'],
            geometry=dict(frames=18430, target_frames=14334, orders=288, nodes=73,
                original_nodes=57, clock_observations=89, channels=2, block=1024),
            known_registration_proof=str(a.workspace/'references/analysis/c1_fit_registration_v1/known1/report.json'),
            complete_preparation_math=str(a.workspace/'references/analysis/c1_declared_objective_v1/real1/report.json'),
            original_failed_audit=str(a.workspace/'references/analysis/c1_source_adapter_v1/prepare_audit1/report.json'),
            source_closure=dict(r['sources']), input_closure=dict(r['inputs']), toolchain=runtime,
            resource_preflight=resources, exact_sources_root=str((a.out/'exact_sources').resolve()),
            legacy_namespace_snapshot=before,
            single_later_run_only=True, no_fit_launched_by_registration=True,
            no_FirstEarly_FirstMid_refit_or_automatic_remaining4=True,
            source_fidelity_NOT_evaluated=True, eligible_for_later_source_statistics=False)
        pair = reserve(payload, canonical, storage, [v['root'] for v in before['namespaces']])
        # Original namespaces and frozen contracts are checked again without
        # incorrectly applying the historical "D has no run specs" condition.
        for item in before['namespaces']:
            root = Path(item['root'])
            assert sorted(p.name for p in root.iterdir() if p.is_dir()) == item['existing_directories']
        for name, expected in r['inputs'].items():
            assert sha(name) == expected
        for name, expected in r['sources'].items():
            assert sha(repo/name) == expected
        r.update(result='c1_source_single_registration_reserved', verification_passed=True,
            pair=pair, canonical_ledger=str(canonical), storage_ledger=str(storage),
            original_namespaces_and_source_contracts_unchanged=True,
            no_actual_factor_files=not list(storage.rglob('*.bin')),
            actual_source_fidelity_NOT_evaluated=True, no_runtime_or_hearing_promotion=True,
            concrete_later_run_spec_still_required=True)
        assert r['no_actual_factor_files']
        save(a.out/'report.json', r)
        print('C1_SOURCE_REGISTERED', row['label'], pair['registration_sha256'], flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error))
        save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
