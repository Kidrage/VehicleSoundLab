"""Freeze the complementary detector and actual C/workbench/controller evidence."""
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess
from urllib.request import urlopen

from research_archive_v1 import load, save, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze', type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    data = Path('E:/VehicleSoundLab')
    root = data/'references/analysis/low_mid_event_scan_v1'
    f3 = data/'references/analysis/F3_event_context_v1'
    base = data/'baselines/event_knots_v1/delivery1'
    assert not args.freeze.exists() and (base/'manifest.json').is_file()
    names = dict(detector='verification2/report.json', candidate='C1/report.json',
                 independent='C-audit3/report.json', review='review-web1/verification.json', ui='ui1/report.json')
    checks = {key: load(root/name) for key, name in names.items()}
    assert all(row['result'] == 'passed' for row in checks.values())
    baseline = load(root/'before/runtime.json')
    current = {p.relative_to(repo).as_posix(): sha(p) for folder in ('src', 'modules', 'voices')
               for p in (repo/folder).rglob('*') if p.is_file() and (p.suffix in ('.c', '.h') or folder == 'voices')}
    assert len(current) == 459 and current == baseline
    old = base/'evidence/startup1/exact_sources'
    assert all(sha(old/name) == digest for name, digest in baseline.items())
    assert len([name for name in baseline if name.startswith('voices/')]) == 89
    executed = {
        'tools/build_low_mid_event_v1.py': root/'C1/executed_build.py',
        'tools/audit_low_mid_event_candidate_v1.py': root/'C-audit3/executed_audit.py',
        'tools/verify_low_mid_event_ui_v1.py': root/'ui1/executed_verification.py',
        'tools/verify_low_mid_event_review_v1.py': root/'review-web1/verify_low_mid_event_review_v1.py',
        'tools/verify_low_mid_event_review_v1.cjs': root/'review-web1/verify_low_mid_event_review_v1.cjs'}
    verified = ('tools/event_authoring/scan.py', 'tools/scan_approved_event_region.py',
        'tools/event_designer/candidates.py', 'tools/event_designer/workspace.py',
        'tools/sound_designer/web/events.html', 'tools/sound_designer/web/events.js',
        'tools/sound_designer/web/event_candidates.js')
    executed.update({name: root/'verification2/exact_sources'/name for name in verified})
    assert all(sha(repo/name) == sha(path) for name, path in executed.items())
    assert checks['independent']['runtime_voice_files_unchanged'] == 459
    assert len(checks['independent']['afterfire_slot_starts']) == 4
    assert all(row['underflows'] == 0 and row['frames'] == 384000 for row in checks['ui']['cases'])
    assert checks['ui']['own_window_closed'] and checks['review']['own_service_closed']
    assert checks['detector']['runtime_voice_files_unchanged'] == 459
    for name in ('C-audit1', 'C-audit2', 'verification1'):
        assert load(root/name/'report.json')['result'] == 'failed'
    f3_scan = load(f3/'scan1/report.json')
    f3_check = load(f3/'selection2/report.json')
    assert len(f3_scan['candidates']) == 585
    assert sum(row['both_full_band_above_3db'] for row in f3_scan['candidates']) == 31
    assert f3_check['result'] == 'passed' and f3_check['maximum_error_db'] < 1e-10
    assert not f3_check['known_candidate']['both_full_band_above_3db']
    notes = load(repo/'research/low_mid_event_context_notes_v1.json')
    assert len(notes['cases']) == 4
    context_bindings = {}
    for context_root in (root/'contexts1', f3/'contexts1', f3/'contexts2'):
        for folder in context_root.iterdir():
            if folder.is_dir() and (folder/'dashboard.jpg').is_file():
                assert (folder/'timeline.png').is_file()
                for name in ('dashboard.jpg', 'timeline.png'):
                    context_bindings[(folder/name).relative_to(data).as_posix()] = sha(folder/name)
    assert len(context_bindings) == 42
    tracks = load(root/'C1/review/tracks.json')
    assert len(tracks) == 9
    for row in tracks:
        assert row['gain'] == (.25 if row['frames'] < 384000 else 1.)
        assert sha(root/'C1/review'/row['file']) == row['sha256']
    url = 'http://127.0.0.1:8789/references/analysis/low_mid_event_scan_v1/C1/review/index.html'
    http = dict(url=url, persistent_service_restarted=False)
    try:
        with urlopen(url, timeout=5) as response:
            http.update(status=response.status, sha256=hashlib.sha256(response.read()).hexdigest())
        assert http['status'] == 200 and http['sha256'] == sha(root/'C1/review/index.html')
        http['exact'] = True
    except OSError as error:
        http.update(exact=False, error=repr(error))
    save(root/'published-review.json', http)
    save(root/'context-bindings.json', context_bindings)
    sources = {'AGENTS.md', 'handoff/当前代码阅读入口.md', 'handoff/低中频事件扫描与收油候选V1.md',
        'research/low_mid_event_scan_v1_plan.json', 'research/F3_event_context_v1_plan.json',
        'research/E_low_mid_event_v1.job.json', 'research/low_mid_event_context_notes_v1.json',
        'research/F3_event_context_v1_notes.json', 'tools/research_archive_v1.py', 'tools/event_review.py',
        'tools/scan_approved_event_region.py', 'tools/prepare_F3_event_context_v1.py',
        'tools/prepare_low_mid_event_context_v1.py', 'tools/verify_startup_handoff_review_v1.py'}
    sources.update(executed)
    for group in ('event_authoring', 'event_designer', 'vehicle_controller', 'vehicle_scenarios', 'sound_designer'):
        sources.update(p.relative_to(repo).as_posix() for p in (repo/'tools'/group).rglob('*')
                       if p.is_file() and p.suffix in ('.py', '.js', '.html', '.css', '.json'))
    sources.update(p.relative_to(repo).as_posix() for p in (repo/'tools').glob('*low_mid*v1*') if p.is_file())
    subprocess.run(['git', 'diff', '--check'], cwd=repo, check=True)
    milestone = dict(schema='vsl.complementary-event-detector-milestone/1', result='passed',
        previous_goal_turn='No progress: only generation/render scope and MCPS rechecked',
        current_goal_turn='Complementary low/mid detector/workbench, original-context evidence, actual C candidate and verified native/browser/controller consumption',
        checks={key: dict(path=str(root/name), sha256=sha(root/name), result='passed') for key, name in names.items()},
        source_ABI=11, author_ABI=4, profile_bytes=1408, preset_schema=7, take_schema=8,
        runtime_voice_files_unchanged=459, formal_voices_unchanged=89,
        runtime_binding_sha256=sha(root/'before/runtime.json'),
        editable_project=checks['candidate']['workbench'], afterfire_slot_starts=4,
        source_files={name: sha(repo/name) for name in sorted(sources)},
        context_bindings_sha256=sha(root/'context-bindings.json'), published_review=http,
        base_freeze=str(base), base_manifest_sha256=sha(base/'manifest.json'), freeze=str(args.freeze),
        limitations=['Acoustic detector is not a physical classifier or source separator',
            'E100ms crop is not the full onset/tail, afterfire is only a local audition slot',
            'Independent auditor scratch-buffer and normal crank-release false assumptions retained',
            'No new listening acceptance or full RPM/load/state coverage'],
        new_download=False, commit_or_push=False, spatial_added=False, ADI_optimization=False,
        persistent_service_restarted=False, new_timbre_accepted=False, physical_identity_confirmed=False,
        goal_complete=False, unresolved=['startup/idle mechanical naturalness', 'complete confirmed fullband afterfire',
                                       'other independent event timbres', 'full RPM/load/state coverage'])
    save(repo/'research/low_mid_event_scan_v1_verification.json', milestone)
    sources.add('research/low_mid_event_scan_v1_verification.json')
    args.freeze.mkdir(parents=True, exist_ok=False)
    for name in sorted(sources):
        target = args.freeze/'repo'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo/name, target)
    for source, target in ((root, args.freeze/'evidence'), (f3, args.freeze/'F3-evidence')):
        shutil.copytree(source, target, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    rows = [dict(path=p.relative_to(args.freeze).as_posix(), bytes=p.stat().st_size, sha256=sha(p))
            for p in sorted(args.freeze.rglob('*')) if p.is_file()]
    manifest = dict(schema='vsl.complementary-event-detector-delta-freeze/1', base_freeze=str(base),
                    base_manifest_sha256=sha(base/'manifest.json'), files=rows, goal_complete=False)
    save(args.freeze/'manifest.json', manifest)
    print(dict(result='frozen', files=len(rows), bytes=sum(row['bytes'] for row in rows),
               manifest_sha256=sha(args.freeze/'manifest.json'), public_review_exact=http['exact']), flush=True)


if __name__ == '__main__':
    main()
