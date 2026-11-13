"""Publish, freeze and verify observed initialization/overlap research, including failure."""
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
root = args.workspace/'references/analysis/observed_score_overlap_v1'; final = root/'final1'
summary = repo/'research/observed_score_overlap_v1_summary.json'
frozen = args.workspace/'baselines/observed_score_overlap_v1'


def load(path): return json.loads(path.read_text(encoding='utf-8'))
def save(path, value): path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')
def sha(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()


def current(r):
    for name, digest in r['sources'].items(): assert sha(repo/name) == sha(final/'exact_sources'/name) == digest
    for item in r['reports'].values(): assert sha(args.workspace/item['path']) == item['sha256']
    for item in r['historical_source_versions']: assert sha(args.workspace/item['path']) == item['sha256']
    for name in ('C_files_sha256.json', 'voice_files_sha256.json'):
        assert all(sha(repo/file) == digest for file, digest in load(final/name).items())
    assert len(load(final/'C_files_sha256.json')) == 540
    assert sha(args.workspace/'AGENTS.md') == sha(final/'data_workspace_AGENTS.md') == r['data_memory_sha256']
    assert sha(repo/'references/segments_v1.json') == sha(args.workspace/'references/segments_v1.json') == r['catalogue_sha256']
    for item in r['original_report_chain']: assert sha(args.workspace/item['path']) == item['sha256']
    for item in r['prior_manifests'].values(): assert sha(args.workspace/item['path']) == item['sha256']
    subprocess.run(['git', 'diff', '--exit-code', 'HEAD', '--', 'src', 'modules', 'experiments', 'voices', 'CMakeLists.txt'],
        cwd=repo, capture_output=True, check=True)


if args.stage == 'publish':
    final.mkdir(exist_ok=False)
    r = dict(schema='vsl.observed-score-overlap-final/1', result='running', sources={}, reports={}, historical_source_versions=[])
    try:
        values = {name: load(root/name/'report.json') for name in ('observe1', 'audit1', 'audit2')}
        observed, failed, audit = (values[name] for name in ('observe1', 'audit1', 'audit2'))
        assert observed['result'] == 'frozen_observed_initialization_and_exact_score_overlap_measured' and observed['controls']['passed']
        assert failed['result'] == 'failed' and failed['error'] == 'AssertionError()' and len(failed['cases']) == 3
        assert audit['result'] == 'four_covariance_geometries_rebuilt_score_relative_gate_separately_retained'
        assert not audit['all_original_score_relative_gates_passed']
        assert all(row['score_check']['additional_forward_bound_passed'] for row in audit['cases'])
        assert not audit['cases'][-1]['score_check']['original_relative_gate_passed']
        for old, new in zip(failed['cases'], audit['cases']):
            assert old['id'] == new['id'] and old['independent_relative_errors'] == new['independent_relative_errors']
        sources = {Path(__file__), repo/'AGENTS.md', repo/'research/观测初值与重叠证据V1.md',
            repo/'handoff/研究续接.md', repo/'handoff/算法说明.md', repo/'handoff/开发留痕.md',
            repo/'research/怠速与加速完成度V1.md'}
        for name, value in values.items():
            assert not value['real_audio_read'] and not value['truth_read'] and not value['heldout_used']
            assert not value['estimator_rerun'] and not value['model_exported'] and not value['runtime_changed']
            r['reports'][name] = dict(path=(root/name/'report.json').relative_to(args.workspace).as_posix(),
                sha256=sha(root/name/'report.json'), result=value['result'])
            for file, digest in value['sources'].items():
                assert sha(root/name/'exact_sources'/file) == digest
                if sha(repo/file) != digest:
                    assert name == 'audit1' and file == 'tools/audit_observed_score_overlap_v1.py'
                    r['historical_source_versions'].append(dict(path=(root/name/'exact_sources'/file).relative_to(args.workspace).as_posix(),
                        sha256=digest, current_sha256=sha(repo/file), reason='Original relative-score assertion failure retained; supplemental cancellation bound separately declared'))
                sources.add(repo/file)
        assert len(r['historical_source_versions']) == 1
        for name in ('audit1', 'audit2'):
            assert values[name]['parent_report_sha256'] == sha(root/'observe1/report.json')
        for row in observed['cases']: assert sha(root/'observe1'/(row['id']+'.npz')) == row['arrays_sha256']
        for source in sources:
            relative = source.relative_to(repo); dest = final/'exact_sources'/relative
            dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(source, dest)
            r['sources'][relative.as_posix()] = sha(source)
        previous = args.workspace/'references/analysis/bounded_observed_phase_v1/final1'
        for name in ('C_files_sha256.json', 'voice_files_sha256.json'): shutil.copy2(previous/name, final/name)
        shutil.copy2(args.workspace/'AGENTS.md', final/'data_workspace_AGENTS.md')
        parents = {name: dict(path='baselines/'+name+'/manifest.json',
            sha256=sha(args.workspace/'baselines'/name/'manifest.json'))
            for name in ('bounded_observed_phase_v1', 'complex_radial_v1')}
        r.update(result='observed_initial_lineage_and_full_score_overlap_measured_NOT_phase_recovery',
            original_report_chain=observed['parent_report_chain'], prior_manifests=parents,
            initialization=observed['initialization'], controls=observed['controls'], measurements=observed['cases'],
            independent_covariance_reconstruction=audit['cases'],
            original_failed_audit_preserved=True, original_failed_score_gate_reconstructed=True,
            all_original_score_relative_gates_passed=False, additional_forward_bounds_passed=True,
            C_H=540, C_hashes_sha256=sha(final/'C_files_sha256.json'), voice_hashes_sha256=sha(final/'voice_files_sha256.json'),
            catalogue_sha256=sha(repo/'references/segments_v1.json'), data_memory_sha256=sha(final/'data_workspace_AGENTS.md'),
            real_audio_read=False, truth_read=False, heldout_used=False, estimator_rerun=False, quadratic_solver_rerun=False,
            model_exported=False, runtime_changed=False, existing55CTests_rerun=False, new_audio=False,
            fitted_phase_uncertainty=False, original_phase_error_cause_proved=False, real_shared_phase_DNA_permitted=False,
            vehicle_timbre_accepted=False, idle_acceleration_complete=False, full_qualification=False, goal_complete=False,
            moving35='held_unchanged', original_A_low_listening='original_question_pending',
            F3_stopped54_56='speech_excluded_from_quantitative_and_DNA', other_reviewed_F_short_clips='usable_mild_wind_noted',
            previous_goal_turn='progress_one_bounded_observed_direction_and_original_metric_cross_evaluations',
            current_goal_turn='progress_actual_observed_initial_lineage_and_four_full_score_covariances_independently_rebuilt',
            next_step='Design update/qualification from full source noise and observed support; independent rapid-phase controls before one original dense36. No mechanical ratio weight, inverse rescue, initialization/window/bound/strength sweep. Original36/all17/full33/individual14k/originalE before real DNA.',
            limits=observed['limits'])
        current(r); save(summary, r)
    except Exception as exc:
        r.update(result='failed', error=repr(exc)); raise
    finally: save(final/'report.json', r)
    print(json.dumps(dict(result=r['result'], cases=len(r['measurements']), original_score_gate_still_failed=True)), flush=True)
elif args.stage == 'freeze':
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=repo).strip()
    r = load(summary); current(r); assert sha(summary) == sha(final/'report.json')
    frozen.mkdir(exist_ok=False); shutil.copytree(root, frozen/'evidence')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
    subprocess.run(['git', 'archive', '--format=zip', '--output='+str(frozen/'source.zip'), commit], cwd=repo, check=True)
    files = [dict(path=x.relative_to(frozen).as_posix(), bytes=x.stat().st_size, sha256=sha(x))
        for x in sorted(frozen.rglob('*')) if x.is_file()]
    save(frozen/'manifest.json', dict(schema='vsl.freeze/1', source_commit=commit, files=files,
        prior_manifests=r['prior_manifests'], original_score_relative_gate_passed=False,
        additional_forward_bounds_passed=True, real_audio_read=False, profiles_exported=0,
        original_dense_control_qualified=False, vehicle_timbre_accepted=False, goal_complete=False))
    print(json.dumps(dict(result='frozen', files=len(files), bytes=sum(x['bytes'] for x in files),
        commit=commit, manifest_sha256=sha(frozen/'manifest.json'))), flush=True)
else:
    r = load(summary); current(r); m = load(frozen/'manifest.json')
    assert sha(summary) == sha(final/'report.json') == sha(frozen/'evidence/final1/report.json')
    for item in m['files']:
        assert sha(frozen/item['path']) == item['sha256'] and (frozen/item['path']).stat().st_size == item['bytes']
    with zipfile.ZipFile(frozen/'source.zip') as archive:
        assert archive.testzip() is None
        for name, digest in r['sources'].items(): assert hashlib.sha256(archive.read(name)).hexdigest() == digest
    for item in r['prior_manifests'].values():
        path = args.workspace/item['path']; assert sha(path) == item['sha256']
        for row in load(path)['files']: assert sha(path.parent/row['path']) == row['sha256']
    print(json.dumps(dict(result='all_payloads_historical_versions_sources_parents_C_voices_verified',
        files=len(m['files']), manifest_sha256=sha(frozen/'manifest.json'))), flush=True)
