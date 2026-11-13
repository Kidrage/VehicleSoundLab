"""Publish, freeze and verify rejected known-control observation research."""
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
root = args.workspace/'references/analysis/orthogonal_band_v1'; final = root/'final1'
summary = repo/'research/orthogonal_band_v1_summary.json'; frozen = args.workspace/'baselines/orthogonal_band_v1'


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
    r = dict(schema='vsl.orthogonal-band-final/1', result='running', sources={}, reports={})
    try:
        values = {name: load(root/name/'report.json') for name in ('fit1', 'baseline1', 'audit1')}
        candidate, baseline, audit = (values[name] for name in ('fit1', 'baseline1', 'audit1'))
        assert candidate['result'] == 'known_rapid_control_rejected_dense_not_started' and candidate['controls']['passed']
        assert baseline['result'] == 'matched_parent_control_rejected'
        assert audit['result'] == 'both_known_controls_rejected_all40_steps_independently_rebuilt'
        assert not candidate['dense_started'] and not baseline['dense_started'] and not audit['original_dense_started']
        assert candidate['known']['QP_certified'] == baseline['QP_certified'] == 20
        assert all(row['certified_QPs'] == row['steps'] == 20 and not row['original_phase_gate_passed'] for row in audit['cases'])
        assert baseline['parent_report_sha256'] == sha(root/'fit1/report.json')
        for name, digest in audit['reports_sha256'].items(): assert sha(root/name/'report.json') == digest
        sources = {Path(__file__), repo/'AGENTS.md', repo/'research/正交频带与快速初值V1.md',
            repo/'handoff/研究续接.md', repo/'handoff/算法说明.md', repo/'handoff/开发留痕.md',
            repo/'research/怠速与加速完成度V1.md'}
        for name, value in values.items():
            assert not value['real_audio_read'] and not value['model_exported'] and not value['runtime_changed']
            r['reports'][name] = dict(path=(root/name/'report.json').relative_to(args.workspace).as_posix(),
                sha256=sha(root/name/'report.json'), result=value['result'])
            for file, digest in value['sources'].items():
                assert sha(repo/file) == sha(root/name/'exact_sources'/file) == digest
                sources.add(repo/file)
        assert not audit['nonlinear_estimator_rerun'] and not audit['quadratic_solver_rerun']
        figure = root/'audit1/known_phase.png'; assert sha(figure) == audit['plot_sha256']
        assert candidate['known']['fit_report_sha256'] == sha(root/'fit1/known/fit.json')
        assert baseline['fit_report_sha256'] == sha(root/'baseline1/fit.json')
        for source in sources:
            relative = source.relative_to(repo); dest = final/'exact_sources'/relative
            dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(source, dest)
            r['sources'][relative.as_posix()] = sha(source)
        previous = args.workspace/'references/analysis/observed_score_overlap_v1/final1'
        for name in ('C_files_sha256.json', 'voice_files_sha256.json'): shutil.copy2(previous/name, final/name)
        shutil.copy2(args.workspace/'AGENTS.md', final/'data_workspace_AGENTS.md'); shutil.copy2(figure, final/figure.name)
        parents = {name: dict(path='baselines/'+name+'/manifest.json',
            sha256=sha(args.workspace/'baselines'/name/'manifest.json'))
            for name in ('observed_score_overlap_v1', 'complex_radial_v1')}
        case_summaries = [{k: v for k, v in row.items() if k != 'trace'} for row in audit['cases']]
        geometry_error = max(max(step['independent_geometry_errors'].values()) for row in audit['cases'] for step in row['trace'])
        r.update(result='orthogonal_observation_and_matched_parent_both_fail_fresh_rapid_control',
            prior_manifests=parents, controls=candidate['controls'], known_results=case_summaries,
            numeric_libraries=candidate['numeric_libraries'], actual_QPs=40, actual_QPs_certified=40,
            all40_steps_independently_reconstructed=True, independent_geometry_maximum_relative_error=geometry_error,
            independent_complex_source_maximum_error=audit['independent_complex_source_maximum_error'],
            observed_initial_LS_gradient_maximum=audit['initial_observed_LS_gradient_maximum'],
            exact_same_input_and_physical_initial=audit['exact_same_input_and_physical_initial'],
            candidate_and_baseline_original_failures_retained=True, original_dense_started=False,
            existing_analytic_QP_controls_reused=True, old_controls_rerun=False, figures_visually_checked=True,
            C_H=540, C_hashes_sha256=sha(final/'C_files_sha256.json'), voice_hashes_sha256=sha(final/'voice_files_sha256.json'),
            catalogue_sha256=sha(repo/'references/segments_v1.json'), data_memory_sha256=sha(final/'data_workspace_AGENTS.md'),
            real_audio_read=False, model_exported=False, runtime_changed=False, new_WAV=False, existing55CTests_rerun=False,
            initialization_sole_cause_proved=False, noise_or_omission_sole_explanation_sufficient=False,
            real_shared_phase_DNA_permitted=False, vehicle_timbre_accepted=False, idle_acceleration_complete=False,
            full_qualification=False, goal_complete=False, moving35='held_unchanged', original_A_low_listening='original_question_pending',
            F3_stopped54_56='speech_excluded_from_quantitative_and_DNA', other_reviewed_F_short_clips='usable_mild_wind_noted',
            previous_goal_turn='progress_observed_initial_provenance_and_four_exact_score_covariances',
            current_goal_turn='progress_new_orthogonal_observation_knownfailure_matched_parent_failure_and_all40_independent_audit',
            next_step='Fixed noiseless rapid14 control: qualify observed common-phase initialization and across-line consistency without truth or added iteration budget. Then originalfailed36/all17/full33/individual14k/originalE before real shared-phase DNA.',
            limits=candidate['limits']+['Both known controls failed; not best-achievable-method comparisons or a proof initialization alone caused the failure'])
        current(r); save(summary, r)
    except Exception as exc:
        r.update(result='failed', error=repr(exc)); raise
    finally: save(final/'report.json', r)
    print(json.dumps(dict(result=r['result'], actual_QPs=r['actual_QPs'], dense_started=False)), flush=True)
elif args.stage == 'freeze':
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=repo).strip()
    r = load(summary); current(r); assert sha(summary) == sha(final/'report.json')
    frozen.mkdir(exist_ok=False); shutil.copytree(root, frozen/'evidence')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
    subprocess.run(['git', 'archive', '--format=zip', '--output='+str(frozen/'source.zip'), commit], cwd=repo, check=True)
    files = [dict(path=x.relative_to(frozen).as_posix(), bytes=x.stat().st_size, sha256=sha(x)) for x in sorted(frozen.rglob('*')) if x.is_file()]
    save(frozen/'manifest.json', dict(schema='vsl.freeze/1', source_commit=commit, files=files, prior_manifests=r['prior_manifests'],
        known_phase_controls_qualified=False, original_dense_started=False, real_audio_read=False,
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
    print(json.dumps(dict(result='all_payloads_exact_sources_parents_C_voices_verified', files=len(m['files']),
        manifest_sha256=sha(frozen/'manifest.json'))), flush=True)
