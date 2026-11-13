"""Publish, freeze and verify the failed restricted-block known control."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True)
p.add_argument('--stage', choices=('publish', 'freeze', 'verify'), required=True)
args = p.parse_args(); repo = Path(__file__).resolve().parents[1]
root = args.workspace/'references/analysis/phase_envelope_blocks_v1'; final = root/'final1'
summary = repo/'research/phase_envelope_blocks_v1_summary.json'; frozen = args.workspace/'baselines/phase_envelope_blocks_v1'


def load(path): return json.loads(path.read_text(encoding='utf-8'))
def save(path, value): path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')
def sha(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()


def current(r):
    for name, digest in r['sources'].items(): assert sha(repo/name) == sha(final/'exact_sources'/name) == digest
    for item in r['reports'].values(): assert sha(args.workspace/item['path']) == item['sha256']
    for name in ('C_files_sha256.json', 'voice_files_sha256.json'):
        assert all(sha(repo/file) == digest for file, digest in load(final/name).items())
    assert len(load(final/'C_files_sha256.json')) == 540
    assert sha(args.workspace/'AGENTS.md') == sha(final/'data_workspace_AGENTS.md') == r['data_memory_sha256']
    assert sha(repo/'references/segments_v1.json') == sha(args.workspace/'references/segments_v1.json') == r['catalogue_sha256']
    for item in r['prior_manifests'].values(): assert sha(args.workspace/item['path']) == item['sha256']
    subprocess.run(['git', 'diff', '--exit-code', 'HEAD', '--', 'src', 'modules', 'experiments', 'voices', 'CMakeLists.txt'],
        cwd=repo, capture_output=True, check=True)


if args.stage == 'publish':
    final.mkdir(exist_ok=False)
    r = dict(schema='vsl.phase-envelope-blocks-final/1', result='running', sources={}, reports={})
    try:
        failed = load(root/'fit1/report.json'); fit = load(root/'fit2/report.json')
        audit = load(root/'audit1/report.json'); fitted = load(root/'fit2/fit.json')
        assert failed['result'] == 'failed' and fit['result'] == 'known_blocks_rejected'
        assert fit['controls']['passed'] and fit['steps'] == fit['QP_certified'] == 20
        assert fit['fit_report_sha256'] == sha(root/'fit2/fit.json')
        assert audit['result'] == 'all20_restricted_QPs_and_full_nonlinear_path_independently_rebuilt'
        assert audit['candidate_report_sha256'] == sha(root/'fit2/report.json')
        assert not audit['nonlinear_estimator_rerun'] and not audit['quadratic_solver_rerun']
        assert audit['restricted_QPs_certified'] == 20 and not fit['assessment']['passed']
        sources = {Path(__file__), repo/'AGENTS.md', repo/'research/相位与包络分块更新V1.md',
            repo/'research/phase_envelope_blocks_v1_control_review.json', repo/'handoff/研究续接.md',
            repo/'handoff/算法说明.md', repo/'handoff/开发留痕.md', repo/'research/怠速与加速完成度V1.md'}
        for name, report in (('fit1', failed), ('fit2', fit), ('audit1', audit)):
            r['reports'][name] = dict(path=(root/name/'report.json').relative_to(args.workspace).as_posix(),
                sha256=sha(root/name/'report.json'), result=report['result'])
            for file, digest in report['sources'].items():
                assert sha(root/name/'exact_sources'/file) == digest
                if name != 'fit1':
                    assert sha(repo/file) == digest
                    sources.add(repo/file)
        for path in sources:
            rel = path.relative_to(repo); dest = final/'exact_sources'/rel
            dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path, dest); r['sources'][rel.as_posix()] = sha(path)
        old = args.workspace/'references/analysis/residual_scale_bootstrap_v1/final1'
        for name in ('C_files_sha256.json', 'voice_files_sha256.json'): shutil.copy2(old/name, final/name)
        shutil.copy2(args.workspace/'AGENTS.md', final/'data_workspace_AGENTS.md')
        parents = {'residual_scale_bootstrap_v1': dict(path='baselines/residual_scale_bootstrap_v1/manifest.json',
            sha256=sha(args.workspace/'baselines/residual_scale_bootstrap_v1/manifest.json'))}
        prior = load(args.workspace/'references/analysis/residual_scale_bootstrap_v1/fit1/report.json')
        previous = load(args.workspace/'references/analysis/residual_scale_bootstrap_v1/fit1/fit.json')
        assert fit['joint_parent_report_sha256'] == sha(args.workspace/'references/analysis/residual_scale_bootstrap_v1/fit1/report.json')
        assert fit['joint_parent_fit_sha256'] == sha(args.workspace/'references/analysis/residual_scale_bootstrap_v1/fit1/fit.json')
        r.update(result='fixed_block_schedule_rejected_prediction_mismatch_remains', prior_manifests=parents,
            controls=fit['controls'], original_analytic_assertion_failure=audit['original_control_assertion_failure_preserved'],
            parent_assessment=prior['assessment'], assessment=fit['assessment'],
            old_original_cost=previous['final_cost'], new_original_cost=fitted['final_cost'],
            normalized_residual=fitted['normalized_projection_residual'], final_stage_scale=fitted['final_stage_scale'],
            original_support=fitted['observation_supported'], original_scale_reached=fitted['original_scale_reached'],
            actual_QPs=20, actual_QPs_certified=20, phase_QPs=10, angles_amplitude_QPs=10,
            accepted_phase_steps=audit['accepted_phase_steps'], accepted_angles_amplitude_steps=audit['accepted_angle_amplitude_steps'],
            certificate_scope='Only fixed-coordinate subproblems; not unrestricted full-QP optimality',
            actual_known_fits=1, controls_failed_before_known_read=True, total_iterations=20,
            inactive_coordinates_exact_zero_before_after_retraction=True, full_original_constraints_independently_checked=True,
            geometry_maximum_relative_error=audit['geometry_maximum_relative_error'],
            waveform_maximum_error=audit['waveform_maximum_error'], scalar_loss_maximum_error=audit['scalar_loss_maximum_error'],
            all20_steps_independently_reconstructed=True, C_H=540,
            C_hashes_sha256=sha(final/'C_files_sha256.json'), voice_hashes_sha256=sha(final/'voice_files_sha256.json'),
            catalogue_sha256=sha(repo/'references/segments_v1.json'), data_memory_sha256=sha(final/'data_workspace_AGENTS.md'),
            original_dense_started=False, real_audio_read=False, model_exported=False, runtime_changed=False,
            new_WAV=False, existing55CTests_rerun=False, parent_fit_reused_not_rerun=True,
            real_shared_phase_DNA_permitted=False, vehicle_timbre_accepted=False, full_qualification=False,
            idle_acceleration_complete=False, goal_complete=False, moving35='held_unchanged',
            original_A_low_listening='original_question_pending',
            F3_stopped54_56='speech_excluded_from_quantitative_and_DNA', other_reviewed_F_short_clips='usable_mild_wind_noted',
            previous_goal_turn='progress_single_scale_rule_failure_and80_fixed_block_models',
            current_goal_turn='progress_ONE_fixed_block_knownfit_andall20_restrictedcertificates_trajectory_audit',
            next_step='Inspect actual angle/amplitude subproblem nonlinear prediction mismatch and derive update safeguards; no blind schedule/scale/initial/iteration sweep. Original36/all17/full33/individual14k/originalE before real DNA.',
            limits=fit['limits']+audit['limits'])
        current(r); save(summary, r)
    except Exception as exc:
        r.update(result='failed', error=repr(exc)); raise
    finally: save(final/'report.json', r)
    print(json.dumps(dict(result=r['result'], actual_QPs=20, known_fits=1)), flush=True)
elif args.stage == 'freeze':
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=repo).strip()
    r = load(summary); current(r); assert sha(summary) == sha(final/'report.json')
    frozen.mkdir(exist_ok=False); shutil.copytree(root, frozen/'evidence')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
    subprocess.run(['git', 'archive', '--format=zip', '--output='+str(frozen/'source.zip'), commit], cwd=repo, check=True)
    files = [dict(path=x.relative_to(frozen).as_posix(), bytes=x.stat().st_size, sha256=sha(x)) for x in sorted(frozen.rglob('*')) if x.is_file()]
    save(frozen/'manifest.json', dict(schema='vsl.freeze/1', source_commit=commit, files=files,
        prior_manifests=r['prior_manifests'], known_phase_control_qualified=False, original_dense_started=False,
        real_audio_read=False, profiles_exported=0, vehicle_timbre_accepted=False, goal_complete=False))
    print(json.dumps(dict(result='frozen', files=len(files), bytes=sum(x['bytes'] for x in files), commit=commit,
        manifest_sha256=sha(frozen/'manifest.json'))), flush=True)
else:
    r = load(summary); current(r); m = load(frozen/'manifest.json')
    assert sha(summary) == sha(final/'report.json') == sha(frozen/'evidence/final1/report.json')
    for item in m['files']: assert sha(frozen/item['path']) == item['sha256'] and (frozen/item['path']).stat().st_size == item['bytes']
    with zipfile.ZipFile(frozen/'source.zip') as archive:
        assert archive.testzip() is None
        for name, digest in r['sources'].items(): assert hashlib.sha256(archive.read(name)).hexdigest() == digest
    for item in r['prior_manifests'].values():
        path = args.workspace/item['path']; assert sha(path) == item['sha256']
        for row in load(path)['files']: assert sha(path.parent/row['path']) == row['sha256']
    print(json.dumps(dict(result='all_payloads_exact_sources_parent_C_voices_verified', files=len(m['files']),
        manifest_sha256=sha(frozen/'manifest.json'))), flush=True)
