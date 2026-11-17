"""Bind the real idle/lifecycle correction, unchanged assets and executed evidence."""
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess
from urllib.request import urlopen

from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--freeze',type=Path,required=True)
    args=p.parse_args()
    repo=Path(__file__).resolve().parents[1]
    data=Path('E:/VehicleSoundLab')
    root=data/'references/analysis/start_idle_lifecycle_v1'
    base=data/'baselines/A_exterior_startup_v1/delivery1'
    assert not args.freeze.exists()
    assert sha(base/'manifest.json')=='e9dc35e7c8b1baaf9b460519131911c77346a8bea19698ce4531e5ddf9d92eba'
    names=dict(driver='C3/report.json',native='C-audit2/report.json',
               browser='review-web2/verification.json',ui='ui1/report.json')
    checks={key:load(root/name) for key,name in names.items()}
    assert all(c['result']=='passed' for c in checks.values())
    runtime=load(base/'evidence/selection1/runtime.json')
    current={p.relative_to(repo).as_posix():sha(p) for group in ('src','modules','voices')
             for p in (repo/group).rglob('*') if p.is_file() and (p.suffix in ('.c','.h') or group=='voices')}
    assert runtime==current and len(runtime)==459
    assert sum(name.startswith('voices/') for name in runtime)==89
    assert checks['driver']['current_catalog']=='v10-moving-fine-idle'
    assert checks['driver']['control_trajectory_exact'] and checks['driver']['event_4channels_and_notices_exact']
    assert checks['driver']['idle_added_bus_proven'] and checks['driver']['source_only']
    assert all(row['monitor_peak'] < 1 for row in checks['driver']['measurements'].values())
    assert checks['ui']['own_window_closed'] and checks['ui']['underflows']==0
    assert checks['ui']['frames']==36*48000 and checks['ui']['idle_controls_enabled']
    assert checks['browser']['own_service_closed']
    assert len(checks['browser']['browser']['decoded'])==8
    bridge=repo/'build-vehicle-source-v12/bin/Release/vsl_source_bridge.dll'
    assert sha(bridge)==checks['driver']['bridge_sha256']==checks['ui']['bridge_sha256']
    executed={
        'tools/build_start_idle_lifecycle_v1.py':'C3/executed_build.py',
        'tools/vehicle_scenarios/start_idle.py':'C3/executed_scenario.py',
        'tools/audit_start_idle_lifecycle_v1.py':'C-audit2/executed_audit.py',
        'tools/verify_start_idle_controller_v1.py':'ui1/executed_verification.py',
        'tools/verify_start_idle_review_v1.py':'review-web2/executed_verification.py',
        'research/start_idle_lifecycle_v1_plan.json':'C3/plan.json'}
    assert all(sha(repo/name)==sha(root/path) for name,path in executed.items())
    original_idle=data/'baselines/fine_idle_drive_v1'
    assets=('experiments/modal_idle_v1/F2_fixed_idle.msource',
            'experiments/modal_texture_v1/F2_amplitude.mtexture',
            'experiments/spectral_texture_v1/F2_fine_static.sfir',
            'experiments/idle_state_v1/study.h')
    original_rows={r['path']:r['sha256'] for r in load(original_idle/'manifest.json')['files']}
    for name in assets:
        assert sha(repo/name)==sha(original_idle/'source'/name)==original_rows['source/'+name]
    assert load(root/'C1/report.json')['result']=='failed'
    assert load(root/'C2/report.json')['result']=='passed'
    assert load(root/'C-audit1/report.json')['result']=='passed'
    tracks=load(root/'C3/review/tracks.json')
    assert len(tracks)==8 and all(sha(root/'C3/review'/r['file'])==r['sha256'] for r in tracks)
    url='http://127.0.0.1:8789/references/analysis/start_idle_lifecycle_v1/C3/review/index.html'
    with urlopen(url,timeout=5) as response:
        digest=hashlib.sha256(response.read()).hexdigest()
        assert response.status==200 and digest==sha(root/'C3/review/index.html')
    save(root/'published-review.json',dict(url=url,HTTP_status=200,sha256=digest,persistent_service_restarted=False))
    sources={'AGENTS.md','handoff/当前代码阅读入口.md','handoff/启动怠速全流程接线V1.md',
             'tools/finalize_start_idle_lifecycle_v1.py','tools/research_archive_v1.py',
             'tools/verify_low_mid_event_review_v1.cjs','tools/verify_startup_handoff_review_v1.py',
             'tools/event_review.py','experiments/catalog_drive_v1/models.c','experiments/fine_idle_drive_v1/models.c'}
    sources.update(executed)
    sources.update(assets)
    subprocess.run(['git','diff','--check'],cwd=repo,check=True)
    milestone=dict(schema='vsl.start-idle-lifecycle-milestone/1',result='passed',goal_complete=False,
        previous_goal_turn='No synthesis progress: source/render and MCPS response only',
        current_goal_turn='Frozen exterior startup and corrected real F2 idle/lifecycle composition with independent C/UI/browser evidence',
        checks={key:dict(path=str(root/name),sha256=sha(root/name),result='passed') for key,name in names.items()},
        runtime_voice_files_unchanged=459,formal_voices_unchanged=89,
        additional_legacy_idle_inputs={name:sha(repo/name) for name in assets},
        legacy_idle_base_manifest_sha256=sha(original_idle/'manifest.json'),
        bridge_sha256=sha(bridge),source_ABI=11,author_ABI=4,preset_schema=7,take_schema=8,
        source_files={name:sha(repo/name) for name in sorted(sources)},
        previous_startup_demo_F2_claim_corrected=True,unnecessary_parked_shift_removed_from_scenario=True,
        source_only=True,new_timbre_accepted=False,physical_afterfire_confirmed=False,
        runtime_identity_scope_gap='Legacy F2 experiment assets are separately bound here, but are not covered by the general voices-only take identity.',
        published_review=load(root/'published-review.json'),
        base_freeze=str(base),base_manifest_sha256=sha(base/'manifest.json'),freeze=str(args.freeze),
        unresolved=['startup/idle mechanical listening quality','general asset-identity scope including legacy F2',
                    'confirmed complete physical afterfire and other event timbres','full RPM/load/state coverage'],
        new_download=False,commit_or_push=False,spatial_added=False,ADI_optimization=False,persistent_service_restarted=False)
    save(repo/'research/start_idle_lifecycle_v1_verification.json',milestone)
    sources.add('research/start_idle_lifecycle_v1_verification.json')
    args.freeze.mkdir(parents=True,exist_ok=False)
    for name in sorted(sources):
        target=args.freeze/'repo'/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(repo/name,target)
    shutil.copytree(root,args.freeze/'evidence',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    rows=[dict(path=p.relative_to(args.freeze).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
          for p in sorted(args.freeze.rglob('*')) if p.is_file()]
    save(args.freeze/'manifest.json',dict(schema='vsl.start-idle-lifecycle-delta-freeze/1',
        base_freeze=str(base),base_manifest_sha256=sha(base/'manifest.json'),files=rows,goal_complete=False))
    print(dict(result='frozen',files=len(rows),bytes=sum(r['bytes'] for r in rows),manifest_sha256=sha(args.freeze/'manifest.json')),flush=True)


if __name__=='__main__':main()
