"""Bind successful shared-basis evidence and both failed attempts into one archive."""
import argparse
import csv
import os
from pathlib import Path
import sys

from research_archive_v1 import freeze, load, save, sha, verify


def checked_csv(path, rows):
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with path.open(encoding='utf-8', newline='') as stream:
        printed = list(csv.DictReader(stream))
    assert len(printed) == len(rows)
    cells = 0
    for original, published in zip(rows, printed):
        for key, value in original.items():
            if isinstance(value, str):
                assert published[key] == value
            else:
                assert float(published[key]) == value
                cells += 1
    return cells


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    args = parser.parse_args()
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[key] = '2'
    sys.path.insert(0, str(args.workspace/'tools/python_deps'))
    from c1_registered_source_v1.binding import protected

    repo = Path(__file__).resolve().parents[1]
    study = args.workspace/'references/analysis/shared_basis_operator_v1'
    protected(args.workspace, repo)
    failed, producer, bad_audit, audit, bench = [
        load(study/name/'report.json')
        for name in ('known1', 'known2', 'audit2', 'support_audit2', 'bench1')
    ]
    assert failed['result'] == bad_audit['result'] == 'failed'
    assert failed['cases'] == [] and 'broadcast' in failed['error']
    assert bad_audit['active_case']['name'] == 'small_rank_deficient'
    assert producer['result'] == 'shared_discrete_basis_known_execution_completed'
    assert audit['verification_passed'] and len(audit['cases']) == 4
    assert audit['producer_sha256'] == sha(study/'known2/report.json')
    assert not audit['full_scale_operator_or_constrained_solver_or_actual_source_qualification']
    assert audit['maximum_scaled_error'] == 9.574693105866959e-16
    assert bench['result'] == 'single_complete_width_known_shared_block_benchmarked'
    assert bench['only_one_of_56_spectral_blocks_executed']
    assert bench['dot_scaled_error'] < 2e-11
    assert not audit['new_C1_source_eligible_for_statistics']

    sources = set()
    inputs = {}
    # Failed producer sources stay frozen as executed, including its old bug.
    # Current successful producer and benchmark must also match working sources.
    for label, report in (('known1', failed), ('known2', producer), ('bench1', bench)):
        for name, digest in report['sources'].items():
            assert sha(study/label/'exact_sources'/name) == digest
            if label != 'known1':
                assert sha(repo/name) == digest
                sources.add(name)
        for name, digest in report['inputs'].items():
            path = Path(name)
            assert path.drive.upper() == 'E:' and sha(path) == digest
            if not path.is_relative_to(study):
                inputs[path.relative_to(args.workspace).as_posix()] = path
    for label, name, report in (
        ('audit2', 'tools/audit_shared_basis_operator_v1.py', bad_audit),
        ('support_audit2', 'tools/audit_shared_basis_support_v1.py', audit),
    ):
        # The old failed auditor did not emit its own digest. Its exact script
        # is independently bound by the successful producer's source capture.
        digest = (producer['sources'][name] if label == 'audit2'
                  else report['auditor_sha256'])
        assert sha(study/label/'executed_audit.py') == digest
        assert sha(repo/name) == digest
        sources.add(name)

    legacy_path = next(Path(name) for name in producer['inputs']
                       if Path(name).parent.name == 'known_all_audit3')
    legacy = load(legacy_path)
    assert not legacy['verification_passed'] and len(legacy['failures']) == 19
    total_elements = total_blocks = 0
    for case, proof in zip(producer['cases'], audit['cases']):
        assert case['name'] == proof['name'] and case['compiled_blocks'] == 17
        for filename, field in (('output.npz', 'output_sha256'), ('blocks.npz', 'blocks_sha256')):
            assert sha(study/'known2'/case['name']/filename) == case[field]
        assert proof['maximum_scaled_error'] <= 2e-11
        total_elements += proof['elements_checked']
        total_blocks += proof['compiled_block_entries_checked']
    assert (total_elements, total_blocks) == (3377044, 2622720)
    assert sha(study/'bench1/probe.npz') == bench['probe_sha256']
    costs = producer['full_geometry_resources']
    assert audit['complete_geometry_support_storage_work_counts_verified']
    assert (costs['real_unknowns'], costs['full_data_rows']) == (84096, 495836)
    assert (costs['full_supported_windows'], costs['target_supported_windows']) == (56, 40)
    assert bench['block_payload_bytes'] == costs['maximum_spectral_block_bytes'] == 339904512
    assert bench['block_rows'] * bench['block_columns'] * 8 == bench['block_payload_bytes']
    assert min(row['matrix_bytes'] for row in costs['shared_spectral_blocks']) > costs['bounded_cache_bytes']

    # Publish tables directly from already independently checked reports.
    review = study/'tables1'
    review.mkdir(exist_ok=False)
    case_rows = [dict(case=c['name'], elements=c['elements_checked'],
                      compiled_entries=c['compiled_block_entries_checked'],
                      maximum_scaled_error=c['maximum_scaled_error']) for c in audit['cases']]
    cross_rows = [dict(case=c['name'], group=g, relative_difference=value)
                  for c in audit['cases']
                  for g, value in enumerate(c['cross_legacy_target_group_relative_differences'])]
    resource_keys = ('frames', 'nodes', 'orders', 'real_unknowns', 'full_data_rows',
                     'full_supported_windows', 'target_supported_windows', 'full_dense_bytes',
                     'one_channel_global_dense_bytes', 'shared_spectral_payload_bytes',
                     'shared_wave_payload_bytes', 'maximum_spectral_block_bytes',
                     'source_geometry_bytes', 'bounded_cache_bytes',
                     'estimated_authored_array_budget_bytes', 'one_forward_matrix_products',
                     'one_adjoint_matrix_products', 'spectral_column_FFTs_per_uncached_action')
    resource_rows = [dict(metric=k, value=costs[k]) for k in resource_keys]
    timing_keys = ('block_rows', 'block_columns', 'block_payload_bytes', 'compile_seconds',
                   'forward_seconds', 'adjoint_seconds', 'dot_scaled_error')
    bench_rows = ([dict(metric=k, value=bench[k]) for k in timing_keys]
                  + [dict(metric=k, value=v) for k, v in bench['process_memory'].items()])
    numeric_cells = 0
    for name, rows in (('known_cases.csv', case_rows), ('cross_legacy.csv', cross_rows),
                       ('resources.csv', resource_rows), ('single_block.csv', bench_rows)):
        numeric_cells += checked_csv(review/name, rows)
    save(review/'report.json', dict(
        result='audited_shared_basis_tables_published', numeric_cells_roundtrip_checked=numeric_cells,
        no_new_audio_or_audible_cause_claim=True,
        inputs={str(study/n/'report.json'): sha(study/n/'report.json')
                for n in ('known2', 'support_audit2', 'bench1')},
        tables={p.name: sha(p) for p in sorted(review.glob('*.csv'))}))

    sources.update(('tools/freeze_shared_basis_operator_v1.py',
                    'research/共享离散基与提取资源V1.md',
                    'research/shared_basis_operator_next_v1_plan.json',
                    'AGENTS.md', 'README.md', 'handoff/研究续接.md', 'handoff/算法说明.md'))
    assert not list(study.rglob('*.wav')) and not list(study.rglob('*.bin'))
    validation = dict(
        result='shared_discrete_basis_evidence_and_failures_archived',
        method=producer['schema'], saved_small_cases=4, elements_checked=total_elements,
        compiled_block_entries_checked=total_blocks, maximum_scaled_error=audit['maximum_scaled_error'],
        original_comparison_threshold=2e-11, original_19_failures_preserved=True,
        failed_producer_and_failed_support_audit_preserved=True,
        full_geometry_support_storage_work_counts_verified=True,
        only_one_of_56_full_width_synthetic_blocks_benchmarked=True,
        full_scale_operator_or_constrained_solver_or_actual_source_qualification=False,
        original_direct_waveform_FFT_fidelity_separate=True, new_C1_source_eligible_for_statistics=False,
        no_actual_fit_statistical_training_audio_C_or_audible_cause_claim=True,
        CSV_numeric_cells_roundtrip_checked=numeric_cells,
        protected_C_H=670, protected_voice_files=82, protected_F2_files=3,
        index_and_hearings_exact=True, no_D_or_factor_copies=True, full_goal='ACTIVE')
    root = args.workspace/'baselines/shared_basis_operator_v1'
    info = freeze(root, repo, sources, study, inputs, validation)
    verify(root)
    save(repo/'research/shared_basis_operator_v1_summary.json', dict(
        validation, archive=str(root), benchmark={k: bench[k] for k in timing_keys},
        resources={k: costs[k] for k in resource_keys}, **info))
    print('SHARED_BASIS_ARCHIVED', info, flush=True)


if __name__ == '__main__':
    main()
