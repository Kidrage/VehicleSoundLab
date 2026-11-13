"""Publish and freeze the rejected score construction and its independent evidence."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--stage', choices=('publish', 'freeze'), required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(args.workspace/'tools/python_deps'))
from drive_evidence_v1.sources import sha
base = args.workspace/'references/analysis/model_score_v1'
final = base/'final1'
summary = repo/'research/model_score_v1_summary.json'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n',
                    encoding='utf-8', newline='\n')


if args.stage == 'publish':
    final.mkdir(exist_ok=False)
    report = dict(schema='vsl.model-score-publication/1', result='running', sources={}, reports={})
    try:
        names = ('geometry1', 'invariance1', 'audit1', 'conditioning1')
        items = {name: load(base/name/'report.json') for name in names}
        geometry, invariance, audit, conditioning = (items[name] for name in names)
        assert geometry['result'] == 'fixed_initial_score_geometry_and_linear_controls_passed'
        assert invariance['result'] == 'fixed_initial_score_space_not_numerically_qualified'
        assert not invariance['fit_permitted'] and not invariance['controls']['passed']
        assert invariance['controls']['analytic_full_rank_control']['passed']
        assert audit['result'] == 'initial_score_geometry_replayed_and_permutation_failure_independently_confirmed'
        assert audit['geometry_and_invariance_exact_replay'] and audit['failed_permutation_retained']
        assert audit['invariance_report_sha256'] == sha(base/'invariance1/report.json')
        assert conditioning['result'] == 'same_initial_tangent_conditioning_measured_without_fitting'
        assert conditioning['sample_to_observed_jacobian_maximum_error'] == 0
        sources = {Path(__file__), repo/'AGENTS.md', repo/'handoff/算法说明.md',
            repo/'handoff/研究续接.md', repo/'handoff/开发留痕.md', repo/'research/怠速与加速完成度V1.md',
            repo/'research/初始声源矩投影V1.md'}
        for name, value in items.items():
            assert not value['real_audio_read'] and not value['truth_used'] and not value['heldout_used']
            assert not value.get('nonlinear_estimator_run', False)
            assert not value['model_exported'] and not value['runtime_changed']
            for relative, digest in value['sources'].items():
                assert sha(repo/relative) == sha(base/name/'exact_sources'/relative) == digest
                sources.add(repo/relative)
            report['reports'][name] = dict(path=(base/name/'report.json').relative_to(args.workspace).as_posix(),
                                          sha256=sha(base/name/'report.json'), result=value['result'])
        prior = args.workspace/'references/analysis/state_media_v1/final1'
        for filename in ('C_files_sha256.json', 'voice_files_sha256.json'):
            hashes = load(prior/filename)
            assert all(sha(repo/path) == digest for path, digest in hashes.items())
            shutil.copy2(prior/filename, final/filename)
        assert len(load(final/'C_files_sha256.json')) == 540
        subprocess.run(['git', 'diff', '--exit-code', 'HEAD', '--', 'src', 'modules', 'experiments', 'voices', 'CMakeLists.txt'],
                       cwd=repo, capture_output=True, check=True)
        assert not list(base.rglob('*.wav')) and not list(base.rglob('*.model')) and not (base/'fit1').exists()
        for source in sources:
            relative = source.relative_to(repo)
            target = final/'exact_sources'/relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            report['sources'][relative.as_posix()] = sha(source)
        shutil.copy2(args.workspace/'AGENTS.md', final/'data_workspace_AGENTS.md')
        for directory, filename in (('audit1', 'model_score_numerics.png'), ('conditioning1', 'model_score_conditioning.png')):
            assert sha(base/directory/filename) == items[directory]['plot_sha256']
            shutil.copy2(base/directory/filename, final/filename)
        report.update(result='fixed_initial_score_rejected_before_fit_due_to_numerical_order_dependence',
            geometry_controls=geometry['controls'],
            initial_score_condition=geometry['basis']['normalized_adjoint_jacobian_condition'],
            all732_directions_retained=True, permutation_controls=invariance['controls'],
            exact_replay=True, independent_projection_checks=audit['independent_projection_checks'],
            tangent_conditioning=conditioning['spectra'],
            sample_to_observed_jacobian_error=0., nonlinear_estimator_run=False, phase_fit_attempted=False,
            original17_rerun=False, full33_replaced=False, individual14kHz_demonstrated=False,
            real_source_permitted=False, source_audio_read=False, model_exported=False, runtime_changed=False,
            C_H=540, existing_Ctests_rerun=False, moving35='held_unchanged',
            F1_F2_F3='approved_and_acquired_in_state_media_v1', A_low_listening='original_question_pending',
            idle_acceleration_complete=False, vehicle_timbre_accepted=False,
            C_hashes_sha256=sha(final/'C_files_sha256.json'), voice_hashes_sha256=sha(final/'voice_files_sha256.json'),
            previous_goal_turn_classification='progress_actual_correlated_metric_fit_audits_and_signal_budgets',
            goal_turn_classification='progress_actual_score_geometry_permutation_rejection_independent_replay_and_tangent_conditioning',
            next_step='Original-bound observed finite common-phase and amplitude-compensation stability before designing noise-aware extraction; preserve rapid phase and failed dense36/all17/full33/individual14kHz/original E; no blind whitening/QR/cutoff/ridge/iteration sweeps',
            limits=[*invariance['limitations'], *audit['limitations'], *conditioning['limitations']],
            goal_complete=False)
        save(summary, report)
    except Exception as exc:
        report.update(result='failed', error=repr(exc))
        raise
    finally:
        save(final/'report.json', report)
    print(json.dumps(dict(result=report['result'], phase_fits=0, real_models=0)), flush=True)
else:
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=repo).strip()
    report = load(summary)
    assert report['result'] == 'fixed_initial_score_rejected_before_fit_due_to_numerical_order_dependence'
    assert sha(summary) == sha(final/'report.json')
    for relative, digest in report['sources'].items():
        assert sha(repo/relative) == sha(final/'exact_sources'/relative) == digest
    for row in report['reports'].values():
        assert sha(args.workspace/row['path']) == row['sha256']
    out = args.workspace/'baselines/model_score_v1'
    out.mkdir(exist_ok=False)
    shutil.copytree(base, out/'evidence')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
    subprocess.run(['git', 'archive', '--format=zip', '--output='+str(out/'source.zip'), commit], cwd=repo, check=True)
    with zipfile.ZipFile(out/'source.zip') as archive:
        assert archive.testzip() is None
    files = [dict(path=path.relative_to(out).as_posix(), bytes=path.stat().st_size, sha256=sha(path))
             for path in sorted(out.rglob('*')) if path.is_file()]
    prior = args.workspace/'baselines/correlated_observation_v1/manifest.json'
    save(out/'manifest.json', dict(schema='vsl.freeze/1', source_commit=commit, files=files,
        goal_complete=False, profiles_exported=0, source_evaluated=False, vehicle_timbre_accepted=False,
        prior_correlated_manifest=prior.relative_to(args.workspace).as_posix(), prior_correlated_manifest_sha256=sha(prior)))
    assert all(sha(out/row['path']) == row['sha256'] for row in files)
    print(json.dumps(dict(result='frozen', commit=commit, files=len(files), bytes=sum(row['bytes'] for row in files))), flush=True)
