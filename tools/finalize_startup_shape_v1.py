"""Freeze optional modal attacks, actual author/controller use and retained failures."""
import argparse
from pathlib import Path
import shutil
import subprocess
from research_archive_v1 import sha,load,save
from startup_response_evidence_v1 import verify


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--freeze',type=Path,required=True);a=p.parse_args()
    repo=Path(__file__).resolve().parents[1];data=Path('E:/VehicleSoundLab')
    root=data/'references/analysis/startup_shape_v1';base=data/'baselines/startup_handoff_v1/delivery1'
    checks={key:load(root/name) for key,name in dict(native='verification2/report.json',
        independent_fft='audit2/report.json',workbench='web4/verification.json',
        review='review-web2/report.json',controller='ui1/report.json',
        regression='regression1/report.json').items()}
    assert all(v['result']=='passed' for v in checks.values())
    verify(repo,load(root/'verification2/source_binding.json'))
    prior=load(repo/'research/startup_handoff_v1_verification.json')
    old_sources=base/'evidence/verification1/exact_sources'
    for name in prior['voices_unchanged']:assert sha(repo/name)==sha(old_sources/name),name
    assert len(prior['voices_unchanged'])==89
    for variant in ('V10-original','V11-original','V11-candidate'):
        assert all(load(root/'verification2'/variant/'verification.json')['checks'].values())
    current=repo/'build-vehicle-source-v11/bin/Release/vsl_source_bridge.dll'
    old=repo/'build-vehicle-source-v10/bin/Release/vsl_source_bridge.dll'
    author=repo/'build-event-synth-v3/bin/Release/vsl_event_author_bridge.dll'
    old_author=repo/'build-event-synth-v2/bin/Release/vsl_event_author_bridge.dll'
    assert sha(current)==checks['native']['current_bridge_sha256']==checks['controller']['bridge_sha256']
    assert sha(old)==prior['bridge_sha256']==checks['native']['old_bridge_sha256']
    assert sha(author)==checks['native']['author_bridge_sha256']
    assert sha(old_author)==checks['native']['old_author_sha256']
    for track in load(root/'review2/tracks.json'):assert sha(root/'review2'/track['file'])==track['sha256']
    # The original before-edit snapshot selected 49 voice extensions. Check
    # all 89 formal files independently against the previous full freeze here.
    sources={'AGENTS.md','handoff/当前代码阅读入口.md','handoff/声源生成边界与算力V2.md',
        'handoff/启动分频起音与控制台V11.md','Build-Event-Designer.ps1','Build-Vehicle-Source.ps1',
        'tools/author_event.py','tools/inspect_startup_shape_v1.py',
        'tools/startup_response_evidence_v1.py','tools/research_archive_v1.py',
        'experiments/event_synth_v1/author_bridge.c','experiments/event_synth_v1/checks.c',
        'experiments/event_synth_v1/CMakeLists.txt','experiments/vehicle_source_v1/bridge.c',
        'tools/sound_designer/controller.py','tools/sound_designer/web/events.js',
        'tools/sound_designer/web/events.html'}
    for folder in ('modules/event_synth','tools/event_authoring','tools/event_designer','tools/vehicle_controller'):
        sources.update(path.relative_to(repo).as_posix() for path in (repo/folder).rglob('*')
            if path.is_file() and '__pycache__' not in path.parts)
    sources.update(path.relative_to(repo).as_posix() for path in (repo/'tools').glob('*startup_shape*v1*') if path.is_file())
    subprocess.run(['git','diff','--check'],cwd=repo,check=True)
    for file in ('event-build1.log','source-build1.log'):
        assert '100% tests passed' in (root/file).read_text(encoding='utf-8-sig',errors='replace')
    actual=load(root/'web4/verification.json')['actual_parameters']
    milestone=dict(schema='vsl.startup-shape-milestone/1',result='passed',
        previous_goal_turn='no synthesis progress: source/render boundary and budget only',
        current_goal_turn='actual per-mode source envelope and authoring/controller integration',
        bridge_sha256=sha(current),old_bridge_sha256=sha(old),author_bridge_sha256=sha(author),
        abi=10,author_abi=3,profile_bytes=800,preset_schema=7,take_schema=8,
        runtime_C_H_changed=checks['native']['runtime_changes'],voices_unchanged=prior['voices_unchanged'],
        before_snapshot_voice_subset=49,full_prior_freeze_voice_check=89,
        checks=checks,core_checks=dict(event=2,source=6),
        editable_parameters=actual,editable_parameters_sha256=sha(actual),
        source_files={name:sha(repo/name) for name in sorted(sources)},
        freeze=str(a.freeze),base_freeze=str(base),base_manifest_sha256=sha(base/'manifest.json'),
        retained_failures=['diagnosis1/candidate1 used implicit Tukey while claiming Hann',
            'web1 compared WAV timestamp bytes instead of PCM','web2 CSV BOM verifier',
            'review-web1 read old media before new Blob loaded'],
        new_timbre_accepted=False,goal_complete=False,physical_rpm_measured=False,
        persistent_service_restarted=False,spatial_added=False,ADI_optimization=False,new_download=False,commit_or_push=False,
        unresolved=['startup mechanical sound quality and high-band multiple bursts','idle variation quality',
            'confirmed full-band afterfire','other event timbres','full RPM/load/state coverage'])
    save(repo/'research/startup_shape_v1_verification.json',milestone)
    sources.add('research/startup_shape_v1_verification.json')
    a.freeze.mkdir(parents=True,exist_ok=False)
    for name in sorted(sources):
        target=a.freeze/'repo'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,target)
    shutil.copytree(root,a.freeze/'evidence',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    binaries=a.freeze/'binaries';binaries.mkdir()
    for path,label in ((current,'source_v11.dll'),(old,'source_v10.dll'),(author,'author_v3.dll'),(old_author,'author_v2.dll')):
        shutil.copy2(path,binaries/label)
    project=Path(actual).parents[1];shutil.copytree(project,a.freeze/'editable-project',ignore=shutil.ignore_patterns('__pycache__'))
    (a.freeze/'README.md').write_text('# 启动分频起音 V1 冻结增量\n\n'
        '基于 startup_handoff_v1/delivery1 及其基础链；先恢复基础，再覆盖repo。'
        '新source ABI10／author ABI3／profile800字节，配方7／行程8保持严格二进制身份。'
        '旧二进制与参数路径保留；89正式声源逐文件不变。\n\n'
        '当前候选为diagnosis2／candidate2／verification2／review2。'
        'web4、review-web2、ui1与audit2是最终核查；原窗函数错误及验证器失败保留。'
        '新音色未听评通过，实测RPM／真实全频回火／完整状态质量仍未完成；完整目标继续。\n',encoding='utf-8')
    files=[dict(path=p.relative_to(a.freeze).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
        for p in sorted(a.freeze.rglob('*')) if p.is_file()]
    save(a.freeze/'manifest.json',dict(schema='vsl.startup-shape-delta-freeze/1',
        base_freeze=str(base),base_manifest_sha256=sha(base/'manifest.json'),files=files,goal_complete=False))
    print(dict(result='frozen',files=len(files),bytes=sum(row['bytes'] for row in files),manifest_sha256=sha(a.freeze/'manifest.json')),flush=True)


if __name__=='__main__':main()
