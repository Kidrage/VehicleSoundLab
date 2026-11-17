"""Freeze catalog identity and actual V13 lifecycle UI evidence as an explicit delta."""
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess
from urllib.request import urlopen

from research_archive_v1 import load, save, sha
from vehicle_controller.catalog_assets import inventory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze',type=Path,required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    data = Path('E:/VehicleSoundLab')
    root = data/'references/analysis/catalog_asset_identity_v1'
    base = data/'baselines/start_idle_lifecycle_v1/delivery1'
    assert not args.freeze.exists()
    assert sha(base/'manifest.json') == '677f361054150d15a6a6972410a23ceefd34379994f3305242a5ba703694ed9b'
    names = dict(identity='verification1/report.json',lifecycle='lifecycle1/report.json',
        controller='ui2/report.json',launch='launch2/report.json',browser='review-web1/verification.json')
    checks = {key:load(root/name) for key,name in names.items()}
    assert all(c['result'] == 'passed' for c in checks.values())
    digest,assets = inventory(repo)
    assert len(assets['files']) == 92
    for name in ('identity','lifecycle','controller'):
        assert checks[name]['catalog_assets_sha256'] == digest
    assert checks['launch']['ready']['catalog_assets_sha256'] == digest
    assert checks['controller']['flows'] == 2 and checks['controller']['frames_each'] == 36*48000
    assert checks['controller']['actual_complete_flow_button'] and checks['controller']['underflows_each'] == 0
    assert checks['controller']['terminal_controls_enabled'] and checks['controller']['stopped_state_has_no_idle_label']
    assert checks['controller']['own_window_closed']
    assert checks['launch']['own_window_closed'] and checks['launch']['own_service_closed']
    assert checks['launch']['browser']['actual_workbench_click'] and checks['launch']['no_audio_autoplay']
    assert checks['browser']['own_service_closed'] and len(checks['browser']['browser']['decoded']) == 8
    assert all(c['native_23channels_exact'] and c['monitor_exact'] and c['notices_state_exact'] and
        c['actual_native_process_calls'] == 4552 for c in checks['lifecycle']['cases'].values())
    assert load(root/'ui1/report.json')['result'] == 'passed'
    assert load(root/'launch1/report.json')['result'] == 'passed'
    bridge = repo/'build-vehicle-source-v12/bin/Release/vsl_source_bridge.dll'
    expected_binary = '97cff42c3244d15f4a48e11026737e92a6427bcdb8201a944ed9e6f33f577b9f'
    assert sha(bridge) == checks['lifecycle']['bridge_sha256'] == checks['controller']['bridge_sha256'] == expected_binary
    old_runtime = data/'baselines/A_exterior_startup_v1/delivery1/evidence/selection1/runtime.json'
    runtime = load(old_runtime)
    current = {p.relative_to(repo).as_posix():sha(p) for group in ('src','modules','voices')
        for p in (repo/group).rglob('*') if p.is_file() and (p.suffix in ('.c','.h') or group == 'voices')}
    assert current == runtime and len(current) == 459
    save(root/'runtime.json',current)
    save(root/'catalog-assets.json',assets)
    executed = {
        'tools/verify_catalog_assets_v1.py':'verification1/executed_verification.py',
        'tools/rebind_start_idle_catalog_v1.py':'lifecycle1/executed_verification.py',
        'tools/verify_catalog_controller_v13.py':'ui2/executed_verification.py',
        'tools/verify_catalog_launch_v13.py':'launch2/executed_verification.py',
        'tools/verify_catalog_launch_v13.cjs':'launch2/executed_browser.cjs',
        'tools/verify_start_idle_review_v1.py':'review-web1/executed_verification.py'}
    assert all(sha(repo/name) == sha(root/evidence) for name,evidence in executed.items())
    for name in ('controller-preset.json','full.take.json'):
        assert sha(root/'lifecycle1/review'/name) == sha(root/'review-web1/browser'/name)
    screenshots = ['ui2/controls.png','ui2/complete-flow.png','ui2/replayed.png',
        'launch2/independent-window.png','launch2/browser/workbench.png',
        'review-web1/browser/desktop.png','review-web1/browser/mobile.png']
    save(root/'visual-review.json',dict(result='passed',method='Each exact screenshot opened and visually inspected by the agent',
        files={name:sha(root/name) for name in screenshots},
        observations=['Compact controller controls readable; terminal flow/replay buttons enabled and stopped label correct',
            'Workbench retains an independent-window action and opens one stopped source-only controller',
            'Eight-track review and parameter downloads readable at desktop and390px width']))
    url = 'http://127.0.0.1:8789/references/analysis/catalog_asset_identity_v1/lifecycle1/review/index.html'
    with urlopen(url,timeout=5) as response:
        published = hashlib.sha256(response.read()).hexdigest()
        assert response.status == 200 and published == sha(root/'lifecycle1/review/index.html')
    save(root/'published-review.json',dict(url=url,HTTP_status=200,sha256=published,persistent_service_restarted=False))
    sources = {'AGENTS.md','handoff/当前代码阅读入口.md','handoff/完整资产身份与控制台V13.md',
        'research/catalog_asset_identity_v1_plan.json','tools/finalize_catalog_assets_v1.py',
        'tools/audit_catalog_assets_delivery_v1.py','tools/research_archive_v1.py',
        'tools/verify_low_mid_event_review_v1.cjs','tools/verify_startup_handoff_review_v1.py',
        'tools/event_review.py','tools/sound_designer/controller.py','tools/run_vehicle_controller.py',
        'Launch-Vehicle-Controller.cmd'}
    sources.update(executed)
    for directory in ('tools/vehicle_controller','tools/vehicle_scenarios'):
        sources.update(p.relative_to(repo).as_posix() for p in (repo/directory).rglob('*.py'))
    subprocess.run(['git','diff','--check'],cwd=repo,check=True)
    milestone = dict(schema='vsl.catalog-assets-milestone/1',result='passed',goal_complete=False,
        previous_goal_turn='No synthesis progress: only source/render/MCPS scope clarification',
        current_goal_turn='Complete runtime asset identity; actual36s UI lifecycle and saved device replay; bounded workbench launch',
        checks={key:dict(path=str(root/name),sha256=sha(root/name),result='passed') for key,name in names.items()},
        catalog_assets_sha256=digest,catalog_asset_files=92,runtime_voice_files_unchanged=459,formal_voices_unchanged=89,
        bridge_sha256=expected_binary,source_ABI=11,author_ABI=4,ui_revision=13,preset_schema=8,take_schema=9,
        source_files={name:sha(repo/name) for name in sorted(sources)},
        base_freeze=str(base),base_manifest_sha256=sha(base/'manifest.json'),freeze=str(args.freeze),
        published_review=load(root/'published-review.json'),source_only=True,
        compatibility='Old preset7/take8 remain with frozen V12 Python and original inputs; no implicit migration.',
        new_timbre_accepted=False,physical_afterfire_confirmed=False,
        unresolved=['startup/idle mechanical listening quality','confirmed complete physical afterfire and other event timbres',
                    'full RPM/load/state coverage'],
        new_download=False,commit_or_push=False,spatial_added=False,ADI_optimization=False,persistent_service_restarted=False)
    save(repo/'research/catalog_asset_identity_v1_verification.json',milestone)
    sources.add('research/catalog_asset_identity_v1_verification.json')
    args.freeze.mkdir(parents=True,exist_ok=False)
    for name in sorted(sources):
        target = args.freeze/'repo'/name
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(repo/name,target)
    shutil.copytree(root,args.freeze/'evidence',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    rows = [dict(path=p.relative_to(args.freeze).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
        for p in sorted(args.freeze.rglob('*')) if p.is_file()]
    save(args.freeze/'manifest.json',dict(schema='vsl.catalog-assets-delta-freeze/1',
        base_freeze=str(base),base_manifest_sha256=sha(base/'manifest.json'),files=rows,goal_complete=False))
    print(dict(result='frozen',files=len(rows),bytes=sum(r['bytes'] for r in rows),manifest_sha256=sha(args.freeze/'manifest.json')),flush=True)


if __name__ == '__main__':
    main()
