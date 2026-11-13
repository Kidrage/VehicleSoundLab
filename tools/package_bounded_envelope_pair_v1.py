"""Publish and freeze audited finite amplitude compensation, without changing runtime."""
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
base = args.workspace/'references/analysis/bounded_envelope_pair_v1'
final = base/'final1'
summary = repo/'research/bounded_envelope_pair_v1_summary.json'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n',
                    encoding='utf-8', newline='\n')


if args.stage == 'publish':
    final.mkdir(exist_ok=False)
    report = dict(schema='vsl.bounded-envelope-pair-publication/1', result='running', sources={}, reports={})
    try:
        locations = dict(pair1=base/'pair1', audit1=base/'audit1')
        items = {name: load(path/'report.json') for name, path in locations.items()}
        pair, audit = items['pair1'], items['audit1']
        assert pair['result'] == 'finite_envelope_compensation_certified_not_phase_qualification'
        assert pair['controls']['passed'] and len(pair['cases']) == 2
        assert all(row['feasible'] and row['fit']['certificate']['success'] for row in pair['cases'])
        assert all(not row['fit']['qp']['primal_polish_attempted'] for row in pair['cases'])
        assert audit['result'] == 'full_bounded_envelope_certificates_controls_and_waveforms_independently_reconstructed'
        assert audit['candidate_report_sha256'] == sha(base/'pair1/report.json')
        assert audit['all_saved_controls_and_parameters_exact'] and not audit['large_QPs_rerun']
        assert all(row['certificate']['passed'] for row in audit['cases']+audit['controls'])
        parent = args.workspace/'references/analysis/bounded_clock_pair_v1/pair2'
        assert sha(parent/'report.json') == pair['parent_report_sha256'] == audit['parent_report_sha256']
        sources = {Path(__file__), repo/'AGENTS.md', repo/'handoff/算法说明.md', repo/'handoff/研究续接.md',
            repo/'handoff/开发留痕.md', repo/'research/怠速与加速完成度V1.md',
            repo/'research/慢包络有限补偿V1.md'}
        for name, value in items.items():
            assert not value['real_audio_read'] and not value['truth_used'] and not value['heldout_used']
            assert not value['phase_estimator_run'] and not value['model_exported'] and not value['runtime_changed']
            for relative, digest in value['sources'].items():
                assert sha(repo/relative) == sha(locations[name]/'exact_sources'/relative) == digest
                sources.add(repo/relative)
            report['reports'][name] = dict(path=(locations[name]/'report.json').relative_to(args.workspace).as_posix(),
                sha256=sha(locations[name]/'report.json'), result=value['result'])
        prior = args.workspace/'references/analysis/bounded_clock_pair_v1/final1'
        for filename in ('C_files_sha256.json', 'voice_files_sha256.json'):
            hashes = load(prior/filename)
            assert all(sha(repo/path) == digest for path, digest in hashes.items())
            shutil.copy2(prior/filename, final/filename)
        assert len(load(final/'C_files_sha256.json')) == 540
        subprocess.run(['git', 'diff', '--exit-code', 'HEAD', '--', 'src', 'modules', 'experiments', 'voices', 'CMakeLists.txt'],
                       cwd=repo, capture_output=True, check=True)
        assert not list(base.rglob('*.model'))
        for source in sources:
            relative = source.relative_to(repo)
            destination = final/'exact_sources'/relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            report['sources'][relative.as_posix()] = sha(source)
        shutil.copy2(args.workspace/'AGENTS.md', final/'data_workspace_AGENTS.md')
        assert sha(base/'pair1/bounded_envelope_pairs.png') == pair['plot_sha256']
        shutil.copy2(base/'pair1/bounded_envelope_pairs.png', final/'bounded_envelope_pairs.png')
        report.update(result='audited_finite_envelope_compensation_published_not_phase_qualification',
            pairs=[dict(id=row['id'], before=row['raw_difference_norm_before'], after=row['raw_difference_norm_after'],
                relative_norm_reduction=1-row['raw_difference_norm_after']/row['raw_difference_norm_before'],
                certificate=row['fit']['certificate'], primal_polish_attempted=row['fit']['qp']['primal_polish_attempted'],
                fixed_hypothesis_fresh_noise_distance=row['fixed_hypothesis_distance_under_fresh_white_noise']) for row in pair['cases']],
            analytic_controls_passed=True, all_original_constraints_and_raw_gradients_audited=True,
            independent_cases=audit['cases'], independent_Fejer_partition_error=audit['independent_Fejer_partition_error'],
            real_audio_read=False, truth_used=False, heldout_used=False, nonlinear_phase_estimator_run=False,
            constant_angles_and_common_phase_fixed=True, amplitude_variables=612,
            joint_angle_and_amplitude_compensation_examined=False,
            original17_rerun=False, full33_replaced=False, individual14kHz_demonstrated=False,
            phase_extracted_real_model_permitted=False, model_exported=False, runtime_changed=False,
            C_H=540, existing_Ctests_rerun=False, moving35='held_unchanged',
            F1_F2_F3='approved_and_acquired_in_state_media_v1', A_low_listening='original_question_pending',
            idle_acceleration_complete=False, vehicle_timbre_accepted=False,
            C_hashes_sha256=sha(final/'C_files_sha256.json'), voice_hashes_sha256=sha(final/'voice_files_sha256.json'),
            next_step='If continuing finite stability diagnosis, jointly compensate fixed common-phase pairs with constant angles and bounded slow amplitudes; no global nuisance lower-bound claim. Keep failed dense36/all17/full33/individual14kHz/original E before real phase-extracted models. Qualify F source actions and audio quality separately.',
            limits=pair['limitations'], goal_complete=False)
        save(summary, report)
    except Exception as exc:
        report.update(result='failed', error=repr(exc))
        raise
    finally:
        save(final/'report.json', report)
    print(json.dumps(dict(result=report['result'], C_H=540, real_models=0)), flush=True)
else:
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=repo).strip()
    report = load(summary)
    assert report['result'] == 'audited_finite_envelope_compensation_published_not_phase_qualification'
    assert sha(summary) == sha(final/'report.json')
    for relative, digest in report['sources'].items():
        assert sha(repo/relative) == sha(final/'exact_sources'/relative) == digest
    for row in report['reports'].values():
        assert sha(args.workspace/row['path']) == row['sha256']
    out = args.workspace/'baselines/bounded_envelope_pair_v1'
    out.mkdir(exist_ok=False)
    shutil.copytree(base, out/'evidence')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
    subprocess.run(['git', 'archive', '--format=zip', '--output='+str(out/'source.zip'), commit], cwd=repo, check=True)
    with zipfile.ZipFile(out/'source.zip') as archive:
        assert archive.testzip() is None
    files = [dict(path=path.relative_to(out).as_posix(), bytes=path.stat().st_size, sha256=sha(path))
             for path in sorted(out.rglob('*')) if path.is_file()]
    prior = args.workspace/'baselines/bounded_clock_pair_v1/manifest.json'
    save(out/'manifest.json', dict(schema='vsl.freeze/1', source_commit=commit, files=files,
        goal_complete=False, profiles_exported=0, vehicle_timbre_accepted=False, real_audio_read=False,
        prior_bounded_clock_pair_manifest=prior.relative_to(args.workspace).as_posix(),
        prior_bounded_clock_pair_manifest_sha256=sha(prior)))
    assert all(sha(out/row['path']) == row['sha256'] for row in files)
    print(json.dumps(dict(result='frozen', commit=commit, files=len(files), bytes=sum(row['bytes'] for row in files),
        manifest_sha256=sha(out/'manifest.json'))), flush=True)
