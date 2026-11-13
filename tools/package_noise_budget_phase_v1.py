"""Freeze the rejected noise-budget estimator, controls and full reconstruction."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--stage', choices=['publish', 'freeze'], required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(args.workspace/'tools/python_deps'))
from drive_evidence_v1.sources import sha
base = args.workspace/'references/analysis/noise_budget_phase_v1'
final = base/'final1'
summary = repo/'research/noise_budget_phase_v1_summary.json'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')


if args.stage == 'publish':
    final.mkdir(exist_ok=False)
    report = dict(schema='vsl.noise-budget-phase-publication/1', result='running', sources={}, reports={})
    try:
        reports = {name: load(base/name/'report.json') for name in ('fit1', 'fit2', 'audit1', 'audit2', 'bias1')}
        expected_changes = {'fit1': {'research/noise_budget_phase_v1_plan.json', 'tools/noise_budget_phase_v1/conic.py',
            'tools/noise_budget_phase_v1/fit.py', 'tools/diagnose_noise_budget_phase_v1.py'},
            'audit1': {'tools/audit_noise_budget_phase_v1.py'}}
        sources = {Path(__file__), repo/'AGENTS.md', repo/'handoff/算法说明.md', repo/'handoff/研究续接.md',
            repo/'handoff/开发留痕.md', repo/'research/怠速与加速完成度V1.md', repo/'research/噪声预算相位稳定化V1.md'}
        for name, value in reports.items():
            assert not value['real_audio_read'] and not value['real_source_permitted']
            changed = set()
            for relative, digest in value['sources'].items():
                assert sha(base/name/'exact_sources'/relative) == digest
                if sha(repo/relative) != digest:
                    changed.add(relative)
                sources.add(repo/relative)
            assert changed == expected_changes.get(name, set()), (name, changed)
            report['reports'][name] = dict(path=(base/name/'report.json').relative_to(args.workspace).as_posix(),
                sha256=sha(base/name/'report.json'), result=value['result'], changed_executed_sources=sorted(changed))
        assert all(reports[name]['result'] == 'dense_noise_budget_candidate_rejected' and
            not reports[name]['assessment']['qualified'] for name in ('fit1', 'fit2'))
        assert reports['fit1']['fit']['conic_subproblems_certified'] == 6
        assert reports['fit2']['fit']['conic_subproblems_certified'] == 20
        assert reports['fit2']['fit']['noise_budget_feasible']
        assert reports['audit1']['result'] == 'failed' and reports['audit1']['error'] == 'AssertionError()'
        audit = reports['audit2']
        assert audit['result'] == 'original_conic_certificates_and_full_noise_budget_traces_reconstructed'
        assert not audit['independent_solver_controls_qualified'] and not audit['independent_controls']['passed']
        assert audit['independent_controls']['cases'][0]['solution_error'] > 1e-7
        assert len(audit['cases']) == 2 and all(row['original_conic_certificates_passed'] == 20 and
            len(row['trace']) == 20 and row['all_candidates_merit_noise_radius_and_final_assessment_exact'] for row in audit['cases'])
        assert not reports['bias1']['may_initialize_estimator'] and not reports['bias1']['linear_projection_solves']
        prior = args.workspace/'references/analysis/bounded_phase_noise_v1/final1'
        for name in ('C_files_sha256.json', 'voice_files_sha256.json'):
            hashes = load(prior/name)
            assert all(sha(repo/path) == digest for path, digest in hashes.items())
            shutil.copy2(prior/name, final/name)
        assert len(load(final/'C_files_sha256.json')) == 540
        subprocess.run(['git', 'diff', '--exit-code', 'HEAD', '--', 'src', 'modules', 'experiments', 'voices', 'CMakeLists.txt'],
            cwd=repo, capture_output=True, check=True)
        assert not list(base.rglob('*.model')) and not list(base.rglob('*.wav'))
        for path in sources:
            relative = path.relative_to(repo)
            target = final/'exact_sources'/relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            report['sources'][relative.as_posix()] = sha(path)
        shutil.copy2(args.workspace/'AGENTS.md', final/'data_workspace_AGENTS.md')
        for folder, name in (('audit2', 'noise_budget_phase.png'), ('bias1', 'roughness_bias.png')):
            assert sha(base/folder/name) == reports[folder]['plot_sha256']
            shutil.copy2(base/folder/name, final/name)
        report.update(result='noise_budget_smoothing_rejected_rapid_phase_bias_and_independent_control_failure',
            actual_fits={name: dict(assessment=reports[name]['assessment'],
                fit={key: reports[name]['fit'][key] for key in ('iterations', 'accepted_steps', 'conic_subproblems_certified',
                    'final_noise_ratio', 'final_roughness', 'seconds')}) for name in ('fit1', 'fit2')},
            original_conic_KKT_passed=40, complete_both_traces_reconstructed=True,
            independent_solver_controls_qualified=False, failed_control=audit['independent_controls']['cases'][0],
            known_representation_diagnosis=reports['bias1']['cases'],
            original17_rerun=False, full33_replaced=False, individual14kHz_demonstrated=False,
            real_source_permitted=False, source_audio_read=False, model_exported=False, runtime_changed=False,
            C_H=540, existing_Ctests_rerun=False, moving35='held_unchanged', new_media_downloaded=False,
            idle_acceleration_complete=False, vehicle_timbre_accepted=False,
            C_hashes_sha256=sha(final/'C_files_sha256.json'), voice_hashes_sha256=sha(final/'voice_files_sha256.json'),
            previous_goal_turn_classification='progress_actual_discrepancy_candidate_independent_audits_and_freeze',
            goal_turn_classification='progress_actual_noise_budget_SOCP_estimator_two_runs_full_trace_audit_and_rapid_phase_bias_evidence',
            next_step='Protect observed-supported rapid common phase under noise, first on independent rapid/occlusion/local-phase controls; no blind derivative/noise-multiplier/iteration sweep; retain failed dense positive/all17/full33/individual14kHz/original E',
            limits=['Minimum global phase jerk within mean white-noise budget worsens original phase error; neither candidate is a new timbre',
                'All40 scalar original conic KKT checks pass, but independent ellipsoid variable accuracy4.43e-7 fails1e-7; backend is not fully qualified',
                'Finite nonlinear steps and tiny objective changes do not prove global/local nonlinear convergence',
                'Frozen known-phase point is diagnosis only; its fixed nuisance noise ratio1.195 is not a fixed-phase optimum or an estimator initialization',
                'First native-status over-rejection, failed audit assertion, exact executed sources and original gates are retained',
                'No real noise calibration/new media; F1/F2/F3 and original A-low remain pending without duplicate requests'])
        save(summary, report)
    except Exception as exc:
        report.update(result='failed', error=repr(exc))
        raise
    finally:
        save(final/'report.json', report)
    print(json.dumps(dict(result=report['result'], original_KKT=40, solver_qualified=False, real_models=0)), flush=True)
else:
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=repo).strip()
    report = load(summary)
    assert report['result'] == 'noise_budget_smoothing_rejected_rapid_phase_bias_and_independent_control_failure'
    assert sha(summary) == sha(final/'report.json')
    for name, digest in report['sources'].items():
        assert sha(repo/name) == sha(final/'exact_sources'/name) == digest
    for value in report['reports'].values():
        assert sha(args.workspace/value['path']) == value['sha256']
    out = args.workspace/'baselines/noise_budget_phase_v1'
    out.mkdir(exist_ok=False)
    shutil.copytree(base, out/'evidence')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
    subprocess.run(['git', 'archive', '--format=zip', '--output='+str(out/'source.zip'), commit], cwd=repo, check=True)
    with zipfile.ZipFile(out/'source.zip') as archive:
        assert archive.testzip() is None
    items = [dict(path=path.relative_to(out).as_posix(), bytes=path.stat().st_size, sha256=sha(path))
        for path in sorted(out.rglob('*')) if path.is_file()]
    prior = args.workspace/'baselines/bounded_phase_noise_v1/manifest.json'
    save(out/'manifest.json', dict(schema='vsl.freeze/1', source_commit=commit, files=items,
        goal_complete=False, profiles_exported=0, source_evaluated=False, vehicle_timbre_accepted=False,
        prior_bounded_noise_manifest=prior.relative_to(args.workspace).as_posix(), prior_bounded_noise_manifest_sha256=sha(prior)))
    assert all(sha(out/item['path']) == item['sha256'] for item in items)
    print(json.dumps(dict(result='frozen', commit=commit, files=len(items), bytes=sum(item['bytes'] for item in items))), flush=True)
