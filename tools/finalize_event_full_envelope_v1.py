"""Freeze complete-interval authoring, real C/UI evidence and source bindings."""
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess
from urllib.request import urlopen

from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--freeze', type=Path, required=True)
    args = p.parse_args()
    repo = Path(__file__).resolve().parents[1]
    data = Path('E:/VehicleSoundLab')
    root = data/'references/analysis/event_full_envelope_v1'
    base = data/'baselines/low_mid_event_scan_v1/delivery1'
    assert not args.freeze.exists()
    assert sha(base/'manifest.json') == '502493287d8a926d40318f36a5a1f41db7c147fed79a6d6726bc2d1f7933de8f'
    names = dict(fitting='verification1/report.json', independent_spectra='audit1/report.json',
        workbench='web1/verification.json', driver='C4/report.json', native='C-audit1/report.json',
        browser='review-web1/verification.json', ui='ui1/report.json',
        A_selection='A-selection1/report.json', A_reuse='A-reuse1/report.json')
    checks = {key: load(root/name) for key, name in names.items()}
    assert all(value['result'] == 'passed' for value in checks.values())
    runtime = load(root/'before/runtime.json')
    assert runtime == load(base/'evidence/before/runtime.json')
    current = {p.relative_to(repo).as_posix(): sha(p) for group in ('src', 'modules', 'voices')
               for p in (repo/group).rglob('*') if p.is_file() and (p.suffix in ('.c', '.h') or group == 'voices')}
    assert current == runtime and len(runtime) == 459
    assert len([name for name in runtime if name.startswith('voices/')]) == 89
    exact = root/'verification1/candidate/analysis/exact_sources'
    for path in exact.glob('*.py'):
        source = repo/'tools/author_event.py' if path.name == 'author_event.py' else repo/'tools/event_authoring'/path.name
        assert sha(source) == sha(path), str(source)
    executed = {
        'tools/build_event_full_envelope_v1.py': root/'C4/executed_build.py',
        'tools/audit_event_full_driver_v1.py': root/'C-audit1/executed_audit.py',
        'tools/verify_event_full_envelope_v1.py': root/'verification1/executed_verification.py',
        'tools/verify_event_full_envelope_workbench_v1.py': root/'web1/executed_verification.py',
        'tools/verify_event_full_envelope_review_v1.py': root/'review-web1/executed_verification.py',
        'tools/verify_low_mid_event_ui_v1.py': root/'ui1/executed_verification.py',
        'tools/audit_A_low_mid_reuse_v1.py': root/'A-reuse1/executed_audit.py'}
    # Known/authoring verification stores its own source under this name.
    if not executed['tools/verify_event_full_envelope_v1.py'].is_file():
        executed['tools/verify_event_full_envelope_v1.py'] = root/'verification1/verify_event_full_envelope_v1.py'
    assert all(sha(repo/name) == sha(path) for name, path in executed.items())
    assert all(load(root/name/'report.json')['result'] == 'failed' for name in ('C1', 'C2', 'C3'))
    assert checks['workbench']['source_free_import_C_PCM_exact']
    assert checks['native']['continuous_19channels_exact']
    assert checks['ui']['own_window_closed'] and all(row['underflows'] == 0 for row in checks['ui']['cases'])
    assert checks['browser']['own_service_closed']
    assert checks['independent_spectra']['selected_band_indices'] == [0]
    rows = checks['independent_spectra']['results']
    old = [r['four_band_normalized_shape_rmse'] for r in rows if r['variant'] == 'original']
    new = [r['four_band_normalized_shape_rmse'] for r in rows if r['variant'] == 'candidate']
    assert len(old) == len(new) == 4
    assert all(b[0] < a[0] and b[1] > a[1] for a, b in zip(old, new))
    tracks = load(root/'C4/review/tracks.json')
    assert len(tracks) == 10 and all(sha(root/'C4/review'/r['file']) == r['sha256'] for r in tracks)
    url = 'http://127.0.0.1:8789/references/analysis/event_full_envelope_v1/C4/review/index.html'
    with urlopen(url, timeout=5) as response:
        digest = hashlib.sha256(response.read()).hexdigest()
        assert response.status == 200 and digest == sha(root/'C4/review/index.html')
    save(root/'published-review.json', dict(url=url, HTTP_status=200, sha256=digest,
        persistent_service_restarted=False))
    notes = load(repo/'research/A_low_mid_event_context_v1_notes.json')
    assert len(notes['cases']) == 4 and len(checks['A_selection']['selected']) == 4
    context_bindings = {}
    for row in notes['cases']:
        for name in ('dashboard.jpg', 'timeline.png', 'original.wav'):
            path = root/'A-contexts1'/row['name']/name
            context_bindings[path.relative_to(root).as_posix()] = sha(path)
    save(root/'context-bindings.json', context_bindings)
    sources = {'AGENTS.md', 'handoff/当前代码阅读入口.md', 'handoff/事件完整区间与四频段包络V1.md',
        'research/event_full_envelope_v1_plan.json', 'research/E_full_event_v1.job.json',
        'research/A_low_mid_event_search_v1_plan.json', 'research/A_low_mid_event_context_v1_notes.json',
        'tools/author_event.py', 'tools/research_archive_v1.py', 'tools/event_review.py',
        'tools/prepare_A_low_mid_context_v1.py', 'tools/inspect_event_timeline_v1.py',
        'tools/scan_approved_event_region.py', 'tools/verify_low_mid_event_review_v1.cjs',
        'tools/verify_startup_handoff_review_v1.py', 'tools/audit_event_full_envelope_v1.py',
        'tools/finalize_event_full_envelope_v1.py'}
    sources.update(executed)
    for group in ('event_authoring', 'event_designer', 'vehicle_controller', 'vehicle_scenarios', 'sound_designer'):
        sources.update(p.relative_to(repo).as_posix() for p in (repo/'tools'/group).rglob('*')
                       if p.is_file() and p.suffix in ('.py', '.cjs', '.js', '.html', '.css', '.json'))
    subprocess.run(['git', 'diff', '--check'], cwd=repo, check=True)
    milestone = dict(schema='vsl.complete-event-contour-milestone/1', result='passed',
        previous_goal_turn='No synthesis progress: generation/render scope and MCPS response only',
        current_goal_turn='Four-band offline authoring and complete E interval, C composition/UI/replay and original A context evidence',
        checks={key: dict(path=str(root/name), sha256=sha(root/name), result='passed') for key, name in names.items()},
        source_ABI=11, author_ABI=4, profile_bytes=1408, preset_schema=7, take_schema=8,
        runtime_voice_files_unchanged=459, formal_voices_unchanged=89,
        runtime_binding_sha256=sha(root/'before/runtime.json'),
        editable_project=checks['workbench']['actual_editable_project'],
        source_files={name: sha(repo/name) for name in sorted(sources)},
        published_review=load(root/'published-review.json'),
        base_freeze=str(base), base_manifest_sha256=sha(base/'manifest.json'), freeze=str(args.freeze),
        low_band_shape_improved=True, mid_band_shape_regressed=True,
        new_timbre_accepted=False, physical_identity_confirmed=False, goal_complete=False,
        new_download=False, commit_or_push=False, spatial_added=False, ADI_optimization=False,
        persistent_service_restarted=False,
        unresolved=['startup/idle mechanical naturalness', 'confirmed complete fullband afterfire',
                    'other independent event timbres', 'full RPM/load/state coverage', 'E middle-band temporal shape'])
    save(repo/'research/event_full_envelope_v1_verification.json', milestone)
    sources.add('research/event_full_envelope_v1_verification.json')
    args.freeze.mkdir(parents=True, exist_ok=False)
    for name in sorted(sources):
        destination = args.freeze/'repo'/name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo/name, destination)
    shutil.copytree(root, args.freeze/'evidence', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    rows = [dict(path=p.relative_to(args.freeze).as_posix(), bytes=p.stat().st_size, sha256=sha(p))
            for p in sorted(args.freeze.rglob('*')) if p.is_file()]
    save(args.freeze/'manifest.json', dict(schema='vsl.complete-event-contour-delta-freeze/1',
        base_freeze=str(base), base_manifest_sha256=sha(base/'manifest.json'), files=rows, goal_complete=False))
    print(dict(result='frozen', files=len(rows), bytes=sum(r['bytes'] for r in rows),
               manifest_sha256=sha(args.freeze/'manifest.json')), flush=True)


if __name__ == '__main__':
    main()
