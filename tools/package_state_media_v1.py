"""Publish and freeze approved-media retrieval, raw observations and visual state evidence."""
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

base = args.workspace/'references/analysis/state_media_v1'
raw = args.workspace/'references/raw/state_media_v1'
final = base/'final1'
summary = repo/'research/state_media_v1_summary.json'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n',
                    encoding='utf-8', newline='\n')


if args.stage == 'publish':
    final.mkdir(exist_ok=False)
    report = dict(schema='vsl.state-media-publication/1', result='running', sources={}, reports={})
    try:
        plan = load(repo/'research/approved_state_media_v1_plan.json')
        review = load(repo/'research/state_media_v1_visual_review.json')
        assert review['visual_review_completed'] and not review['audio_listening_completed']
        assert not review['idle_acceleration_complete']
        catalog = load(args.workspace/'references/approval_manifest.json')
        assert sum(row.get('approved') is True for row in catalog) == 7
        attempts = ['F1_fetch1', 'F1_fetch2', 'F2_fetch1', 'F3_fetch1', 'F3_fetch2']
        successful = ['F1_fetch2', 'F2_fetch1', 'F3_fetch2']
        for name in attempts:
            path = raw/name/'report.json'
            item = load(path)
            assert item['approval_evidence'] == plan['approval_evidence']
            assert sha(raw/name/'executed_fetch.py') == item['sources']['tools/fetch_approved_state_media_v1.py']
            assert sha(raw/name/'approved_plan.json') == item['sources']['research/approved_state_media_v1_plan.json']
            assert sha(raw/name/'approval_manifest.json') == item['approval_manifest_sha256']
            if name in successful:
                assert item['result'] == 'downloaded_for_usability_inspection'
                media = args.workspace/item['file']
                assert sha(media) == item['sha256'] and media.stat().st_size == item['bytes']
                if name != 'F2_fetch1':
                    assert item['resumed_copy']['original_attempt_preserved']
                    previous = raw/name.replace('fetch2', 'fetch1')
                    assert sha(previous/'report.json') == item['resumed_copy']['previous_report_sha256']
                    for value in item['resumed_copy']['files']:
                        assert sha(previous/value['file']) == value['sha256']
            else:
                assert item['result'] == 'retrieval_failed'
            report['reports'][name] = dict(path=path.relative_to(args.workspace).as_posix(),
                sha256=sha(path), result=item['result'], executed_fetch_sha256=sha(raw/name/'executed_fetch.py'))
        sources = {Path(__file__), repo/'tools/fetch_approved_state_media_v1.py',
            repo/'tools/inspect_F3_state_frames_v1.py', repo/'research/state_media_v1_visual_review.json',
            repo/'research/F补充素材可用性V1.md', repo/'research/怠速与加速完成度V1.md', repo/'AGENTS.md',
            repo/'handoff/算法说明.md', repo/'handoff/研究续接.md', repo/'handoff/开发留痕.md'}
        decoded = {}
        for identity in ('F1', 'F2', 'F3'):
            directory = base/(identity+'_inspect1')
            path = directory/'report.json'
            item = load(path)
            assert item['result'] == 'raw_recording_measured_and_coarse_video_prepared'
            assert not item['model_extracted'] and not item['runtime_changed'] and not item['timbre_accepted']
            assert sha(args.workspace/item['input_file']) == item['input_sha256']
            assert sha(directory/'native_reference.wav') == item['decoded']['sha256']
            assert not item['decoded']['normalized'] and not item['decoded']['resampled']
            assert sha(directory/'context.jpg') == item['context_sheet_sha256']
            assert sha(directory/'recording_observations.png') == item['plot_sha256']
            for relative, digest in item['sources'].items():
                assert sha(repo/relative) == sha(directory/'exact_sources'/relative) == digest
                sources.add(repo/relative)
            for frame in item['context']['frames']:
                assert sha(directory/frame['file']) == frame['sha256']
            decoded[identity] = item['measurements']
            report['reports'][identity+'_inspect1'] = dict(path=path.relative_to(args.workspace).as_posix(),
                sha256=sha(path), result=item['result'])
        detail_path = base/'F3_context1/report.json'
        detail = load(detail_path)
        assert detail['result'] == 'original_PTS_state_frames_prepared' and not detail['audio_read']
        assert sha(repo/'tools/inspect_F3_state_frames_v1.py') == sha(detail_path.parent/'executed_inspect.py') == detail['source_sha256']
        for name, value in detail['observations'].items():
            directory = detail_path.parent/name
            assert sha(directory/'context.jpg') == value['sheet_sha256']
            for frame in value['frames']:
                assert sha(directory/frame['file']) == frame['sha256']
        report['reports']['F3_context1'] = dict(path=detail_path.relative_to(args.workspace).as_posix(),
            sha256=sha(detail_path), result=detail['result'])
        prior = args.workspace/'references/analysis/native_observation_v1/final1'
        for filename in ('C_files_sha256.json', 'voice_files_sha256.json'):
            hashes = load(prior/filename)
            assert all(sha(repo/p) == digest for p, digest in hashes.items())
            shutil.copy2(prior/filename, final/filename)
        assert len(load(final/'C_files_sha256.json')) == 540
        for source in sources:
            relative = source.relative_to(repo)
            target = final/'exact_sources'/relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            report['sources'][relative.as_posix()] = sha(source)
        shutil.copy2(args.workspace/'AGENTS.md', final/'data_workspace_AGENTS.md')
        raw_files = [dict(path=path.relative_to(args.workspace).as_posix(),
                         bytes=path.stat().st_size, sha256=sha(path))
                     for path in sorted(raw.rglob('*')) if path.is_file()]
        save(final/'raw_files_sha256.json', raw_files)
        report.update(result='approved_F1_F2_F3_acquired_recording_and_state_evidence_only',
            approval=plan['approval_evidence'], total_approved_source_identities=7,
            successful_downloads=3, failed_attempts_preserved=2,
            coarse_frames=44, detailed_original_PTS_frames=65,
            visual_review_completed=True, audio_listening_completed=False,
            decoded_recordings=decoded, visual_review=review,
            raw_files_sha256=sha(final/'raw_files_sha256.json'),
            native_rate_decoding=True, normalization=False, denoising=False, resampling=False,
            new_DNA_profiles=0, runtime_changed=False, C_H=540,
            C_hashes_sha256=sha(final/'C_files_sha256.json'), voice_hashes_sha256=sha(final/'voice_files_sha256.json'),
            existing_Ctests_rerun=False, moving35='held_unchanged',
            idle_acceleration_complete=False, vehicle_timbre_accepted=False,
            new_phase_estimator_qualified=False,
            next_step='Preserve original phase qualification gates; confirm continuous F3 state boundaries/AV timing and local F2 usability before fitting separate car/perspective/state parameters',
            goal_complete=False)
        save(summary, report)
    except Exception as exc:
        report.update(result='failed', error=repr(exc))
        raise
    finally:
        save(final/'report.json', report)
    print(json.dumps(dict(result=report['result'], downloads=3, frames=109, new_DNA=0)), flush=True)
