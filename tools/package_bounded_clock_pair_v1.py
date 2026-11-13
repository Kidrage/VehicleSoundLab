"""Freeze finite model-pair diagnostics and separately scoped approved F3 identity evidence."""
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
base = args.workspace/'references/analysis/bounded_clock_pair_v1'
media = args.workspace/'references/analysis/F3_passage_identity_v1'
final = base/'final1'
summary = repo/'research/bounded_clock_pair_v1_summary.json'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n',
                    encoding='utf-8', newline='\n')


if args.stage == 'publish':
    final.mkdir(exist_ok=False)
    report = dict(schema='vsl.bounded-clock-pair-publication/1', result='running', sources={}, reports={})
    try:
        locations = dict(pair2=base/'pair2', audit1=base/'audit1', F3_match1=media/'match1', F3_audit1=media/'audit1')
        items = {name: load(path/'report.json') for name, path in locations.items()}
        pair, audit, identity, identity_audit = (items[name] for name in locations)
        assert pair['result'] == 'finite_bounded_clock_pairs_measured_not_phase_qualification'
        assert pair['controls']['passed'] and all(row['feasible'] for row in pair['cases'])
        assert audit['result'] == 'finite_pairs_controls_and_original_serialization_failure_independently_reconstructed'
        assert audit['pairs_and_controls_exact'] and audit['failed_attempt_all_arrays_exact']
        assert audit['candidate_report_sha256'] == sha(base/'pair2/report.json')
        assert audit['preserved_failure_reproduced']['type'] == 'TypeError'
        assert identity['result'] == 'no_direct_integer_shift_copy_established'
        assert not identity['copy_evidence_gates_passed'] and not identity['independent_take_established']
        assert identity_audit['result'] == 'F3_source_slices_controls_and_fixed_lag_identity_measurements_reconstructed'
        assert identity_audit['candidate_report_sha256'] == sha(media/'match1/report.json')
        assert identity_audit['all_slices_and_measurements_exact']
        assert identity['real_audio_read'] and identity_audit['real_audio_read']
        assert not pair['real_audio_read'] and not audit['real_audio_read']
        sources = {Path(__file__), repo/'AGENTS.md', repo/'handoff/算法说明.md', repo/'handoff/研究续接.md',
            repo/'handoff/开发留痕.md', repo/'research/怠速与加速完成度V1.md',
            repo/'research/F补充素材可用性V1.md', repo/'research/有限相位与声线补偿V1.md',
            repo/'research/F3加速音轨复用核查V1.md'}
        for name, value in items.items():
            assert not value['model_exported'] and not value['runtime_changed']
            for relative, digest in value['sources'].items():
                assert sha(repo/relative) == sha(locations[name]/'exact_sources'/relative) == digest
                sources.add(repo/relative)
            report['reports'][name] = dict(path=(locations[name]/'report.json').relative_to(args.workspace).as_posix(),
                sha256=sha(locations[name]/'report.json'), result=value['result'])
        recovered = load(base/'pair1/recovered_failure.json')
        assert recovered['recovered_metadata'] and not recovered['original_report_saved']
        assert not (base/'pair1/report.json').exists()
        variants = {}
        for relative, digest in pair['sources'].items():
            earlier = base/'pair1/exact_sources'/relative
            if relative == 'tools/bounded_clock_pair_v1/checks.py':
                assert earlier.read_text(encoding='utf-8').replace('columns=rank)', 'columns=int(rank))') == (repo/relative).read_text(encoding='utf-8')
                variants[relative] = dict(pair1_sha256=sha(earlier), pair2_sha256=digest,
                    change='Native integer serialization only; all pair/control arrays independently exact')
            else:
                assert sha(earlier) == digest
        prior = args.workspace/'references/analysis/model_score_v1/final1'
        for filename in ('C_files_sha256.json', 'voice_files_sha256.json'):
            hashes = load(prior/filename)
            assert all(sha(repo/path) == digest for path, digest in hashes.items())
            shutil.copy2(prior/filename, final/filename)
        assert len(load(final/'C_files_sha256.json')) == 540
        subprocess.run(['git', 'diff', '--exit-code', 'HEAD', '--', 'src', 'modules', 'experiments', 'voices', 'CMakeLists.txt'],
                       cwd=repo, capture_output=True, check=True)
        assert not list(base.rglob('*.model')) and not list(media.rglob('*.model'))
        for source in sources:
            relative = source.relative_to(repo)
            target = final/'exact_sources'/relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            report['sources'][relative.as_posix()] = sha(source)
        shutil.copy2(args.workspace/'AGENTS.md', final/'data_workspace_AGENTS.md')
        for directory, filename, value in ((base/'pair2', 'bounded_clock_pairs.png', pair),
                                           (media/'match1', 'F3_passage_identity.png', identity)):
            assert sha(directory/filename) == value['plot_sha256']
            shutil.copy2(directory/filename, final/filename)
        report.update(result='finite_clock_compensation_and_F3_identity_evidence_published_not_phase_qualification',
            pair_construction=pair['construction'], pair_controls=pair['controls'], pairs=pair['cases'],
            pair_audit_exact=True, independent_Gaussian_checks=audit['independent_Gaussian_checks'],
            recovered_failure=recovered, original_failure_reproduced=audit['preserved_failure_reproduced'],
            preserved_source_variants=variants, F3_controls=identity['controls'], F3_measurement=identity['measurement'],
            F3_source_master=identity['source_master'], F3_source_master_sha256=identity['source_master_sha256'],
            F3_inspection_report_sha256=identity['source_inspection_report_sha256'],
            F3_original_master_unchanged=True, F3_direct_copy_established=False, F3_independent_take_established=False,
            F3_audit_exact=True, phase_diagnostic_real_audio_read=False, approved_F3_source_audio_read=True,
            nonlinear_estimator_run=False, original17_rerun=False, full33_replaced=False,
            individual14kHz_demonstrated=False, phase_extracted_real_model_permitted=False,
            model_exported=False, runtime_changed=False, C_H=540, existing_Ctests_rerun=False,
            moving35='held_unchanged', F1_F2_F3='approved_and_acquired_in_state_media_v1',
            A_low_listening='original_question_pending', idle_acceleration_complete=False,
            vehicle_timbre_accepted=False, C_hashes_sha256=sha(final/'C_files_sha256.json'),
            voice_hashes_sha256=sha(final/'voice_files_sha256.json'),
            previous_goal_turn_classification='progress_actual_score_geometry_rejection_replay_and_conditioning',
            goal_turn_classification='progress_actual_bounded_finite_pairs_independent_audits_and_approved_F3_waveform_identity_evidence',
            next_step='Original-bound slow-envelope finite compensation with complete certificates; keep failed dense36/all17/full33/individual14kHz/original E. Qualify F source actions and listening quality before actual state fitting; no independent-take or AV claim from direct-copy failure',
            limits=[*pair['limitations'], *identity['limitations']], goal_complete=False)
        save(summary, report)
    except Exception as exc:
        report.update(result='failed', error=repr(exc))
        raise
    finally:
        save(final/'report.json', report)
    print(json.dumps(dict(result=report['result'], real_models=0, C_H=540)), flush=True)
