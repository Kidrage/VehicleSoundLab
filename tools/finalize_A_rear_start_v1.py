"""Freeze exterior startup authoring and the executed C/workbench evidence."""
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
    root = data/'references/analysis/A_exterior_startup_v1'
    base = data/'baselines/event_full_envelope_v1/delivery1'
    assert not args.freeze.exists()
    assert sha(base/'manifest.json') == '0114cbcbf8af99362de389b7b7f00eea569b75229b9976306349faccc2abbcc2'
    names = dict(selection='selection1/report.json', solver='solver-verification4/report.json',
        sources='verification5/report.json', workbench='web1/verification.json',
        driver='C1/report.json', native='C-audit1/report.json', ui='ui1/report.json',
        browser='review-web3/verification.json')
    checks = {key: load(root/name) for key, name in names.items()}
    assert all(row['result'] == 'passed' for row in checks.values())
    runtime = load(root/'selection1/runtime.json')
    assert runtime == load(base/'evidence/before/runtime.json')
    current = {p.relative_to(repo).as_posix(): sha(p) for group in ('src', 'modules', 'voices')
               for p in (repo/group).rglob('*') if p.is_file() and (p.suffix in ('.c', '.h') or group == 'voices')}
    assert current == runtime and len(runtime) == 459
    assert len([name for name in runtime if name.startswith('voices/')]) == 89
    exact = root/'catch7/exact_sources'
    for path in exact.glob('*.py'):
        source = repo/'tools/author_event.py' if path.name == 'author_event.py' else repo/'tools/event_authoring'/path.name
        assert sha(source) == sha(path), str(source)
    executed = {
        'tools/prepare_A_rear_start_v1.py': 'selection1/executed_preparation.py',
        'tools/verify_contour_joint_response_v1.py': 'solver-verification4/executed_verification.py',
        'tools/verify_A_rear_start_v1.py': 'verification5/executed_verification.py',
        'tools/verify_A_rear_workbench_v1.py': 'web1/executed_verification.py',
        'tools/build_A_rear_start_v1.py': 'C1/executed_build.py',
        'tools/audit_A_rear_driver_v1.py': 'C-audit1/executed_audit.py',
        'tools/verify_A_rear_controller_v1.py': 'ui1/executed_verification.py',
        'tools/verify_A_rear_review_v1.py': 'review-web3/executed_verification.py'}
    assert all(sha(repo/name) == sha(root/path) for name, path in executed.items())
    assert checks['workbench']['actual_job9_extraction_parameters_exact']
    assert checks['workbench']['source_free_import_C_PCM_exact']
    assert checks['native']['continuous_19channels_exact']
    assert checks['native']['catch_0_25_only_control_level_differs']
    assert checks['native']['source_only']
    assert checks['ui']['own_window_closed'] and checks['ui']['parameter_roundtrip_exact']
    assert all(row['underflows'] == 0 for row in checks['ui']['cases'])
    assert checks['browser']['own_service_closed']
    assert all(row['native_23channels_exact'] and row['monitor_exact'] and row['notices_state_exact']
               and row['event_peak'] <= 4 for row in checks['native']['captures'].values())
    profiles = checks['sources']['profiles']
    assert len(profiles['crank']['seeds']) == 4 and len(profiles['catch']['seeds']) == 8
    assert [row['seed'] for row in profiles['catch']['seeds'][4:]] == [13007, 90419, 58211, 71237]
    samples = [row for profile in profiles.values() for row in profile['seeds']]
    assert all(row['all_spectral_gates_pass'] for row in samples)
    max_error = max(row['C_python_max_error_FS'] for row in samples)
    assert max_error < 3e-7
    assert checks['selection']['source_sha256'] == sha(data/'references/clean/A_decoded_float.wav')
    bridge = repo/'build-vehicle-source-v12/bin/Release/vsl_source_bridge.dll'
    # The author Renderer selects the current build path; do not assume its name.
    from event_authoring.native import Renderer
    renderer = Renderer(repo)
    assert renderer.identity == checks['sources']['author_bridge_sha256']
    assert sha(bridge) == checks['driver']['bridge_sha256'] == checks['ui']['bridge_sha256']
    tracks = load(root/'C1/review/tracks.json')
    assert len(tracks) == 11
    assert all(sha(root/'C1/review'/row['file']) == row['sha256'] for row in tracks)
    url = 'http://127.0.0.1:8789/references/analysis/A_exterior_startup_v1/C1/review/index.html'
    with urlopen(url, timeout=5) as response:
        digest = hashlib.sha256(response.read()).hexdigest()
        assert response.status == 200 and digest == sha(root/'C1/review/index.html')
    save(root/'published-review.json', dict(url=url, HTTP_status=200, sha256=digest,
        persistent_service_restarted=False))
    failures = {}
    for folder in ('catch1', 'catch2', 'catch3', 'catch4', 'catch5', 'catch6',
                   'verification1', 'verification2', 'verification3', 'verification4',
                   'solver-verification1', 'review-web1', 'review-web2'):
        assert (root/folder).is_dir(), folder
        paths = [p for p in (root/folder).rglob('*') if p.is_file() and p.suffix != '.pyc']
        failures[folder] = dict(preserved_files=len(paths),
            machine_reports=[p.relative_to(root).as_posix() for p in paths
                             if p.name in ('report.json', 'verification.json')],
            machine_evidence_available=bool(paths), promoted=False)
    save(root/'preserved-attempts.json', dict(attempts=failures,
        limitation='Some interrupted attempts have no machine-readable terminal report. Their files are preserved; no missing logs are reconstructed.'))
    sources = {'AGENTS.md', 'handoff/当前代码阅读入口.md', 'handoff/车外启动与同步包络提参V1.md',
        'research/A_exterior_startup_v1_plan.json', 'research/A_exterior_startup_v1_selection.json',
        'research/A_exterior_startup_v1_timeline.json', 'tools/author_event.py', 'tools/event_review.py',
        'tools/research_archive_v1.py', 'tools/finalize_A_rear_start_v1.py',
        'tools/verify_event_joint_web_v1.cjs', 'tools/verify_low_mid_event_review_v1.cjs',
        'tools/verify_startup_handoff_review_v1.py'}
    sources.update(executed)
    for group in ('event_authoring', 'event_designer', 'vehicle_controller', 'vehicle_scenarios', 'sound_designer'):
        sources.update(p.relative_to(repo).as_posix() for p in (repo/'tools'/group).rglob('*')
                       if p.is_file() and p.suffix in ('.py', '.cjs', '.js', '.html', '.css', '.json'))
    subprocess.run(['git', 'diff', '--check'], cwd=repo, check=True)
    milestone = dict(schema='vsl.exterior-startup-joint-authoring-milestone/1', result='passed',
        previous_goal_turn='No synthesis progress: source/render scope and MCPS confirmation only',
        current_goal_turn='Finalize executed exterior startup, joint temporal/spectral authoring and C/controller/workbench delivery',
        checks={key: dict(path=str(root/name), sha256=sha(root/name), result='passed') for key, name in names.items()},
        source_ABI=11, author_ABI=4, profile_bytes=1408, preset_schema=7, take_schema=8,
        runtime_voice_files_unchanged=459, formal_voices_unchanged=89,
        runtime_binding_sha256=sha(root/'selection1/runtime.json'), bridge_sha256=sha(bridge),
        author_bridge_sha256=renderer.identity, C_python_max_error_FS=max_error,
        unscaled_event_max_peak=max(row['peak'] for row in samples),
        C_selection_seed_counts=dict(crank=4, catch=4), C_independent_catch_seed_count=4,
        editable_project=checks['workbench']['actual_editable_project'],
        source_files={name: sha(repo/name) for name in sorted(sources)},
        published_review=load(root/'published-review.json'),
        base_freeze=str(base), base_manifest_sha256=sha(base/'manifest.json'), freeze=str(args.freeze),
        new_timbre_accepted=False, physical_source_separated=False, physical_RPM_identified=False,
        goal_complete=False, new_download=False, commit_or_push=False, spatial_added=False,
        ADI_optimization=False, persistent_service_restarted=False,
        unresolved=['startup/idle mechanical naturalness and hearing', 'confirmed complete physical afterfire',
                    'other independent event timbres', 'full RPM/load/state coverage',
                    'later startup acoustic interval may duplicate continuous DNA'])
    save(repo/'research/A_exterior_startup_v1_verification.json', milestone)
    sources.add('research/A_exterior_startup_v1_verification.json')
    args.freeze.mkdir(parents=True, exist_ok=False)
    for name in sorted(sources):
        target = args.freeze/'repo'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo/name, target)
    shutil.copytree(root, args.freeze/'evidence', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    rows = [dict(path=p.relative_to(args.freeze).as_posix(), bytes=p.stat().st_size, sha256=sha(p))
            for p in sorted(args.freeze.rglob('*')) if p.is_file()]
    save(args.freeze/'manifest.json', dict(schema='vsl.exterior-startup-joint-authoring-delta-freeze/1',
        base_freeze=str(base), base_manifest_sha256=sha(base/'manifest.json'), files=rows, goal_complete=False))
    print(dict(result='frozen', files=len(rows), bytes=sum(row['bytes'] for row in rows),
        manifest_sha256=sha(args.freeze/'manifest.json'), C_python_max_error_FS=max_error), flush=True)


if __name__ == '__main__':
    main()
