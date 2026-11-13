"""Publish the actual bounded-noise pair and independently reconstructed traces."""
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
base = args.workspace/'references/analysis/bounded_phase_noise_v1'
final = base/'final1'
summary = repo/'research/bounded_phase_noise_v1_summary.json'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n',
                    encoding='utf-8', newline='\n')


if args.stage == 'publish':
    final.mkdir(exist_ok=False)
    report = dict(schema='vsl.bounded-phase-noise-publication/1', result='running', sources={}, reports={})
    try:
        pair, audit = (load(base/name/'report.json') for name in ('pair1', 'audit1'))
        assert pair['result'] == 'bounded_antithetic_observation_sensitivity_measured'
        assert audit['result'] == 'reconstructed_bounded_pair_input_full_traces_and_sensitivity'
        assert audit['candidate_report_sha256'] == sha(base/'pair1/report.json')
        assert pair['controls']['passed'] and pair['zero_case_reuse']['estimator_sources_libraries_model_plan_time_initial_target_scales_exact']
        assert pair['all_QPs_certified'] and pair['sensitivity'] == audit['sensitivity']
        assert len(pair['cases']) == len(audit['cases']) == 2
        for fit, checked in zip(pair['cases'], audit['cases']):
            assert fit['sign'] == checked['sign'] and fit['qp_certified'] == checked['qp_certified'] == 20
            assert fit['fit']['iterations'] == len(checked['trace']) == 20
            assert checked['entire_trace_exact'] and checked['final_phase_assessment_and_bounds_exact']
            assert all(row['candidate_objective_retraction_radius_exact'] for row in checked['trace'])
        assert not audit['nonlinear_estimator_rerun'] and not audit['quadratic_solver_rerun']
        assert audit['proxy_full_complex_FFT_relative_error'] < 1e-12
        assert sha(base/'audit1/bounded_sensitivity.png') == audit['plot_sha256']
        discrepancy = load(base/'discrepancy1/report.json')
        discrepancy_audit = load(base/'discrepancy_audit1/report.json')
        assert discrepancy['result'] == 'discrepancy_prefix_rejected' and not discrepancy['assessment']['qualified']
        assert discrepancy['selection']['selected_iteration'] == 1
        assert discrepancy_audit['result'] == 'observed_discrepancy_crossing_and_rejected_assessment_reconstructed'
        assert discrepancy_audit['candidate_report_sha256'] == sha(base/'discrepancy1/report.json')
        assert discrepancy_audit['observed_only_crossing_exact'] and discrepancy_audit['selected_parameters_phase_and_assessment_exact']
        assert discrepancy_audit['assessment'] == discrepancy['assessment']
        assert sha(base/'discrepancy_audit1/discrepancy_phase.png') == discrepancy_audit['plot_sha256']
        sources = {Path(__file__), repo/'AGENTS.md', repo/'handoff/算法说明.md', repo/'handoff/研究续接.md',
            repo/'handoff/开发留痕.md', repo/'research/怠速与加速完成度V1.md', repo/'research/有界相位噪声敏感度V1.md'}
        for name, value in (('pair1', pair), ('audit1', audit), ('discrepancy1', discrepancy), ('discrepancy_audit1', discrepancy_audit)):
            assert not value['real_audio_read'] and not value['real_source_permitted']
            for relative, digest in value['sources'].items():
                assert sha(repo/relative) == sha(base/name/'exact_sources'/relative) == digest
                sources.add(repo/relative)
            report['reports'][name] = dict(path=(base/name/'report.json').relative_to(args.workspace).as_posix(),
                sha256=sha(base/name/'report.json'), result=value['result'])
        prior = args.workspace/'references/analysis/interior_qp_v1/final1'
        for filename in ('C_files_sha256.json', 'voice_files_sha256.json'):
            hashes = load(prior/filename)
            assert all(sha(repo/name) == digest for name, digest in hashes.items())
            shutil.copy2(prior/filename, final/filename)
        assert len(load(final/'C_files_sha256.json')) == audit['C_H'] == 540
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
        shutil.copy2(base/'audit1/bounded_sensitivity.png', final/'bounded_sensitivity.png')
        shutil.copy2(base/'discrepancy_audit1/discrepancy_phase.png', final/'discrepancy_phase.png')
        report.update(result='actual_bounded_phase_sensitivity_measured_not_qualification',
            noise_proxy=pair['noise_proxy'], added_noise_to_observed_RMS_db=audit['added_noise_to_observed_RMS_db'],
            sensitivity=pair['sensitivity'], original_phase_gate=pair['original_phase_gate'],
            discrepancy_stop=dict(selection=discrepancy['selection'], assessment=discrepancy['assessment'],
                selected_parameters_phase_assessment_independently_reconstructed=True),
            actual_fits=[dict(sign=row['sign'], qp_certified=row['qp_certified'],
                iterations=row['fit']['iterations'], accepted=row['fit']['accepted_steps'],
                final_cost=row['fit']['final_cost'], assessment=row['assessment']) for row in pair['cases']],
            all40_QPs_certified=True, complete_both_traces_reconstructed=True,
            real_source_permitted=False, source_audio_read=False, model_exported=False, runtime_changed=False,
            original17_rerun=False, full33_replaced=False, individual14kHz_demonstrated=False,
            C_H=540, existing_Ctests_rerun=False, moving35='held_unchanged', new_media_downloaded=False,
            C_hashes_sha256=sha(final/'C_files_sha256.json'), voice_hashes_sha256=sha(final/'voice_files_sha256.json'),
            idle_acceleration_complete=False, vehicle_timbre_accepted=False,
            previous_goal_turn_classification='verified_wait_polled_live_audit22197_to_terminal_then_status_answer',
            goal_turn_classification='progress_actual_observation_only_discrepancy_candidate_rejected_independent_audits_publication_and_freeze',
            next_step='Simple observed-noise discrepancy stop fails; noise-aware bounded common-phase stabilization preserving rapid phase and local timbre deviations; no blind strength sweep or real uncertainty from one direction; retain all17/full33/individual14kHz/original E',
            limits=pair['limits']+discrepancy['limits'])
        save(summary, report)
    except Exception as exc:
        report.update(result='failed', error=repr(exc))
        raise
    finally:
        save(final/'report.json', report)
    print(json.dumps(dict(result=report['result'], certified_QPs=40, real_models=0)), flush=True)
