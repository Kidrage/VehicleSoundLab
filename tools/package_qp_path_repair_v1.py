"""Publish, freeze and verify unit-box and feasible-path work, failures included."""
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
analysis = args.workspace/'references/analysis'
final = analysis/'qp_path_repair_v1/final1'
summary = repo/'research/qp_path_repair_v1_summary.json'
frozen = args.workspace/'baselines/qp_path_repair_v1'


def load(path): return json.loads(path.read_text(encoding='utf-8'))
def save(path, value): path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')
def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def current(r):
    for name, digest in r['sources'].items():
        assert sha(repo/name) == sha(final/'exact_sources'/name) == digest
    for item in r['reports'].values():
        assert sha(args.workspace/item['path']) == item['sha256']
    for name in ('C_files_sha256.json', 'voice_files_sha256.json'):
        assert all(sha(repo/file) == digest for file, digest in load(final/name).items())
    assert len(load(final/'C_files_sha256.json')) == 540
    assert sha(args.workspace/'AGENTS.md') == sha(final/'data_workspace_AGENTS.md') == r['data_memory_sha256']
    assert sha(repo/'references/segments_v1.json') == sha(args.workspace/'references/segments_v1.json') == r['catalogue_sha256']
    for item in r['prior_manifests'].values():
        assert sha(args.workspace/item['path']) == item['sha256']
    subprocess.run(['git', 'diff', '--exit-code', 'HEAD', '--', 'src', 'modules', 'experiments', 'voices', 'CMakeLists.txt'], cwd=repo, capture_output=True, check=True)


if args.stage == 'publish':
    final.mkdir(parents=True, exist_ok=False)
    r = dict(schema='vsl.qp-path-repair-final/1', result='running', sources={}, reports={})
    try:
        paths = dict(unit_replay='unit_box_qp_v1/replay1', unit_replay_audit='unit_box_qp_v1/replay_audit1',
            unit_fit='unit_box_qp_v1/fit1', unit_fit_audit='unit_box_qp_v1/fit_audit1',
            feasible_replay='feasible_polish_v1/replay1', feasible_failed_audit='feasible_polish_v1/audit1',
            feasible_audit='feasible_polish_v1/audit2', coarse_failed_diagnosis='feasible_polish_v1/coarse_diagnosis1',
            coarse_diagnosis='feasible_polish_v1/coarse_diagnosis2')
        reports = {name:load(analysis/path/'report.json') for name, path in paths.items()}
        assert reports['unit_replay']['all3_passed']
        assert reports['unit_replay_audit']['result'] == 'six_analytic_and_three_original_QP_transforms_independently_certified'
        fit, audit = reports['unit_fit'], reports['unit_fit_audit']
        assert fit['result'] == 'known_unit_box_rejected'
        assert audit['actual_QPs'] == 20 and audit['QPs_certified'] == 17 and audit['QP_failure_steps'] == [5, 11, 12]
        assert audit['recovery_gates'] == dict(phase=True, root=True, support=True, floor=True, all_QPs=False)
        assert not audit['original_factor_relative_gates_all_passed'] and audit['supplemental_forward_bounds_passed']
        assert audit['candidate_report_sha256'] == sha(analysis/paths['unit_fit']/'report.json')
        assert fit['fit_report_sha256'] == sha(analysis/paths['unit_fit']/'fit.json')
        feasible, checked = reports['feasible_replay'], reports['feasible_audit']
        assert feasible['result'] == 'feasible_polish_replay_rejected'
        assert checked['result'] == 'seven_controls_and_all57_blocking_iterates_independently_rebuilt'
        assert checked['total_saved_iterates'] == 57 and checked['certified_QPs'] == 1 and checked['failed_QPs'] == [11, 12]
        assert checked['candidate_report_sha256'] == sha(analysis/paths['feasible_replay']/'report.json')
        assert reports['feasible_failed_audit']['result'] == reports['coarse_failed_diagnosis']['result'] == 'failed'
        assert reports['coarse_diagnosis']['result'] == 'all3_coarse_dual_support_and_lifted_residuals_decomposed'
        sources = {Path(__file__), repo/'AGENTS.md', repo/'research/求解缩放与可行修正V1.md',
            repo/'handoff/研究续接.md', repo/'handoff/算法说明.md', repo/'handoff/开发留痕.md',
            repo/'research/怠速与加速完成度V1.md', repo/'research/current_demo_v1_summary.json',
            repo/'research/current_demo_v1_listening.json', repo/'handoff/demo/index.html',
            repo/'tools/diagnose_feasible_layout_v1.py'}
        for name, report in reports.items():
            folder = analysis/paths[name]
            r['reports'][name] = dict(path=(folder/'report.json').relative_to(args.workspace).as_posix(), sha256=sha(folder/'report.json'), result=report['result'])
            for relative, digest in report['sources'].items():
                assert sha(folder/'exact_sources'/relative) == digest
                if name not in ('feasible_failed_audit', 'coarse_failed_diagnosis'):
                    assert sha(repo/relative) == digest
                    sources.add(repo/relative)
        layout = analysis/'feasible_polish_v1/layout_diagnosis1.json'
        layout_report = load(layout)
        assert layout_report['result'] == 'original_F_layout_recreates_all57_fractions_exactly'
        r['reports']['layout_diagnosis'] = dict(path=layout.relative_to(args.workspace).as_posix(), sha256=sha(layout), result=layout_report['result'])
        for path in sources:
            relative = path.relative_to(repo); dest = final/'exact_sources'/relative
            dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path, dest)
            r['sources'][relative.as_posix()] = sha(path)
        previous = analysis/'majorizer_paths_v1/final1'
        for name in ('C_files_sha256.json', 'voice_files_sha256.json'):
            shutil.copy2(previous/name, final/name)
        shutil.copy2(args.workspace/'AGENTS.md', final/'data_workspace_AGENTS.md')
        parent = 'baselines/majorizer_paths_v1/manifest.json'
        fitted = load(analysis/paths['unit_fit']/'fit.json')
        r.update(result='unit_box_known_recovery_but_QP_path_still_rejected_feasibility_repaired',
            prior_manifests=dict(majorizer_paths_v1=dict(path=parent, sha256=sha(args.workspace/parent))),
            unit_transform='Equivalent x=r*t and objective/(gamma*r); all original constraints and certificates retained',
            fixed_original_QPs_replayed=3, fixed_original_QPs_certified=3,
            new_nonlinear_fits=1, nonlinear_fit_QPs=20, nonlinear_fit_QPs_certified=17,
            nonlinear_fit_failed_steps=[5, 11, 12], accepted_steps=7,
            recovery_gates=audit['recovery_gates'], assessment=fit['assessment'],
            normalized_residual=fitted['normalized_projection_residual'], final_cost=fitted['final_cost'],
            fixed_latest_feasible_replays=3, feasible_QPs_certified=1, feasible_failed_steps=[11, 12],
            feasible_saved_iterates=57, feasible_maximum_path_primal=max(x['maximum_path_primal'] for x in checked['replays']),
            original_factor_relative_audit_passed=False,
            original_factor_relative_failed_steps=audit['original_factor_relative_gate_failed_steps'],
            separate_forward_bounds_passed=True, audit_layout_failure_preserved=True, coarse_diagnosis_failure_preserved=True,
            coarse_diagnosis=reports['coarse_diagnosis']['cases'],
            known_recovery=True, full_qualification=False, original_dense_started=False, real_shared_phase_DNA_permitted=False,
            C_H=540, C_hashes_sha256=sha(final/'C_files_sha256.json'), voice_hashes_sha256=sha(final/'voice_files_sha256.json'),
            data_memory_sha256=sha(final/'data_workspace_AGENTS.md'), catalogue_sha256=sha(repo/'references/segments_v1.json'),
            real_audio_read=False, model_exported=False, runtime_changed=False, new_WAV=False, existing55CTests_rerun=False,
            moving35='held_unchanged', current_demo_feedback=load(repo/'research/current_demo_v1_listening.json'),
            F3_stopped54_56='speech_excluded_from_quantitative_and_DNA', other_reviewed_F_short_clips='usable_mild_wind_noted',
            original_A_low_listening='original_question_pending', idle_acceleration_complete=False, goal_complete=False,
            previous_goal_turn='progress_existing_demo_guide_media_HTTP_verification_and_user_positive_listening',
            current_goal_turn='progress_equivalentQP_saved_replays_one_knownfit_all20audit_and_one_feasiblepath_all57audit_plus_precision_diagnosis',
            next_step=reports['coarse_diagnosis']['next'],
            limits=['Numerical feasibility repaired in fixed replays; two final original KKT failures remain. No new full nonlinear fit after this rejection.',
                'Known recovery is not real material, timbre, full idle/acceleration or physical7.1.4 qualification.',
                'No truth-guided prefixes, contact/tolerance/iteration sweeps or budget increases. Original36/all17/full33/individual14k/originalE still required.'])
        current(r); save(summary, r)
    except Exception as exc:
        r.update(result='failed', error=repr(exc)); raise
    finally:
        save(final/'report.json', r)
    print(json.dumps(dict(result=r['result'], nonlinear_QPs=20, feasible_iterates=57)), flush=True)
