"""Publish/freeze the marginal metric, preserved failures, certified fit and signal budgets."""
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
base = args.workspace/'references/analysis/correlated_observation_v1'
final = base/'final1'
summary = repo/'research/correlated_observation_v1_summary.json'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n',
                    encoding='utf-8', newline='\n')


if args.stage == 'publish':
    final.mkdir(exist_ok=False)
    report = dict(schema='vsl.correlated-observation-publication/1', result='running', sources={}, reports={})
    try:
        names = ('geometry1', 'geometry2', 'geometry3', 'numerics1', 'fit1', 'audit1', 'budget1')
        items = {name: load(base/name/'report.json') for name in names}
        assert items['geometry1']['result'] == items['geometry2']['result'] == 'failed'
        assert items['geometry3']['result'] == 'marginal_geometry_and_linear_controls_passed'
        assert items['numerics1']['result'] == 'original_failures_and_final_marginal_geometry_independently_replayed'
        assert not items['numerics1']['cases'][0]['covariance_pass']
        assert not items['numerics1']['cases'][1]['adjoint_pass']
        assert items['numerics1']['cases'][2]['covariance_pass'] and items['numerics1']['cases'][2]['adjoint_pass']
        fit, audit, budget = (items[name] for name in ('fit1', 'audit1', 'budget1'))
        assert fit['result'] == 'dense_marginal_metric_rejected' and not fit['assessment']['qualified']
        assert fit['qp_certified'] == fit['fit']['iterations'] == 20
        assert audit['result'] == 'marginal_metric_original_QP_certificates_and_full_trace_reconstructed'
        assert audit['qp_certified'] == len(audit['trace']) == 20 and audit['entire_trace_and_final_assessment_exact']
        assert audit['candidate_report_sha256'] == sha(base/'fit1/report.json')
        assert budget['result'] == 'known_fixture_raw_and_observation_residual_budgets_closed'
        assert budget['candidate_report_sha256'] == sha(base/'fit1/report.json')
        sources = {Path(__file__), repo/'tools/audit_correlated_geometry_v1.py',
            repo/'AGENTS.md', repo/'handoff/算法说明.md', repo/'handoff/研究续接.md', repo/'handoff/开发留痕.md',
            repo/'research/怠速与加速完成度V1.md', repo/'research/相关观测拟合V1.md'}
        variants = {}
        for name, item in items.items():
            assert not item.get('real_audio_read', False)
            if name == 'numerics1':
                assert sha(repo/'tools/audit_correlated_geometry_v1.py') == sha(base/name/'executed_audit.py') == item['source_sha256']
            for relative, digest in item.get('sources', {}).items():
                assert sha(base/name/'exact_sources'/relative) == digest
                if name in ('geometry1', 'geometry2'):
                    variants.setdefault(relative, []).append(dict(attempt=name, sha256=digest,
                        matches_current_source=(sha(repo/relative) == digest)))
                else:
                    assert sha(repo/relative) == digest
                    sources.add(repo/relative)
            report['reports'][name] = dict(path=(base/name/'report.json').relative_to(args.workspace).as_posix(),
                                          sha256=sha(base/name/'report.json'), result=item['result'])
        prior = args.workspace/'references/analysis/state_media_v1/final1'
        for filename in ('C_files_sha256.json', 'voice_files_sha256.json'):
            hashes = load(prior/filename)
            assert all(sha(repo/path) == digest for path, digest in hashes.items())
            shutil.copy2(prior/filename, final/filename)
        assert len(load(final/'C_files_sha256.json')) == 540
        subprocess.run(['git', 'diff', '--exit-code', 'HEAD', '--', 'src', 'modules', 'experiments', 'voices', 'CMakeLists.txt'],
                       cwd=repo, capture_output=True, check=True)
        assert not list(base.rglob('*.wav')) and not list(base.rglob('*.model'))
        for source in sources:
            relative = source.relative_to(repo)
            target = final/'exact_sources'/relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            report['sources'][relative.as_posix()] = sha(source)
        shutil.copy2(args.workspace/'AGENTS.md', final/'data_workspace_AGENTS.md')
        for directory, name in (('audit1', 'correlated_observation_phase.png'), ('budget1', 'correlated_signal_budget.png')):
            assert sha(base/directory/name) == items[directory]['plot_sha256']
            shutil.copy2(base/directory/name, final/name)
        report.update(result='marginal_correlation_metric_improves_phase_but_rejected_original_gate',
            actual_fit={key: fit['fit'][key] for key in ('iterations', 'accepted_steps', 'initial_cost', 'final_cost',
                'normalized_projection_residual', 'seconds')}, assessment=fit['assessment'],
            QP_certified=20, entire_trace_reconstructed=True,
            geometry=items['geometry3']['controls'], numerical_failures=items['numerics1']['cases'],
            preserved_source_variants=variants, cross_metric_costs=audit['cross_metric_costs'],
            known_fixture_signal_budget=budget['cases'], signal_budget_limits=budget['limitations'],
            original17_rerun=False, full33_replaced=False, individual14kHz_demonstrated=False,
            real_source_permitted=False, source_audio_read=False, model_exported=False, runtime_changed=False,
            C_H=540, existing_Ctests_rerun=False, moving35='held_unchanged',
            F1_F2_F3='approved_and_acquired_in_state_media_v1', A_low_listening='original_question_pending',
            idle_acceleration_complete=False, vehicle_timbre_accepted=False,
            C_hashes_sha256=sha(final/'C_files_sha256.json'), voice_hashes_sha256=sha(final/'voice_files_sha256.json'),
            previous_goal_turn_classification='progress_actual_approved_media_acquisition_and109_PTS_frames',
            goal_turn_classification='progress_actual_correlated_metric_fit_original_certificates_numerical_replays_and_signal_budgets',
            next_step='Use fitting-time observations to handle out-of-band mismatch and noise without absorbing them into fast common phase; do not fit evaluation heldouts or sweep whitening cutoff/ridge; retain failed dense36/all17/full33/individual14kHz/original E',
            limits=fit['limitations'], goal_complete=False)
        save(summary, report)
    except Exception as exc:
        report.update(result='failed', error=repr(exc))
        raise
    finally:
        save(final/'report.json', report)
    print(json.dumps(dict(result=report['result'], QP_certified=20, real_models=0)), flush=True)