else:
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=repo).strip()
    report = load(summary)
    assert report['result'] == 'finite_clock_compensation_and_F3_identity_evidence_published_not_phase_qualification'
    assert sha(summary) == sha(final/'report.json')
    for relative, digest in report['sources'].items():
        assert sha(repo/relative) == sha(final/'exact_sources'/relative) == digest
    for row in report['reports'].values():
        assert sha(args.workspace/row['path']) == row['sha256']
    assert sha(args.workspace/report['F3_source_master']) == report['F3_source_master_sha256']
    out = args.workspace/'baselines/bounded_clock_pair_v1'
    out.mkdir(exist_ok=False)
    shutil.copytree(base, out/'evidence')
    shutil.copytree(media, out/'F3_identity_evidence')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
    subprocess.run(['git', 'archive', '--format=zip', '--output='+str(out/'source.zip'), commit], cwd=repo, check=True)
    with zipfile.ZipFile(out/'source.zip') as archive:
        assert archive.testzip() is None
    files = [dict(path=path.relative_to(out).as_posix(), bytes=path.stat().st_size, sha256=sha(path))
             for path in sorted(out.rglob('*')) if path.is_file()]
    prior = args.workspace/'baselines/model_score_v1/manifest.json'
    save(out/'manifest.json', dict(schema='vsl.freeze/1', source_commit=commit, files=files,
        goal_complete=False, profiles_exported=0, vehicle_timbre_accepted=False,
        phase_diagnostic_real_audio_read=False, approved_F3_source_audio_read=True,
        prior_model_score_manifest=prior.relative_to(args.workspace).as_posix(), prior_model_score_manifest_sha256=sha(prior)))
    assert all(sha(out/row['path']) == row['sha256'] for row in files)
    print(json.dumps(dict(result='frozen', commit=commit, files=len(files), bytes=sum(row['bytes'] for row in files))), flush=True)
