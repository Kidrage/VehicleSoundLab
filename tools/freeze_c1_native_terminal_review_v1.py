"""Freeze actual terminal extraction/native diagnosis/publication without factor copies."""
import argparse
import os
from pathlib import Path
import sys
from research_archive_v1 import load, save, sha, freeze, verify


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', type=Path, required=True)
    a = p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'): os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    from c1_registered_source_v1.binding import execution
    repo = Path(__file__).resolve().parents[1]
    pair, execution_spec = execution(a.workspace, repo)
    assert len(execution_spec['source_closure']) == 206 and len(execution_spec['input_closure']) == 144
    claim = Path(pair['spec']['storage_claim'])
    receipt = load(claim/'execution_result.json')
    assert receipt['result'] == 'c1_registered_single_run_complete'
    assert receipt['solver_qualified'] and not receipt['fidelity_qualified']
    assert sha(claim/'run1/report.json') == receipt['case_report_sha256']
    assert sha(claim/'run1_audit/report.json') == receipt['audit_report_sha256']
    native = a.workspace/'references/analysis/c1_native_diagnostics_v1'
    review = a.workspace/'references/analysis/c1_native_review_v1'
    follow = a.workspace/'references/analysis/c1_native_followthrough_v1/run1'
    terminal = load(follow/'report.json')
    assert terminal['result'] == 'c1_native_followthrough_complete' and terminal['state'] == 'terminal'
    assert terminal['source_receipt_sha256'] == sha(claim/'execution_result.json')
    producer, audit = load(native/'real1/report.json'), load(native/'real_declared_audit1/report.json')
    assert audit['verification_passed'] and audit['producer_sha256'] == sha(native/'real1/report.json')
    assert not audit['retained_original_fsum_centering_failures']
    publication, proof = load(review/'review1/report.json'), load(review/'audit1/report.json')
    assert proof['verification_passed'] and proof['producer_sha256'] == sha(review/'review1/report.json')
    assert publication['verification_passed'] and not publication['source_fidelity_qualified']
    for name, digest in publication['files'].items(): assert sha(review/'review1'/name) == digest
    old = a.workspace/'baselines/c1_native_diagnostics_known_v1'
    verify(old)
    assert sha(old/'manifest.json') == 'eb55d671360ca1fab9bc6977c77df0079983e4b6015e9606540a93f8eab3e159'
    sources = dict(execution_spec['source_closure'])
    for report in (producer, audit, publication, proof):
        for name, digest in report['sources'].items():
            assert name not in sources or sources[name] == digest
            sources[name] = digest
    for name in ('tools/freeze_c1_native_terminal_review_v1.py', 'tools/trace_relative_phase_representation_v1.py',
        'research/C1真实提取与音色误差定位V1.md', 'research/C1原采样率保真核查V1.md',
        'research/c1_native_diagnostics_next_v1_plan.json', 'research/relative_phase_v1_feedback_20261116.json',
        'research/relative_phase_representation_review_20261116.json', 'research/system_scope_review_20261116_summary.json',
        'AGENTS.md', 'README.md', 'handoff/研究续接.md', 'handoff/算法说明.md'):
        sources[name] = sha(repo/name)
    for name, digest in sources.items(): assert sha(repo/name) == digest
    inputs = {}
    # Explicit allowlist: copy diagnostic outputs, never the D factor directory.
    for folder, prefix in ((native/'real1', 'native/real1'),
        (native/'real_declared_audit1', 'native/real_declared_audit1'), (follow, 'followthrough'),
        (a.workspace/'references/analysis/relative_phase_representation_review_20261116_failed1', 'inventory_failure')):
        for path in folder.rglob('*'):
            if path.is_file():
                assert path.suffix != '.bin'
                inputs[prefix+'/'+path.relative_to(folder).as_posix()] = path
    for subpath in ('execution_spec.json', 'run_spec.json', 'execution_result.json',
        'run1/report.json', 'run1/capture.npz', 'run1/preflight.json', 'run1/progress.json',
        'run1_audit/report.json', 'run1_audit/executed_audit.py'):
        inputs['source/'+subpath] = claim/subpath
    inputs['previous_known_archive_manifest.json'] = old/'manifest.json'
    validation = dict(result='actual_c1_terminal_native_loss_evidence_archived',
        source_solver_qualified=True, source_fidelity_qualified=False,
        eligible_for_later_source_statistics=False, original_source_receipt_sha256=sha(claim/'execution_result.json'),
        native_producer_sha256=sha(native/'real1/report.json'),
        native_audit_sha256=sha(native/'real_declared_audit1/report.json'),
        publication_sha256=sha(review/'review1/report.json'), independent_publication_audit_sha256=sha(review/'audit1/report.json'),
        known_controls=6, corruption_rejections=3, CSV_numeric_cells_checked=117,
        actual_processes_terminal=True, no_restart_refit_or_remaining_batch=True,
        factors_remain_on_D_not_copied=True, direct_continuous_OSC_not_measured=True,
        no_runtime_C_default_room_driver_owned_takes_or_hearing_change=True,
        protected_C_H=670, protected_voice_files=82, protected_F2=3,
        original_hearings_and_C_index_exact=True, execution_sources=206, execution_inputs=144,
        previous_known_archive_unchanged=True, original_failures_preserved=True,
        old_relative_phase_representation_is_read_only_inventory=True,
        PNG_visually_inspected=True, SVG_parsed=True, full_goal='ACTIVE')
    baseline = a.workspace/'baselines/c1_native_terminal_review_v1'
    info = freeze(baseline, repo, sources, review, inputs, validation)
    manifest = verify(baseline)
    assert not [row for row in manifest['files'] if row['path'].endswith('.bin')]
    save(repo/'research/c1_native_terminal_review_v1_summary.json', dict(validation, archive=str(baseline), **info))
    print('C1_NATIVE_TERMINAL_ARCHIVE', info, flush=True)


if __name__ == '__main__': main()