else:
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=repo).strip()
    report = load(summary)
    assert report['result'] == 'marginal_correlation_metric_improves_phase_but_rejected_original_gate'
    assert sha(summary) == sha(final/'report.json')
    for name, digest in report['sources'].items():
        assert sha(repo/name) == sha(final/'exact_sources'/name) == digest
    for row in report['reports'].values():
        assert sha(args.workspace/row['path']) == row['sha256']
    out = args.workspace/'baselines/correlated_observation_v1'
    out.mkdir(exist_ok=False)
    shutil.copytree(base, out/'evidence')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
    subprocess.run(['git', 'archive', '--format=zip', '--output='+str(out/'source.zip'), commit], cwd=repo, check=True)
    with zipfile.ZipFile(out/'source.zip') as archive:
        assert archive.testzip() is None
    files = [dict(path=path.relative_to(out).as_posix(), bytes=path.stat().st_size, sha256=sha(path))
             for path in sorted(out.rglob('*')) if path.is_file()]
    prior = args.workspace/'baselines/state_media_v1/manifest.json'
    save(out/'manifest.json', dict(schema='vsl.freeze/1', source_commit=commit, files=files,
        goal_complete=False, profiles_exported=0, source_evaluated=False, vehicle_timbre_accepted=False,
        prior_state_media_manifest=prior.relative_to(args.workspace).as_posix(), prior_state_media_manifest_sha256=sha(prior)))
    assert all(sha(out/row['path']) == row['sha256'] for row in files)
    print(json.dumps(dict(result='frozen', commit=commit, files=len(files), bytes=sum(row['bytes'] for row in files))), flush=True)
