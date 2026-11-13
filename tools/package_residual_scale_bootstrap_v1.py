"""Publish/freeze/verify one rejected scale rule and its fixed-block evidence."""
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
sys.path[:0] = [str(args.workspace/'tools/python_deps')]
root = args.workspace/'references/analysis/residual_scale_bootstrap_v1'; final = root/'final1'
summary = repo/'research/residual_scale_bootstrap_v1_summary.json'; frozen = args.workspace/'baselines/residual_scale_bootstrap_v1'


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
    r = dict(schema='vsl.residual-scale-bootstrap-final/1', result='running', sources={}, reports={})
    try:
        import numpy as np
        from quintic_phase_v1.model import QuinticAbsoluteModel
        from orthogonal_band_v1.operator import OrthogonalBand
        from aperture_model_v1.forward import real_rows
        fit = load(root/'fit1/report.json'); audit = load(root/'audit1/report.json'); fitted = load(root/'fit1/fit.json')
        assert fit['result'] == 'known_bootstrap_rejected' and fit['controls']['passed']
        assert audit['result'] == 'all20_stage_steps_and80_fixed_block_models_independently_rebuilt'
        assert not audit['nonlinear_estimator_rerun'] and not audit['quadratic_solver_rerun']
        assert fit['QP_certified'] == fit['steps'] == 20 and not fit['original_dense_started'] and not fit['original_scale_reached']
        assert fit['fit_report_sha256'] == sha(root/'fit1/fit.json') and audit['candidate_report_sha256'] == sha(root/'fit1/report.json')
        assert len(audit['trace']) == 20 and all(row['certificate']['success'] for row in audit['trace'])
        assert len(audit['block_comparisons']) == 20 and sum(len(x['fixed_models']) for x in audit['block_comparisons']) == 80
        assert all(x['admissible'] for row in audit['block_comparisons'] for x in row['fixed_models'])
        sources = {Path(__file__), repo/'AGENTS.md', repo/'research/残差尺度与相位起步V1.md',
            repo/'handoff/研究续接.md', repo/'handoff/算法说明.md', repo/'handoff/开发留痕.md',
            repo/'research/怠速与加速完成度V1.md'}
        for name, value in (('fit1', fit), ('audit1', audit)):
            assert not value['real_audio_read'] and not value['model_exported'] and not value['runtime_changed']
            r['reports'][name] = dict(path=(root/name/'report.json').relative_to(args.workspace).as_posix(),
                sha256=sha(root/name/'report.json'), result=value['result'])
            for file, digest in value['sources'].items():
                assert sha(repo/file) == sha(root/name/'exact_sources'/file) == digest
                sources.add(repo/file)
        prior = args.workspace/'references/analysis/orthogonal_band_v1/fit1/known'
        assert fit['parent_input_sha256'] == sha(prior/'input.npz') and fit['parent_fit_sha256'] == sha(prior/'fit.json')
        old = load(prior/'fit.json'); assert old['iterations'] == 20
        inputs = np.load(root/'fit1/input.npz'); plan = load(root/'fit1/effective_plan.json')
        variant = load(repo/'research/minority_phase_v1_plan.json')
        model = QuinticAbsoluteModel(inputs['time'], plan, variant, [])
        model.original.aperture = OrthogonalBand(len(inputs['time']), plan)
        residual = model.original.prediction(inputs['initial_parameters'])-real_rows(model.original.aperture.apply(inputs['audio'][:, 0]))
        half = len(residual)//2; magnitude = np.hypot(residual[:half], residual[half:])
        weight = (1+(magnitude/plan['soft_l1_scale'])**2)**(-.5)
        increases = sum(fitted['history'][k]['stage_scale'] > fitted['history'][k-1]['stage_scale'] for k in range(1, 20))
        assert increases == 3
        blocks = []
        for row in audit['block_comparisons']:
            if row['iteration'] in (3, 7):
                blocks.append(dict(iteration=row['iteration'], full_accepted=row['full_accepted'],
                    fixed_original_relative_reductions={x['block']: x['original_reduction']/row['original_before_cost'] for x in row['fixed_models']}))
        for source in sources:
            relative = source.relative_to(repo); dest = final/'exact_sources'/relative
            dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(source, dest)
            r['sources'][relative.as_posix()] = sha(source)
        previous = args.workspace/'references/analysis/orthogonal_band_v1/final1'
        for name in ('C_files_sha256.json', 'voice_files_sha256.json'): shutil.copy2(previous/name, final/name)
        shutil.copy2(args.workspace/'AGENTS.md', final/'data_workspace_AGENTS.md')
        parents = {'orthogonal_band_v1': dict(path='baselines/orthogonal_band_v1/manifest.json',
            sha256=sha(args.workspace/'baselines/orthogonal_band_v1/manifest.json'))}
        r.update(result='observed_scale_rule_rejected_phase_envelope_block_interaction_observed',
            prior_manifests=parents, controls=fit['controls'], assessment=fit['assessment'],
            observed_initial=dict(median_complex_residual=float(np.median(magnitude)),
                median_original_radial_curvature=float(np.median(weight**3)),
                median_original_radial_to_tangential=float(np.median(weight**2))),
            original_fixed_scale_old_cost=old['final_cost'], original_fixed_scale_new_cost=fitted['final_cost'],
            normalized_residual=fitted['normalized_projection_residual'], final_stage_scale=fitted['final_stage_scale'],
            stage_scale_increases=increases, monotone_stage_scale=False,
            actual_QPs=20, actual_QPs_certified=20, accepted_steps=fitted['accepted_steps'],
            original_fixed_objective_monotone_on_accepted_steps=True, total_iterations=20, extra_initialization_iterations=0,
            fixed_block_models=80, all_fixed_block_models_originally_admissible=True, selected_fixed_block_evidence=blocks,
            fixed_block_costs_additive=False, fixed_block_models_optimized=False,
            all20_steps_independently_reconstructed=True,
            independent_geometry_maximum_relative_error=max(max(row['independent_geometry_errors'].values()) for row in audit['trace']),
            independent_wave_maximum_error=audit['independent_wave_maximum_error'], independent_loss_maximum_error=audit['independent_loss_maximum_error'],
            C_H=540, C_hashes_sha256=sha(final/'C_files_sha256.json'), voice_hashes_sha256=sha(final/'voice_files_sha256.json'),
            catalogue_sha256=sha(repo/'references/segments_v1.json'), data_memory_sha256=sha(final/'data_workspace_AGENTS.md'),
            old_fixed_control_reused_by_identity=True, old_controls_rerun=False, existing55CTests_rerun=False,
            real_audio_read=False, model_exported=False, runtime_changed=False, new_WAV=False, original_dense_started=False,
            real_shared_phase_DNA_permitted=False, vehicle_timbre_accepted=False, initialization_sole_cause_proved=False,
            idle_acceleration_complete=False, full_qualification=False, goal_complete=False,
            moving35='held_unchanged', original_A_low_listening='original_question_pending',
            F3_stopped54_56='speech_excluded_from_quantitative_and_DNA', other_reviewed_F_short_clips='usable_mild_wind_noted',
            previous_goal_turn='progress_new_orthogonal_known_control_and_matched_parent_both_fail_all40_audited',
            current_goal_turn='progress_single_observed_scale_rule_failure_all20_steps_and80_fixed_blocks_independently_rebuilt',
            next_step='Fixed rapid control: phase versus slow-envelope block updates within same total budget; explicit restricted-certificate scope. No retuning scale or accepting unoptimized block counterfactuals. Original36/all17/full33/individual14k/originalE before real sharedphaseDNA.',
            limits=fit['limits']+audit['limits'])
        current(r); save(summary, r)
    except Exception as exc:
        r.update(result='failed', error=repr(exc)); raise
    finally: save(final/'report.json', r)
    print(json.dumps(dict(result=r['result'], actual_QPs=20, fixed_block_models=80)), flush=True)
elif args.stage == 'freeze':
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=repo).strip()
    r = load(summary); current(r); assert sha(summary) == sha(final/'report.json')
    frozen.mkdir(exist_ok=False); shutil.copytree(root, frozen/'evidence')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
    subprocess.run(['git', 'archive', '--format=zip', '--output='+str(frozen/'source.zip'), commit], cwd=repo, check=True)
    files = [dict(path=x.relative_to(frozen).as_posix(), bytes=x.stat().st_size, sha256=sha(x)) for x in sorted(frozen.rglob('*')) if x.is_file()]
    save(frozen/'manifest.json', dict(schema='vsl.freeze/1', source_commit=commit, files=files, prior_manifests=r['prior_manifests'],
        known_phase_control_qualified=False, original_dense_started=False, real_audio_read=False,
        profiles_exported=0, vehicle_timbre_accepted=False, goal_complete=False))
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