else:
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=repo).strip()
    report = load(summary)
    assert report['result'] == 'approved_F1_F2_F3_acquired_recording_and_state_evidence_only'
    assert sha(summary) == sha(final/'report.json')
    for relative, digest in report['sources'].items():
        assert sha(repo/relative) == sha(final/'exact_sources'/relative) == digest
    for row in load(final/'raw_files_sha256.json'):
        path = args.workspace/row['path']
        assert path.stat().st_size == row['bytes'] and sha(path) == row['sha256']
    out = args.workspace/'baselines/state_media_v1'
    out.mkdir(exist_ok=False)
    shutil.copytree(base, out/'evidence')
    shutil.copytree(raw, out/'raw')
    shutil.copytree(args.workspace/'references/approved/state_media_v1', out/'approval')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
    subprocess.run(['git', 'archive', '--format=zip', '--output='+str(out/'source.zip'), commit], cwd=repo, check=True)
    with zipfile.ZipFile(out/'source.zip') as archive:
        assert archive.testzip() is None
    files = [dict(path=path.relative_to(out).as_posix(), bytes=path.stat().st_size, sha256=sha(path))
             for path in sorted(out.rglob('*')) if path.is_file()]
    prior = args.workspace/'baselines/native_observation_v1/manifest.json'
    save(out/'manifest.json', dict(schema='vsl.freeze/1', source_commit=commit, files=files,
        prior_native_observation_manifest=prior.relative_to(args.workspace).as_posix(),
        prior_native_observation_manifest_sha256=sha(prior),
        goal_complete=False, new_DNA_profiles=0, vehicle_timbre_accepted=False))
    assert all(sha(out/row['path']) == row['sha256'] for row in files)
    print(json.dumps(dict(result='frozen', commit=commit, files=len(files),
                         bytes=sum(row['bytes'] for row in files))), flush=True)
