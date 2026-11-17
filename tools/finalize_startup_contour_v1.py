"""Freeze V12 event contours with actual C/UI evidence and explicit unqualified B fit."""
import argparse
from pathlib import Path
import shutil
import subprocess
from research_archive_v1 import sha,load,save
from startup_response_evidence_v1 import capture,verify


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--freeze',type=Path,required=True)
    args=parser.parse_args();repo=Path(__file__).resolve().parents[1];data=Path('E:/VehicleSoundLab')
    root=data/'references/analysis/startup_contour_v1';base=data/'baselines/startup_shape_v1/delivery1'
    checks={key:load(root/name) for key,name in dict(native='verification1/report.json',
        independent_fft='audit2/report.json',workbench='web1/verification.json',editor='editor1/report.json',
        controller='ui1/report.json',review='review-web1/report.json',regression='regression1/report.json').items()}
    assert all(check['result']=='passed' for check in checks.values())
    prior=load(repo/'research/startup_shape_v1_verification.json')
    voices=sorted(path.relative_to(repo).as_posix() for path in (repo/'voices').rglob('*') if path.is_file())
    assert len(voices)==89 and voices==sorted(prior['voices_unchanged'])
    for name in voices:assert sha(repo/name)==sha(base/'evidence/verification2/exact_sources'/name),name
    current=repo/'build-vehicle-source-v12/bin/Release/vsl_source_bridge.dll'
    old=repo/'build-vehicle-source-v11/bin/Release/vsl_source_bridge.dll'
    author=repo/'build-event-synth-v4/bin/Release/vsl_event_author_bridge.dll'
    old_author=repo/'build-event-synth-v3/bin/Release/vsl_event_author_bridge.dll'
    assert sha(current)==checks['native']['current_bridge_sha256']==checks['controller']['bridge_sha256']
    assert sha(old)==checks['native']['old_bridge_sha256']==prior['bridge_sha256']
    assert sha(author)==checks['native']['author_bridge_sha256']
    assert sha(old_author)==checks['native']['old_author_sha256']==prior['author_bridge_sha256']
    # Preserve the two prior presentation files against their recorded hashes.
    before=load(root/'verification1/source_binding_before_UI.json')
    hashes={r['path']:r['sha256'] for r in before['files']}
    for name in ('tools/sound_designer/controller.py','tools/vehicle_controller/events.py'):
        s=(repo/name).read_text(encoding='utf-8')
        if name.endswith('controller.py'):s=s.replace('revision=12','revision=10')
        else:s=s.replace("        contours=doc.get('parameters',{}).get('contours',[])\n        if contours:band+=f' {len(contours)}组多段包络。'\n",'')
        path=root/'verification1/presentation_before'/name;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(s,encoding='utf-8',newline='\n');assert sha(path)==hashes[name],name
    # Only a module README was added after the final UI binding; no signal change.
    bound=load(root/'verification1/source_binding.json');verify(repo,bound)
    final_binding=capture(repo,root/'verification1',current);verify(repo,final_binding)
    for variant in ('V11-original','V12-original','V12-candidate'):
        assert all(load(root/'verification1'/variant/'verification.json')['checks'].values())
    for file in ('event-build1.log','source-build1.log'):
        assert '100% tests passed' in (root/file).read_text(encoding='utf-8-sig',errors='replace')
    assert checks['regression']['B_gated_material_trial']['extraction']['status']=='analysis_only'
    b=load(root/'regression1/B/report.json')
    assert b['fit']['source_response_fit']['qualified'] is False
    assert not (root/'regression1/B/profile.json').exists()
    for track in load(root/'review2/tracks.json'):assert sha(root/'review2'/track['file'])==track['sha256']
    subprocess.run(['git','diff','--check'],cwd=repo,check=True)
    actual=checks['workbench']['actual_parameters'];assert Path(actual).is_file()
    sources={'AGENTS.md','handoff/当前代码阅读入口.md','handoff/声源生成边界与算力V2.md',
        'handoff/启动多段包络与控制台V12.md','Build-Event-Designer.ps1','Build-Vehicle-Source.ps1',
        'tools/author_event.py','tools/research_archive_v1.py','tools/startup_response_evidence_v1.py',
        'tools/audit_startup_shape_v1.py','tools/sound_designer/controller.py',
        'experiments/event_synth_v1/author_bridge.c','experiments/event_synth_v1/contour_checks.c',
        'experiments/event_synth_v1/CMakeLists.txt','experiments/vehicle_source_v1/bridge.c'}
    for folder in ('modules/event_synth','tools/event_authoring','tools/event_designer','tools/vehicle_controller'):
        sources.update(p.relative_to(repo).as_posix() for p in (repo/folder).rglob('*')
            if p.is_file() and '__pycache__' not in p.parts)
    sources.update(p.relative_to(repo).as_posix() for p in (repo/'tools').glob('*startup_contour*v1*') if p.is_file())
    sources.update('tools/sound_designer/web/'+name for name in ('events.js','events.html','events.css','event_contours.js'))
    milestone=dict(schema='vsl.startup-contour-milestone/1',result='passed',
        previous_goal_turn='no synthesis progress: generator/render boundary clarification',
        current_goal_turn='actual coarse source envelopes, optional authoring and C/UI/controller integration',
        abi=11,author_abi=4,profile_bytes=1408,preset_schema=7,take_schema=8,
        bridge_sha256=sha(current),old_bridge_sha256=sha(old),author_bridge_sha256=sha(author),
        runtime_C_H_changed=checks['native']['runtime_changes'],voices_unchanged=voices,
        checks=checks,core_checks=dict(event=3,source=6),
        editable_parameters=actual,editable_parameters_sha256=sha(actual),
        source_files={name:sha(repo/name) for name in sorted(sources)},
        freeze=str(args.freeze),base_freeze=str(base),base_manifest_sha256=sha(base/'manifest.json'),
        retained_limitations=['B gated contour final spectral failure -6.368dB; no profile compiled',
            'one unscaled float seed peak about1.032FS; fixed .25 audition gain and no limiter',
            'review1 retained before presentation title correction; review2 current',
            'finalize1 historical presentation restoration used Windows newlines; exact LF hash restoration fixed'],
        new_timbre_accepted=False,goal_complete=False,physical_rpm_measured=False,
        persistent_service_restarted=False,spatial_added=False,ADI_optimization=False,new_download=False,commit_or_push=False,
        unresolved=['startup mechanical/high-band fine texture','B contour/spectral joint fit','idle variation',
            'confirmed full-band afterfire','other event timbres','full RPM/load/state coverage'])
    save(repo/'research/startup_contour_v1_verification.json',milestone)
    sources.add('research/startup_contour_v1_verification.json');args.freeze.mkdir(parents=True,exist_ok=False)
    for name in sorted(sources):
        target=args.freeze/'repo'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,target)
    shutil.copytree(root,args.freeze/'evidence',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    binaries=args.freeze/'binaries';binaries.mkdir()
    for path,label in ((current,'source_v12.dll'),(old,'source_v11.dll'),(author,'author_v4.dll'),(old_author,'author_v3.dll')):
        shutil.copy2(path,binaries/label)
    shutil.copytree(Path(actual).parents[1],args.freeze/'editable-project')
    (args.freeze/'README.md').write_text('# 启动多段包络 V12 冻结增量\n\n'
        '基于 startup_shape_v1/delivery1 及其基础链；先恢复基础，再覆盖repo。'
        'source ABI11／author ABI4／Profile1408字节，配方7／行程8按实际二进制严格校验。'
        '旧DLL、参数与89正式声源保留。\n\n'
        'candidate1／verification1／audit2／web1／editor1／ui1／review2／review-web1／regression1为最终证据。'
        'A候选时间结构改善但未听评；B门控新包络频谱失败明确拒绝，不宣称全面泛化。'
        '完整目标继续，真实全频回火、其他事件、怠速及完整RPM负载质量尚未完成。\n',encoding='utf-8')
    files=[dict(path=p.relative_to(args.freeze).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
        for p in sorted(args.freeze.rglob('*')) if p.is_file()]
    save(args.freeze/'manifest.json',dict(schema='vsl.startup-contour-delta-freeze/1',
        base_freeze=str(base),base_manifest_sha256=sha(base/'manifest.json'),files=files,goal_complete=False))
    print(dict(result='frozen',files=len(files),bytes=sum(row['bytes'] for row in files),manifest_sha256=sha(args.freeze/'manifest.json')),flush=True)


if __name__=='__main__':main()