elif args.stage == 'freeze':
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=repo).strip()
    r = load(summary); current(r); assert sha(summary) == sha(final/'report.json')
    frozen.mkdir(exist_ok=False)
    for name in ('unit_box_qp_v1', 'feasible_polish_v1', 'qp_path_repair_v1'):
        shutil.copytree(analysis/name, frozen/'evidence'/name)
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
    subprocess.run(['git', 'archive', '--format=zip', '--output='+str(frozen/'source.zip'), commit], cwd=repo, check=True)
    files = [dict(path=x.relative_to(frozen).as_posix(), bytes=x.stat().st_size, sha256=sha(x)) for x in sorted(frozen.rglob('*')) if x.is_file()]
    save(frozen/'manifest.json', dict(schema='vsl.freeze/1', source_commit=commit, files=files,
        prior_manifests=r['prior_manifests'], known_phase_recovery=True, known_full_qualification=False,
        original_dense_started=False, profiles_exported=0, goal_complete=False))
    print(json.dumps(dict(result='frozen', files=len(files), bytes=sum(x['bytes'] for x in files), source_commit=commit, manifest_sha256=sha(frozen/'manifest.json'))), flush=True)
else:
    r = load(summary); current(r); manifest = load(frozen/'manifest.json')
    assert sha(summary) == sha(final/'report.json') == sha(frozen/'evidence/qp_path_repair_v1/final1/report.json')
    for item in manifest['files']:
        assert sha(frozen/item['path']) == item['sha256'] and (frozen/item['path']).stat().st_size == item['bytes']
    with zipfile.ZipFile(frozen/'source.zip') as archive:
        assert archive.testzip() is None
        for name, digest in r['sources'].items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == digest
    for item in r['prior_manifests'].values():
        parent = args.workspace/item['path']
        for row in load(parent)['files']:
            assert sha(parent.parent/row['path']) == row['sha256']
    print(json.dumps(dict(result='all_payloads_sources_parent_C_voices_verified', files=len(manifest['files']), manifest_sha256=sha(frozen/'manifest.json'))), flush=True)
