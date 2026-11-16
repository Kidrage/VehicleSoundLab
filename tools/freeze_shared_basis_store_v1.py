"""Archive bounded-store proof and full probes without duplicating the large cache."""
import argparse
import csv
import os
from pathlib import Path
import sys

from research_archive_v1 import freeze, load, save, sha, verify


def table(path, rows):
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with path.open(encoding='utf-8', newline='') as stream:
        printed = list(csv.DictReader(stream))
    assert len(printed) == len(rows)
    count = 0
    for expected, actual in zip(rows, printed):
        for key, value in expected.items():
            if isinstance(value, str):
                assert actual[key] == value
            else:
                assert float(actual[key]) == value
                count += 1
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    a = parser.parse_args()
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[key] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from c1_registered_source_v1.binding import protected
    repo = Path(__file__).resolve().parents[1]
    protected(a.workspace, repo)
    study = a.workspace/'references/analysis/shared_basis_store_v1'
    failed, source, audit, full, full_audit = [load(study/n/'report.json')
                                            for n in ('known1', 'known2', 'audit2', 'full1', 'full_audit1')]
    assert failed['result'] == 'failed' and 'Bad file descriptor' in failed['error']
    assert audit['verification_passed'] and audit['producer_sha256'] == sha(study/'known2/report.json')
    assert audit['total_compiled_entries_verified'] == 2622720 and audit['refusals_verified'] == 14
    assert audit['maximum_scaled_error'] == 0.
    assert full['result'] == 'full_synthetic_stored_shared_operator_executed'
    assert full_audit['producer_sha256'] == sha(study/'full1/report.json')
    assert full_audit['result'] == 'full_synthetic_stored_shared_operator_assessed'
    assert full_audit['all_112_payload_files_independently_hashed_and_loaded']
    assert not full_audit['full_constrained_solver_or_actual_vehicle_fidelity_qualification']
    sources, inputs = set(), {}
    for label, report in (('known1', failed), ('known2', source), ('full1', full)):
        for name, expected in report['sources'].items():
            assert sha(study/label/'exact_sources'/name) == expected
            if label != 'known1':
                assert sha(repo/name) == expected
                sources.add(name)
        for name, expected in report['inputs'].items():
            path = Path(name)
            assert path.drive.upper() == 'E:' and sha(path) == expected
            if not path.is_relative_to(study):
                inputs[path.relative_to(a.workspace).as_posix()] = path
    for label, filename, report in (('audit2', 'tools/audit_shared_basis_store_v1.py', audit),
                                     ('full_audit1', 'tools/audit_shared_basis_store_full_v1.py', full_audit)):
        assert sha(study/label/'executed_audit.py') == sha(repo/filename) == report['auditor_sha256']
        sources.add(filename)
    for case in source['cases']:
        directory = study/'known2'/case['name']
        assert sha(directory/'output.npz') == case['output_sha256']
        assert sha(directory/'store/manifest.json') == case['store']['manifest_sha256']
    assert sha(study/'full1/output.npz') == full['output_sha256']
    assert sha(study/'full1/specification.json') == full['specification_sha256']
    packet = next(Path(name) for name in full['inputs'] if Path(name).name == 'operators.npz')
    with np.load(packet, allow_pickle=False) as stream:
        original = {key: stream[key] for key in ('x', 'prior_apply', 'full_dual')}
        target_duals = [stream['target_dual_'+str(g)] for g in range(7)]
    with np.load(study/'full1/output.npz', allow_pickle=False) as stream:
        values = {key: stream[key] for key in stream.files}
    residual = values['full_forward']-values['rhs']
    objective = float(.5*residual@residual+.5*original['x']@original['prior_apply'])
    objective_error = abs(objective-full['objective'])/max(abs(objective), 1e-300)
    assert objective_error <= 2e-11
    full_dot = abs(values['full_forward']@original['full_dual']-original['x']@values['full_adjoint'])
    full_dot /= max(float(np.linalg.norm(values['full_forward'])*np.linalg.norm(original['full_dual'])), 1e-300)
    target_dot = abs(sum(values['target_'+str(g)]@target_duals[g] for g in range(7))
                     - original['x']@values['target_adjoint'])
    target_dot /= max(float(np.linalg.norm(original['x'])*np.linalg.norm(values['target_adjoint'])), 1e-300)
    assert float(full_dot) == full['full_dot_scaled_error'] < 2e-11
    assert float(target_dot) == full['target_dot_scaled_error'] < 2e-11

    # Full payload lives once outside this evidence tree. The independent full
    # audit checked every file hash and NPY content; preserve its manifest and
    # immutable receipt, not another18GB copy or any actual source-fit factors.
    cache = Path(full['store']['root'])
    assert cache.resolve().is_relative_to((a.workspace/'references/synthetic_blocks').resolve())
    assert cache.drive.upper() == 'E:'
    assert sha(cache/'manifest.json') == sha(study/'full1/cache_manifest.json') == full['store']['manifest_sha256']
    manifest = load(cache/'manifest.json')
    assert len(manifest['blocks']) == 56
    for block in manifest['blocks']:
        for key in ('ids', 'matrix'):
            row = block[key]
            assert (cache/row['file']).stat().st_size == row['bytes']
    save(study/'external_synthetic_payload.json', dict(
        root=str(cache), manifest_sha256=full['store']['manifest_sha256'],
        identity_sha256=full['store']['identity_sha256'], stored_bytes=full['store']['stored_bytes'],
        audited_all_payloads_report_sha256=sha(study/'full_audit1/report.json'),
        only_manifest_and_probes_duplicated=True, no_actual_D_factor_copy=True))

    review = study/'tables1'
    review.mkdir(exist_ok=False)
    cases = [dict(case=c['name'], compiled_entries=c['compiled_entries_verified'],
                  action_elements=c['action_elements_verified'], maximum_scaled_error=c['maximum_scaled_error'])
             for c in audit['cases']]
    rows = [dict(check=k, scaled_error=v) for k, v in full_audit['comparisons'].items()]
    timings = [dict(phase=k, seconds=v) for k, v in full['phases'].items()]
    resources = [dict(metric=k, value=v) for k, v in full['store']['preflight'].items()
                 if isinstance(v, int) and not isinstance(v, bool)]
    resources += [dict(metric=k, value=v) for k, v in full['process_memory'].items()]
    cells = sum(table(review/name, values) for name, values in (
        ('small_cases.csv', cases), ('full_checks.csv', rows),
        ('full_timings.csv', timings), ('resources.csv', resources)))
    save(review/'report.json', dict(result='audited_store_tables_published',
                                   CSV_numeric_cells_roundtrip_checked=cells,
                                   tables={p.name: sha(p) for p in review.glob('*.csv')}))
    sources.update(('tools/freeze_shared_basis_store_v1.py',
                    'research/共享块缓存与完整算子V1.md',
                    'research/shared_basis_store_next_v1_plan.json',
                    'AGENTS.md', 'README.md', 'handoff/研究续接.md', 'handoff/算法说明.md'))
    assert not list(study.rglob('*.wav')) and not list(study.rglob('*.bin'))
    validation = dict(
        result='synthetic_shared_store_and_complete_operator_evidence_archived',
        small_compiled_entries_verified=2622720, small_action_maximum_scaled_error=0.,
        malformed_identity_payload_and_cap_refusals=14,
        Windows_readonly_fsync_failure_preserved=True,
        complete_288_73_stereo_operator_verified=full_audit['verification_passed'],
        complete_operator_elements_checked=full_audit['elements_checked'],
        complete_operator_maximum_scaled_error=full_audit['maximum_scaled_error'],
        complete_operator_failed_checks=len(full_audit['failures']),
        terminal_objective_scaled_error=objective_error,
        full_dot_scaled_error=float(full_dot), target_dot_scaled_error=float(target_dot),
        original_19_failures_and_2e_11_threshold_preserved=True,
        raw_declared_FFT_and_original_17_metrics_separate=True,
        constrained_solver_or_actual_source_or_statistics_or_audio_C_qualification=False,
        new_C1_source_eligible_for_statistics=False,
        CSV_numeric_cells_roundtrip_checked=cells,
        full_synthetic_cache_external_not_duplicated=True, no_D_or_factor_copies=True,
        protected_C_H=670, protected_voice_files=82, protected_F2_files=3,
        index_and_hearings_exact=True, full_goal='ACTIVE')
    root = a.workspace/'baselines/shared_basis_store_v1'
    info = freeze(root, repo, sources, study, inputs, validation)
    verify(root)
    save(repo/'research/shared_basis_store_v1_summary.json', dict(
        validation, archive=str(root), external_cache=str(cache),
        cache_manifest_sha256=full['store']['manifest_sha256'], cache_stored_bytes=full['store']['stored_bytes'],
        phases=full['phases'], process_memory=full['process_memory'], **info))
    print('SHARED_STORE_ARCHIVED', info, flush=True)


if __name__ == '__main__':
    main()