else:
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=repo).strip()
    report = load(summary)
    assert report['result'] == 'actual_bounded_phase_sensitivity_measured_not_qualification'
    assert sha(summary) == sha(final/'report.json')
    for name, digest in report['sources'].items():
        assert sha(repo/name) == sha(final/'exact_sources'/name) == digest
    for value in report['reports'].values():
        assert sha(args.workspace/value['path']) == value['sha256']
    out = args.workspace/'baselines/bounded_phase_noise_v1'
    out.mkdir(exist_ok=False)
    shutil.copytree(base, out/'evidence')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
    subprocess.run(['git', 'archive', '--format=zip', '--output='+str(out/'source.zip'), commit], cwd=repo, check=True)
    with zipfile.ZipFile(out/'source.zip') as archive:
        assert archive.testzip() is None
    items = [dict(path=path.relative_to(out).as_posix(), bytes=path.stat().st_size, sha256=sha(path))
             for path in sorted(out.rglob('*')) if path.is_file()]
    prior = args.workspace/'baselines/interior_qp_v1/manifest.json'
    save(out/'manifest.json', dict(schema='vsl.freeze/1', source_commit=commit, files=items,
        goal_complete=False, profiles_exported=0, source_evaluated=False, vehicle_timbre_accepted=False,
        prior_interior_manifest=prior.relative_to(args.workspace).as_posix(), prior_interior_manifest_sha256=sha(prior)))
    assert all(sha(out/item['path']) == item['sha256'] for item in items)
    print(json.dumps(dict(result='frozen', commit=commit, files=len(items), bytes=sum(item['bytes'] for item in items))), flush=True)
