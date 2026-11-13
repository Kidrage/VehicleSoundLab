"""Publish/freeze native-bin observations, actual fit, audit and noise geometry."""
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
base = args.workspace/'references/analysis/native_observation_v1'
final = base/'final1'
summary = repo/'research/native_observation_v1_summary.json'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')


if args.stage == 'publish':
    final.mkdir(exist_ok=False)
    report = dict(schema='vsl.native-observation-publication/1', result='running', sources={}, reports={})
    try:
        reports = {name: load(base/name/'report.json') for name in ('fit1', 'audit1', 'noise1')}
        fit, audit, noise = (reports[name] for name in ('fit1', 'audit1', 'noise1'))
        assert fit['result'] == 'dense_native_observation_rejected' and not fit['assessment']['qualified']
        assert fit['qp_certified'] == fit['fit']['iterations'] == 20
        assert fit['controls']['passed'] and fit['unchanged_waveform_phase_amplitude_bounds_and_initial']
        assert audit['result'] == 'native_geometry_original_QP_certificates_and_full_trace_reconstructed'
        assert audit['candidate_report_sha256'] == sha(base/'fit1/report.json')
        assert audit['qp_certified'] == len(audit['trace']) == 20 and audit['entire_trace_and_final_assessment_exact']
        assert audit['original_observation_subset_exact'] and audit['waveform_model_and_original_initial_exact']
        assert noise['result'] == 'exact_periodic_Hann_frequency_and_overlap_noise_geometry_measured'
        assert not noise['real_audio_read'] and not noise['whitening_applied']
        assert all(row['exact_Hann_hermitian_covariance_maximum_error'] < 1e-12 and not row['phase_information_rank']
            and not row['real_noise_calibrated'] for row in noise['cases'])
        sources = {Path(__file__), repo/'AGENTS.md', repo/'handoff/算法说明.md', repo/'handoff/研究续接.md',
            repo/'handoff/开发留痕.md', repo/'research/怠速与加速完成度V1.md', repo/'research/原生频点观测V1.md'}
        for name, value in reports.items():
            assert not value['real_audio_read'] and not value['real_source_permitted']
            for relative, digest in value['sources'].items():
                assert sha(repo/relative) == sha(base/name/'exact_sources'/relative) == digest
                sources.add(repo/relative)
            report['reports'][name] = dict(path=(base/name/'report.json').relative_to(args.workspace).as_posix(),
                sha256=sha(base/name/'report.json'), result=value['result'])
        prior = args.workspace/'references/analysis/noise_budget_phase_v1/final1'
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
        assert sha(base/'audit1/native_observation_phase.png') == audit['plot_sha256']
        shutil.copy2(base/'audit1/native_observation_phase.png', final/'native_observation_phase.png')
        report.update(result='native_bin_completion_rejected_phase_gate_exact_noise_correlations_measured',
            actual_fit={key: fit['fit'][key] for key in ('iterations', 'accepted_steps', 'initial_cost', 'final_cost',
                'normalized_projection_residual', 'seconds')}, assessment=fit['assessment'],
            QP_certified=20, entire_trace_reconstructed=True, geometry=fit['geometry'],
            independent_projection_controls=fit['controls'], cross_observation_costs=audit['cross_observation_costs'],
            noise_geometry=noise['cases'], frequency_and_overlap_covariance_exact=True,
            original17_rerun=False, full33_replaced=False, individual14kHz_demonstrated=False,
            real_source_permitted=False, source_audio_read=False, model_exported=False, runtime_changed=False,
            C_H=540, existing_Ctests_rerun=False, moving35='held_unchanged', new_media_downloaded=False,
            idle_acceleration_complete=False, vehicle_timbre_accepted=False,
            C_hashes_sha256=sha(final/'C_files_sha256.json'), voice_hashes_sha256=sha(final/'voice_files_sha256.json'),
            previous_goal_turn_classification='progress_actual_noise_budget_estimator_failure_full_audit_and_freeze',
            goal_turn_classification='progress_actual_native_bin_fit_independent_trace_and_exact_noise_geometry_evidence',
            next_step='Use exact correlated-observation noise geometry in a qualified fitting metric; handle redundant covariance without arbitrary ridge and test omitted/out-of-band signal amplification; preserve fast phase and original failed dense positive/all17/full33/individual14kHz/original E',
            limits=fit['limits']+noise['limits'])
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
    assert report['result'] == 'native_bin_completion_rejected_phase_gate_exact_noise_correlations_measured'
    assert sha(summary) == sha(final/'report.json')
    for name, digest in report['sources'].items():
        assert sha(repo/name) == sha(final/'exact_sources'/name) == digest
    for value in report['reports'].values():
        assert sha(args.workspace/value['path']) == value['sha256']
    out = args.workspace/'baselines/native_observation_v1'
    out.mkdir(exist_ok=False)
    shutil.copytree(base, out/'evidence')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
    subprocess.run(['git', 'archive', '--format=zip', '--output='+str(out/'source.zip'), commit], cwd=repo, check=True)
    with zipfile.ZipFile(out/'source.zip') as archive:
        assert archive.testzip() is None
    items = [dict(path=path.relative_to(out).as_posix(), bytes=path.stat().st_size, sha256=sha(path))
        for path in sorted(out.rglob('*')) if path.is_file()]
    prior = args.workspace/'baselines/noise_budget_phase_v1/manifest.json'
    save(out/'manifest.json', dict(schema='vsl.freeze/1', source_commit=commit, files=items,
        goal_complete=False, profiles_exported=0, source_evaluated=False, vehicle_timbre_accepted=False,
        prior_noise_budget_manifest=prior.relative_to(args.workspace).as_posix(), prior_noise_budget_manifest_sha256=sha(prior)))
    assert all(sha(out/item['path']) == item['sha256'] for item in items)
    print(json.dumps(dict(result='frozen', commit=commit, files=len(items), bytes=sum(item['bytes'] for item in items))), flush=True)
