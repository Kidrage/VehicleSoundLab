"""Freeze the failed unrestricted profile and independently audited rank evidence."""
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
root = args.workspace/'references/analysis/phase_score_budget_v1'; final = root/'final1'
summary = repo/'research/phase_score_budget_v1_summary.json'; frozen = args.workspace/'baselines/phase_score_budget_v1'


def load(path): return json.loads(path.read_text(encoding='utf-8'))
def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')
def sha(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify_current(r):
    for file, digest in r['sources'].items():
        assert sha(repo/file) == sha(final/'exact_sources'/file) == digest
    for item in r['reports'].values():
        assert sha(args.workspace/item['path']) == item['sha256']
    for name in ('C_files_sha256.json', 'voice_files_sha256.json'):
        assert all(sha(repo/file) == digest for file, digest in load(final/name).items())
    assert len(load(final/'C_files_sha256.json')) == 540
    assert sha(repo/'references/segments_v1.json') == sha(args.workspace/'references/segments_v1.json') == r['catalogue_sha256']
    assert sha(args.workspace/'AGENTS.md') == sha(final/'data_workspace_AGENTS.md') == r['data_memory_sha256']
    for item in r['prior_manifests'].values():
        assert sha(args.workspace/item['path']) == item['sha256']
    subprocess.run(['git', 'diff', '--exit-code', 'HEAD', '--', 'src', 'modules', 'experiments', 'voices', 'CMakeLists.txt'],
        cwd=repo, capture_output=True, check=True)


if args.stage == 'publish':
    final.mkdir(exist_ok=False); r = dict(schema='vsl.phase-score-budget-final/1', result='running', sources={}, reports={})
    try:
        folders = {n: root/n for n in ('diagnosis1', 'rank1', 'audit1', 'review1')}
        values = {n: load(folder/'report.json') for n, folder in folders.items()}
        failed, rank, audit, review = (values[n] for n in ('diagnosis1', 'rank1', 'audit1', 'review1'))
        assert failed['result'] == 'failed' and failed['controls']['passed']
        assert audit['result'] == 'original_failure_and_allfive_rank_stages_independently_reproduced'
        assert audit['original_failure_replayed'] == failed['error'] and audit['original_known_controls_replayed']
        assert rank['result'] == 'rank_loss_localized_without_phase_response_or_model_change' and rank['controls']['passed']
        assert rank['previous_failure_sha256'] == audit['diagnosis_report_sha256'] == sha(root/'diagnosis1/report.json')
        assert audit['rank_report_sha256'] == sha(root/'rank1/report.json')
        assert not rank['local_response_calculated'] and not audit['phase_response_calculated']
        assert len(rank['stages']) == len(audit['stages']) == 5
        sources = {Path(__file__), repo/'AGENTS.md', repo/'research/相位归因与数值秩V1.md',
            repo/'research/phase_score_budget_v1_plan.json', repo/'research/phase_score_budget_v1_rank_plan.json',
            repo/'handoff/研究续接.md', repo/'handoff/算法说明.md', repo/'handoff/开发留痕.md', repo/'research/怠速与加速完成度V1.md'}
        for name, value in values.items():
            assert not value['real_audio_read'] and not value['model_exported'] and not value['runtime_changed']
            r['reports'][name] = dict(path=(folders[name]/'report.json').relative_to(args.workspace).as_posix(),
                sha256=sha(folders[name]/'report.json'), result=value['result'])
            for file, digest in value['sources'].items():
                assert sha(repo/file) == sha(folders[name]/'exact_sources'/file) == digest; sources.add(repo/file)
        for name, digest in review['reports_sha256'].items(): assert sha(root/name/'report.json') == digest
        figure = root/'review1/phase_score_rank.png'; assert sha(figure) == review['plot_sha256']
        assert sha(root/'rank1/rank.npz') == rank['arrays_sha256']
        for source in sources:
            relative = source.relative_to(repo); target = final/'exact_sources'/relative
            target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(source, target)
            r['sources'][relative.as_posix()] = sha(source)
        previous = args.workspace/'references/analysis/complex_radial_v1/final1'
        for name in ('C_files_sha256.json', 'voice_files_sha256.json'): shutil.copy2(previous/name, final/name)
        shutil.copy2(args.workspace/'AGENTS.md', final/'data_workspace_AGENTS.md'); shutil.copy2(figure, final/figure.name)
        parents = {name: dict(path='baselines/'+name+'/manifest.json', sha256=sha(args.workspace/'baselines'/name/'manifest.json'))
            for name in ('complex_radial_v1', 'correlated_observation_v1')}
        r.update(result='unrestricted_phase_profile_REJECTED_rank_loss_independently_localized_no_response',
            real_audio_read=False, prior_manifests=parents, catalogue_sha256=sha(repo/'references/segments_v1.json'),
            data_memory_sha256=sha(final/'data_workspace_AGENTS.md'),
            original_failure=failed['error'], original_controls=failed['controls'], rank_controls=rank['controls'],
            supplemental_fixed_rotation_control=review['supplemental_fixed_rotation_rank_control'],
            numerical_rank_stages=rank['stages'], independent_rank_audit=audit['stages'],
            scalar_trig_observed_maximum_errors=audit['scalar_trig_observed_maximum_errors'],
            spectral_Gram_mass_checks=review['spectral_Gram_mass_checks'],
            original_rank_cutoff_unchanged=True, phase_response_calculated=False,
            nuisance_noise_omission_causal_attribution=False, physical_nonidentifiability_proved=False,
            C_H=540, C_hashes_sha256=sha(final/'C_files_sha256.json'), voice_hashes_sha256=sha(final/'voice_files_sha256.json'),
            figures_visually_checked=True, existing55CTests_rerun=False, model_exported=False, runtime_changed=False,
            high_frequency_recovered=False, RPM_inferred=False, vehicle_timbre_accepted=False,
            real_shared_phase_DNA_permitted=False, idle_acceleration_complete=False, full_qualification=False, goal_complete=False,
            moving35='held_unchanged', original_A_low_listening='original_question_pending',
            previous_goal_turn='progress_radial_coordinate_repair_failed_original20step_fit_independent_audit_frozen_pushed',
            current_goal_turn='progress_fullrank_profile_failure_original_control_and_allfive_rank_stages_independently_audited',
            next_step='Observed-only finite feasible phase perturbations with original bounded nuisance controls and nonlinear objective. '
                'No unrestricted pseudoinverse or rank/bound/strength/degree/window/iteration sweeps. '
                'Originalfailed36/all17/full33/individual14k/originalE required before real sharedphaseDNA; F2g(T) is not clock.',
            limits=rank['limits']+audit['limits']+review['limits'])
        verify_current(r); save(summary, r)
    except Exception as exc:
        r.update(result='failed', error=repr(exc)); raise
    finally: save(final/'report.json', r)
    print(json.dumps(dict(result=r['result'], ranks=[s['nuisance_rank'] for s in rank['stages']])), flush=True)
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
        phase_response_calculated=False, vehicle_timbre_accepted=False, goal_complete=False))
    print(json.dumps(dict(result='frozen', files=len(files), bytes=sum(x['bytes'] for x in files),
        commit=commit, manifest_sha256=sha(frozen/'manifest.json'))), flush=True)
else:
    r = load(summary); verify_current(r); m = load(frozen/'manifest.json')
    assert sha(summary) == sha(final/'report.json') == sha(frozen/'evidence/final1/report.json')
    for item in m['files']:
        assert sha(frozen/item['path']) == item['sha256'] and (frozen/item['path']).stat().st_size == item['bytes']
    with zipfile.ZipFile(frozen/'source.zip') as archive:
        assert archive.testzip() is None
        for file, digest in r['sources'].items(): assert hashlib.sha256(archive.read(file)).hexdigest() == digest
    for item in m['prior_manifests'].values():
        path = args.workspace/item['path']; assert sha(path) == item['sha256']
        for row in load(path)['files']: assert sha(path.parent/row['path']) == row['sha256']
    print(json.dumps(dict(result='all_frozen_payloads_sources_parents_C_voices_verified', files=len(m['files']),
        manifest_sha256=sha(frozen/'manifest.json'))), flush=True)
