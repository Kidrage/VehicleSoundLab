"""Publish/freeze all QP failures, certified solver, full trace and noise diagnosis."""
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
base = args.workspace/'references/analysis/interior_qp_v1'
final = base/'final1'
summary = repo/'research/interior_qp_v1_summary.json'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')


if args.stage == 'publish':
    final.mkdir(exist_ok=False)
    report = dict(schema='vsl.interior-qp-publication/1', result='running', sources={}, reports={})
    try:
        reports = {}
        expected_changes = {'replay_refined1': {'tools/diagnose_refined_qp_v1.py'},
            'active_geometry1': {'tools/interior_qp_v1/active_set.py'},
            'replay_certified1': {'tools/interior_qp_v1/active_set.py'}}
        folders = ('replay1', 'replay_qr1', 'replay_refined1', 'replay_refined2', 'dual_geometry1',
            'active_geometry1', 'replay_certified1', 'replay_certified2', 'fit1', 'audit1', 'noise1')
        for name in folders:
            folder = base/name
            filename = 'recovered_failure.json' if name == 'replay_certified1' else 'report.json'
            value = load(folder/filename)
            assert not value['real_audio_read'] and not value['real_source_permitted']
            reports[name] = value
            changed = set()
            for relative, digest in value['sources'].items():
                assert sha(folder/'exact_sources'/relative) == digest
                if sha(repo/relative) != digest:
                    changed.add(relative)
            assert changed == expected_changes.get(name, set()), (name, changed)
            report['reports'][name] = dict(path=(folder/filename).relative_to(args.workspace).as_posix(),
                sha256=sha(folder/filename), result=value['result'], changed_executed_sources=sorted(changed))
        for name in ('replay1', 'replay_qr1', 'replay_refined2'):
            assert reports[name]['result'] == 'failed'
            assert reports[name]['replays'][0]['new_QP']['success']
            assert not reports[name]['replays'][1]['new_QP']['success']
        assert reports['replay_refined1']['error'] == "KeyError('replay_iterations')"
        assert reports['replay_certified1']['original_report_not_written']
        assert not reports['replay_certified1']['QP_replays_started']
        assert all(not row['original_numeric_certificate_passed'] for row in reports['dual_geometry1']['cases'])
        assert all(row['refinement']['success'] for row in reports['active_geometry1']['cases'])
        replay, fit, audit, noise = (reports[name] for name in ('replay_certified2', 'fit1', 'audit1', 'noise1'))
        assert replay['result'] == 'independent_controls_and_actual_subproblem_replays_certified'
        assert replay['controls']['passed'] and replay['controls']['forced_active_explicit_polytope']['passed']
        assert len(replay['controls']['active_set_analytic']) == 5
        assert fit['result'] == 'dense_diagnostic_rejected' and not fit['assessment']['qualified']
        assert fit['fit']['iterations'] == 20 and fit['qp_certified'] == 20 and fit['qp_uncertified'] == 0
        assert audit['result'] == 'reconstructed_original_QP_certificates_and_full_trace'
        assert audit['entire_trace_exact'] and audit['final_assessment_exact'] and len(audit['trace']) == 20
        assert audit['qp_certified'] == 20 and audit['qp_uncertified'] == 0
        assert len(audit['replay_certificates']) == 8
        assert all(row['candidate_objective_retraction_radius_exact'] for row in audit['trace'])
        assert noise['fit_report_sha256'] == sha(base/'fit1/report.json')
        assert not noise['may_initialize_estimator'] and noise['residual_decomposition_maximum_error'] < 1e-12
        prior = args.workspace/'references/analysis/quintic_phase_v1/final1'
        for filename in ('C_files_sha256.json', 'voice_files_sha256.json'):
            hashes = load(prior/filename)
            assert all(sha(repo/name) == digest for name, digest in hashes.items())
            shutil.copy2(prior/filename, final/filename)
        assert len(load(final/'C_files_sha256.json')) == 540
        subprocess.run(['git', 'diff', '--exit-code', 'HEAD', '--', 'src', 'modules', 'experiments', 'voices', 'CMakeLists.txt'],
            cwd=repo, capture_output=True, check=True)
        assert not list(base.rglob('*.model')) and not list(base.rglob('*.wav'))
        sources = {Path(__file__), repo/'AGENTS.md', repo/'handoff/算法说明.md', repo/'handoff/研究续接.md',
            repo/'handoff/开发留痕.md', repo/'research/怠速与加速完成度V1.md', repo/'research/平方根受约束求解V1.md'}
        for value in reports.values():
            sources.update(repo/name for name in value['sources'])
        for path in sources:
            relative = path.relative_to(repo)
            target = final/'exact_sources'/relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            report['sources'][relative.as_posix()] = sha(path)
        shutil.copy2(args.workspace/'AGENTS.md', final/'data_workspace_AGENTS.md')
        shutil.copy2(args.workspace/'tools/ipm_install_report.json', final/'ipm_install_report.json')
        assert sha(final/'ipm_install_report.json') == fit['ipm_install_report_sha256']
        assert sha(base/'noise1/certified_phase.png') == noise['plot_sha256']
        shutil.copy2(base/'noise1/certified_phase.png', final/'certified_phase.png')
        report.update(result='all20_QPs_certified_but_actual_phase_rejected',
            actual_fit={key: fit['fit'][key] for key in ('initial_cost', 'final_cost', 'accepted_steps',
                'normalized_projection_residual', 'seconds')} | {'assessment': fit['assessment']},
            QP_certified=20, QP_uncertified=0, complete_trace_reconstructed=True,
            independent_controls=dict(analytic=9, explicit_polytope=4, active_add_drop_zero_singular=True),
            actual_replay_iterations=[1, 20], diagnostic_noise={key: noise[key] for key in ('norms', 'costs',
                'actual_model_error_noise_correlation')},
            native_status_not_sufficient=True, original_certification_gates_unchanged=True,
            original17_rerun=False, full33_replaced=False, individual14kHz_demonstrated=False,
            real_source_permitted=False, source_audio_read=False, model_exported=False, runtime_changed=False,
            C_H=540, existing_Ctests_rerun=False, moving35='held_unchanged', new_media_downloaded=False,
            idle_acceleration_complete=False, vehicle_timbre_accepted=False,
            C_hashes_sha256=sha(final/'C_files_sha256.json'), voice_hashes_sha256=sha(final/'voice_files_sha256.json'),
            ipm_install_report_sha256=sha(final/'ipm_install_report.json'),
            previous_goal_turn_classification='progress_actual_quintic_fit_audit_and_observation_diagnosis',
            goal_turn_classification='progress_independent_QP_solver_active_set_certification_full_actual_fit_and_noise_evidence',
            next_step='Use the now-certified solver to quantify bound-aware common-phase sensitivity/noise regularization while retaining rapid changes, original failed dense positive/all17/full33/individual14kHz/original E; no more blind solver/iteration sweeps',
            limits=['All20 accurate convex subproblems still fail original latent-phase gate; solver accuracy alone does not fix this case',
                '15accepted/5rejected finite-budget nonlinear steps do not prove nonlinear/global convergence',
                'Known noise correlation .929 is diagnosis only, not physical crank or real-recording uncertainty/sole-cause proof',
                'All native/precision/dual-only failures and two implementation failures with exact sources are retained',
                'Clarabel0.11.1 in isolated ipm_deps is optional offline tooling, not a C/audio runtime dependency',
                'F1/F2/F3 and original A-low remain pending; no duplicate requests/downloads'])
        save(summary, report)
    except Exception as exc:
        report.update(result='failed', error=repr(exc))
        raise
    finally:
        save(final/'report.json', report)
    print(json.dumps(dict(result=report['result'], qp_certified=20, real_models=0)), flush=True)
