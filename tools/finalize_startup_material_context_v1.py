"""Freeze approved B startup evidence and D diagnostics without changing runtime."""
import argparse
from pathlib import Path
import shutil
import subprocess
from research_archive_v1 import sha,load,save


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--freeze',type=Path,required=True);a=p.parse_args()
    repo=Path(__file__).resolve().parents[1];data=Path('E:/VehicleSoundLab')
    work=data/'references/analysis/B_startup_context_v1';d=data/'references/analysis/D_flame_probe_v1'
    base=data/'baselines/vehicle_system_workbench_v1/delivery1'
    b_audit=load(work/'audit3.json');d_audit=load(d/'audit1.json');candidate=load(work/'candidate1/report.json')
    browser=load(work/'web2/report.json');assert all(v['result']=='passed' for v in (b_audit,d_audit,candidate,browser))
    assert browser['own_service_closed'] and browser['browser']['four_tracks_decoded']
    assert b_audit['actual_C_release_check']['silent_from_seconds']==.375
    assert not candidate['timbre_accepted'] and candidate['catch_refused']
    previous=load(repo/'research/vehicle_system_workbench_v1_verification.json')
    old=data/'baselines/state_dna_controller_v1/delivery1/evidence/ui3/exact_sources'
    unchanged=previous['runtime_C_H_unchanged']+previous['voices_unchanged']
    for name in unchanged:assert sha(repo/name)==sha(old/name),name
    dll=repo/'build-vehicle-source-v9/bin/Release/vsl_source_bridge.dll'
    assert sha(dll)==previous['bridge_sha256']==b_audit['source_bridge_unchanged']
    for name,expected in load(work/'review2/report.json')['files'].items():assert sha(work/'review2'/name)==expected
    subprocess.run(['git','diff','--check'],cwd=repo,check=True)
    source_names={
        'tools/probe_D_flames_v1.py','tools/audit_D_flame_probe_v1.py','research/D_flame_probe_v1_plan.json',
        'tools/inspect_event_timeline_v1.py','tools/probe_event_context.py','tools/author_event.py',
        'tools/build_B_startup_candidate_v1.py','tools/audit_B_startup_candidate_v1.py',
        'tools/build_B_startup_review_v1.py','tools/verify_B_startup_review_v1.py','tools/verify_B_startup_review_v1.cjs',
        'tools/finalize_startup_material_context_v1.py','tools/audit_startup_material_context_v1.py',
        'tools/research_archive_v1.py','references/segments_v1.json',
        'handoff/启动素材与包络核查V1.md','handoff/当前代码阅读入口.md','AGENTS.md'}
    for folder,pattern in [('research','B_startup_context_v1_*.json'),('examples/event_authoring','B_initial*.json'),
        ('tools/event_authoring','*.py'),('tools/event_designer','*.py')]:
        source_names.update(p.relative_to(repo).as_posix() for p in (repo/folder).glob(pattern))
    milestone=dict(schema='vsl.startup-material-context-milestone/1',result='passed',
        previous_goal_turn='no progress: compute/source scope answer only',current_goal_turn='progress',
        B_audit=b_audit,D_audit=d_audit,web=browser,
        candidate=str(work/'candidate1/report.json'),candidate_sha256=sha(work/'candidate1/report.json'),
        project_id=candidate['editable_project_id'],catch_diagnostic_id=candidate['catch_diagnostic_project_id'],
        base_freeze=str(base),base_manifest_sha256=sha(base/'manifest.json'),freeze=str(a.freeze),
        source_files={name:sha(repo/name) for name in sorted(source_names)},
        runtime_C_H_unchanged=previous['runtime_C_H_unchanged'],voices_unchanged=previous['voices_unchanged'],
        source_bridge_sha256=sha(dll),timbre_accepted=False,goal_complete=False,
        persistent_service_restarted=False,new_download=False,commit_or_push=False,
        ADI_or_optimization=False,spatial_added=False,
        unresolved=['startup/idle sound quality','confirmed full-band afterfire','other event timbres','full RPM/load/state quality'])
    save(repo/'research/startup_material_context_v1_verification.json',milestone)
    source_names.add('research/startup_material_context_v1_verification.json')
    a.freeze.mkdir(parents=True,exist_ok=False)
    for name in sorted(source_names):
        target=a.freeze/'repo'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,target)
    shutil.copytree(work,a.freeze/'B_evidence',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    shutil.copytree(d,a.freeze/'D_probe',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    # Preserve actual editable project history and the source-free import proof.
    for key in (candidate['editable_project_id'],candidate['source_free_reimport_project_id'],candidate['catch_diagnostic_project_id']):
        shutil.copytree(data/'designs/events'/key,a.freeze/'projects'/key)
    dll=repo/'build-event-synth-v2/bin/Release/vsl_event_author_bridge.dll'
    assert sha(dll)==candidate['renderer_sha256']
    binaries=a.freeze/'binaries';binaries.mkdir();shutil.copy2(dll,binaries/dll.name)
    (a.freeze/'README.md').write_text(
        '# 启动素材与包络核查 V1 冻结增量\n\n'
        '基于 vehicle_system_workbench_v1/delivery1 及其基础链；先恢复基础，再覆盖 repo。'
        '该增量不是独立构建包。当前实时C、89声源及V9 DLL保持，事件作者DLL另附。\n\n'
        'B_evidence包含全部粗查/细查、两版早期提参、接火拒绝、实际C和独立审计。'
        'audit1-failure、audit2及最终audit3均保留；review2/web2是最终页面，仅标题排版改进，review1/web1保留。'
        'projects包含持续候选、仅参数重新导入核查及拒绝的接火诊断工程。\n\n'
        'D_probe为9个可见尾焰和3个对照的固定诊断；原D帧和上下文在基础包D_context。'
        '没有新增已认可音色、完整回火、实测RPM轨迹或空间渲染。完整目标仍未完成。\n',encoding='utf-8')
    files=[dict(path=p.relative_to(a.freeze).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
        for p in sorted(a.freeze.rglob('*')) if p.is_file()]
    save(a.freeze/'manifest.json',dict(schema='vsl.startup-material-context-delta-freeze/1',
        base_freeze=str(base),base_manifest_sha256=sha(base/'manifest.json'),files=files,goal_complete=False))
    print(dict(result='frozen',files=len(files),bytes=sum(v['bytes'] for v in files),manifest_sha256=sha(a.freeze/'manifest.json')),flush=True)


if __name__=='__main__':main()
