"""Freeze actual finite pairs, preserved control failure, full audit and cross metrics."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True)
p.add_argument('--stage', choices=('publish', 'freeze', 'verify'), required=True)
args = p.parse_args(); repo = Path(__file__).resolve().parents[1]
root = args.workspace/'references/analysis/bounded_observed_phase_v1'; final = root/'final1'
summary = repo/'research/bounded_observed_phase_v1_summary.json'; frozen = args.workspace/'baselines/bounded_observed_phase_v1'


def load(path): return json.loads(path.read_text(encoding='utf-8'))
def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')
def sha(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify_current(r):
    for name, digest in r['sources'].items(): assert sha(repo/name) == sha(final/'exact_sources'/name) == digest
    for item in r['reports'].values(): assert sha(args.workspace/item['path']) == item['sha256']
    for item in r['historical_source_versions']: assert sha(args.workspace/item['path']) == item['sha256']
    for name in ('C_files_sha256.json', 'voice_files_sha256.json'):
        assert all(sha(repo/file) == digest for file, digest in load(final/name).items())
    assert len(load(final/'C_files_sha256.json')) == 540
    assert sha(repo/'references/segments_v1.json') == sha(args.workspace/'references/segments_v1.json') == r['catalogue_sha256']
    assert sha(args.workspace/'AGENTS.md') == sha(final/'data_workspace_AGENTS.md') == r['data_memory_sha256']
    for item in r['prior_manifests'].values(): assert sha(args.workspace/item['path']) == item['sha256']
    subprocess.run(['git', 'diff', '--exit-code', 'HEAD', '--', 'src', 'modules', 'experiments', 'voices', 'CMakeLists.txt'],
        cwd=repo, capture_output=True, check=True)


if args.stage == 'publish':
    final.mkdir(exist_ok=False)
    r = dict(schema='vsl.bounded-observed-phase-final/1', result='running', sources={}, reports={}, historical_source_versions=[])
    try:
        folders = {n: root/n for n in ('pair1', 'pair2', 'audit1', 'review1', 'conclusion1')}
        values = {n: load(folder/'report.json') for n, folder in folders.items()}
        failure, pair, audit, review, conclusion = (values[n] for n in ('pair1', 'pair2', 'audit1', 'review1', 'conclusion1'))
        assert failure['result'] == 'failed' and failure['error'] == 'AssertionError()'
        assert pair['result'] == 'finite_observed_direction_compensated_not_phase_qualification' and pair['controls']['passed']
        assert pair['direction']['both_targets_feasible'] and not pair['direction_or_strength_reselected']
        assert audit['all_actual40_steps_audited'] and audit['old_failed_control_replayed'] and audit['repair_only_two_assertion_multipliers']
        assert audit['candidate_report_sha256'] == sha(root/'pair2/report.json') and audit['failure_report_sha256'] == sha(root/'pair1/report.json')
        assert all(row['feasible'] and row['fit']['every_subproblem_certified'] and row['fit']['iterations'] == 20 for row in pair['cases'])
        assert conclusion['result'] == 'fixed_observed_direction_visible_after_bounded_compensation_not_original_error_explanation'
        sources = {Path(__file__), repo/'AGENTS.md', repo/'research/观测弱方向有限补偿V1.md',
            repo/'research/bounded_observed_phase_v1_plan.json', repo/'research/bounded_observed_phase_v1_control_repair.json',
            repo/'research/bounded_observed_phase_v1_cross_plan.json', repo/'handoff/研究续接.md', repo/'handoff/算法说明.md',
            repo/'handoff/开发留痕.md', repo/'research/怠速与加速完成度V1.md'}
        old_checks = 'tools/bounded_observed_phase_v1/checks.py'
        for name, value in values.items():
            assert not value['real_audio_read'] and not value['model_exported'] and not value['runtime_changed']
            r['reports'][name] = dict(path=(folders[name]/'report.json').relative_to(args.workspace).as_posix(),
                sha256=sha(folders[name]/'report.json'), result=value['result'])
            for file, digest in value['sources'].items():
                assert sha(folders[name]/'exact_sources'/file) == digest
                if sha(repo/file) != digest:
                    assert name == 'pair1' and file == old_checks
                    assert audit['historical_source_versions'][file]['pair1_sha256'] == digest
                    r['historical_source_versions'].append(dict(path=(folders[name]/'exact_sources'/file).relative_to(args.workspace).as_posix(),
                        sha256=digest, current_sha256=sha(repo/file), reason='Known-control two-assertion correction; original failed bytes retained and replayed'))
                sources.add(repo/file)
        assert len(r['historical_source_versions']) == 1
        for name, digest in review['reports_sha256'].items(): assert sha(root/name/'report.json') == digest
        for name, digest in conclusion['reports_sha256'].items(): assert sha(root/name/'report.json') == digest
        figure = root/'review1/bounded_observed_phase.png'; assert sha(figure) == review['plot_sha256']
        assert sha(root/'pair2/direction.npz') == pair['arrays_sha256']
        for source in sources:
            relative = source.relative_to(repo); target = final/'exact_sources'/relative
            target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(source, target)
            r['sources'][relative.as_posix()] = sha(source)
        previous = args.workspace/'references/analysis/phase_score_budget_v1/final1'
        for name in ('C_files_sha256.json', 'voice_files_sha256.json'): shutil.copy2(previous/name, final/name)
        shutil.copy2(args.workspace/'AGENTS.md', final/'data_workspace_AGENTS.md'); shutil.copy2(figure, final/figure.name)
        parents = {name: dict(path='baselines/'+name+'/manifest.json', sha256=sha(args.workspace/'baselines'/name/'manifest.json'))
            for name in ('phase_score_budget_v1', 'joint_nuisance_pair_v1')}
        r.update(result='one_observed_finite_direction_visible_under_original_bounds_NOT_original_phase_recovery',
            real_audio_read=False, prior_manifests=parents, catalogue_sha256=sha(repo/'references/segments_v1.json'),
            data_memory_sha256=sha(final/'data_workspace_AGENTS.md'), direction=pair['direction'], controls=pair['controls'],
            old_failed_control_replayed=True, only_two_control_assertions_changed=True,
            reused_old_joint_controls_and_audit=True, old_joint_controls_rerun=False,
            actual_nuisance_fit_steps=40, actual_QPs_certified=40, all_actual40_steps_independently_audited=True,
            finite_case_summaries=conclusion['fixed_case_summaries'], original_bound_activity=conclusion['original_bound_activity'],
            same_metric_cost_ratios=conclusion['same_metric_cost_ratios'], fixed_three_model_cross_evaluations=review['comparisons'],
            scalar_waveform_maximum_errors=review['scalar_waveform_maximum_errors'], scalar_phase_curve_maximum_error=audit['scalar_phase_curve_maximum_error'],
            global_nuisance_minimum_proved=False, original_phase_error_cause_proved=False,
            C_H=540, C_hashes_sha256=sha(final/'C_files_sha256.json'), voice_hashes_sha256=sha(final/'voice_files_sha256.json'),
            figures_visually_checked=True, existing55CTests_rerun=False, model_exported=False, runtime_changed=False,
            high_frequency_recovered=False, RPM_inferred=False, vehicle_timbre_accepted=False,
            real_shared_phase_DNA_permitted=False, idle_acceleration_complete=False, full_qualification=False, goal_complete=False,
            moving35='held_unchanged', original_A_low_listening='original_question_pending',
            previous_goal_turn='progress_unrestricted_profile_failure_allfive_rank_stages_audited_frozen_pushed',
            current_goal_turn='progress_one_observed_finite_direction_sign2_all40bounded_steps_audited_original_observation_cross_evaluated',
            next_step=conclusion['next_step']+' Originalfailed36/all17/full33/individual14k/originalE remain before real DNA; no edge trimming.',
            limits=pair['limits']+audit['limits']+review['limits']+conclusion['limits'])
        verify_current(r); save(summary, r)
    except Exception as exc:
        r.update(result='failed', error=repr(exc)); raise
    finally: save(final/'report.json', r)
    print(json.dumps(dict(result=r['result'], actual_steps=r['actual_nuisance_fit_steps'], cases=r['finite_case_summaries'])), flush=True)
elif args.stage == 'freeze':
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=repo).strip()
    r = load(summary); verify_current(r); assert sha(summary) == sha(final/'report.json')
    frozen.mkdir(exist_ok=False); shutil.copytree(root, frozen/'evidence')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
    subprocess.run(['git', 'archive', '--format=zip', '--output='+str(frozen/'source.zip'), commit], cwd=repo, check=True)
    files = [dict(path=x.relative_to(frozen).as_posix(), bytes=x.stat().st_size, sha256=sha(x))
        for x in sorted(frozen.rglob('*')) if x.is_file()]
    save(frozen/'manifest.json', dict(schema='vsl.freeze/1', source_commit=commit, files=files,
        prior_manifests=r['prior_manifests'], real_audio_read=False, profiles_exported=0,
        original_dense_control_qualified=False, vehicle_timbre_accepted=False, goal_complete=False))
    print(json.dumps(dict(result='frozen', files=len(files), bytes=sum(x['bytes'] for x in files), commit=commit,
        manifest_sha256=sha(frozen/'manifest.json'))), flush=True)
else:
    r = load(summary); verify_current(r); m = load(frozen/'manifest.json')
    assert sha(summary) == sha(final/'report.json') == sha(frozen/'evidence/final1/report.json')
    for item in m['files']:
        assert sha(frozen/item['path']) == item['sha256'] and (frozen/item['path']).stat().st_size == item['bytes']
    with zipfile.ZipFile(frozen/'source.zip') as archive:
        assert archive.testzip() is None
        for name, digest in r['sources'].items(): assert hashlib.sha256(archive.read(name)).hexdigest() == digest
    for item in r['prior_manifests'].values():
        path = args.workspace/item['path']; assert sha(path) == item['sha256']
        for row in load(path)['files']: assert sha(path.parent/row['path']) == row['sha256']
    print(json.dumps(dict(result='all_frozen_payloads_versions_sources_parents_C_voices_verified', files=len(m['files']),
        manifest_sha256=sha(frozen/'manifest.json'))), flush=True)