else:
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=repo).strip()
    report = load(summary)
    assert report['result'] == 'all20_QPs_certified_but_actual_phase_rejected'
    assert sha(summary) == sha(final/'report.json')
    for name, digest in report['sources'].items():
        assert sha(repo/name) == sha(final/'exact_sources'/name) == digest
    for value in report['reports'].values():
        assert sha(args.workspace/value['path']) == value['sha256']
    out = args.workspace/'baselines/interior_qp_v1'
    out.mkdir(exist_ok=False)
    shutil.copytree(base, out/'evidence')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
    subprocess.run(['git', 'archive', '--format=zip', '--output='+str(out/'source.zip'), commit], cwd=repo, check=True)
    with zipfile.ZipFile(out/'source.zip') as archive:
        assert archive.testzip() is None
    items = [dict(path=path.relative_to(out).as_posix(), bytes=path.stat().st_size, sha256=sha(path))
        for path in sorted(out.rglob('*')) if path.is_file()]
    prior = args.workspace/'baselines/quintic_phase_v1/manifest.json'
    save(out/'manifest.json', dict(schema='vsl.freeze/1', source_commit=commit, files=items,
        goal_complete=False, profiles_exported=0, source_evaluated=False, vehicle_timbre_accepted=False,
        prior_quintic_manifest=prior.relative_to(args.workspace).as_posix(), prior_quintic_manifest_sha256=sha(prior)))
    assert all(sha(out/item['path']) == item['sha256'] for item in items)
    print(json.dumps(dict(result='frozen', commit=commit, files=len(items), bytes=sum(item['bytes'] for item in items))), flush=True)
