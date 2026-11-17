"""Freeze the actual startup controller fix, captures and failed directions."""
import argparse
from pathlib import Path
import shutil
import subprocess

from research_archive_v1 import sha,load,save
from startup_response_evidence_v1 import verify


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--freeze',type=Path,required=True);a=p.parse_args()
    repo=Path(__file__).resolve().parents[1];data=Path('E:/VehicleSoundLab')
    work=data/'references/analysis/startup_handoff_v1'
    verification=load(work/'verification1/report.json')
    web=load(work/'web2/report.json');ui=load(work/'ui2/report.json')
    assert all(v['result']=='passed' for v in (verification,web,ui))
    assert len(verification['exact_cases'])==26 and len(verification['neutral_cases'])==12
    verify(repo,load(work/'verification1/source_binding.json'))
    previous=load(repo/'research/startup_material_context_v1_verification.json')
    original=data/'baselines/state_dna_controller_v1/delivery1/evidence/ui3/exact_sources'
    changed=[name for name in previous['runtime_C_H_unchanged'] if sha(repo/name)!=sha(original/name)]
    assert changed==['src/drive/drive.c'],changed
    for name in previous['voices_unchanged']:assert sha(repo/name)==sha(original/name),name
    assert len(previous['voices_unchanged'])==89
    dll=repo/'build-vehicle-source-v10/bin/Release/vsl_source_bridge.dll'
    old=repo/'build-vehicle-source-v9/bin/Release/vsl_source_bridge.dll'
    assert sha(dll)==verification['new_bridge_sha256']==ui['bridge_sha256']
    assert sha(old)==verification['old_bridge_sha256']==previous['source_bridge_sha256']
    for variant in ('original1','no-catch1','fixed1','timing1'):
        value=load(work/variant/'verification.json');assert value['result']=='passed' and all(value['checks'].values())
    for name,expected in load(work/'review2/report.json')['files'].items():assert sha(work/'review2'/name)==expected,name
    observation=load(work/'observation2/report.json')
    rows={v['variant']:v for v in observation['captures']}
    assert rows['original1']['startup_shift_block_seconds']==.225
    assert rows['fixed1']['startup_shift_block_seconds']==rows['timing1']['startup_shift_block_seconds']==0
    assert rows['timing1']['early_to_catch_seconds']==.572
    subprocess.run(['git','diff','--check'],cwd=repo,check=True)
    sources={'AGENTS.md','CMakeLists.txt','Build-Vehicle-Source.ps1','src/drive/drive.c','tests/test_startup_gear.c',
        'tools/vehicle_controller/native.py','tools/vehicle_controller/ui.py','tools/sound_designer/controller.py',
        'handoff/当前代码阅读入口.md','handoff/启动到怠速衔接与控制台V10.md','research/startup_handoff_v1_plan.json',
        'tools/research_archive_v1.py','tools/startup_response_evidence_v1.py'}
    sources.update(path.relative_to(repo).as_posix() for path in (repo/'tools').glob('*startup_handoff*v1*') if path.is_file())
    sources.update(path.relative_to(repo).as_posix() for path in (repo/'tools/startup_handoff_v1').glob('*.py'))
    base=data/'baselines/startup_material_context_v1/delivery1'
    milestone=dict(schema='vsl.startup-handoff-milestone/1',result='passed',
        previous_goal_turn='no synthesis progress: source/render scope only',current_goal_turn='actual controller and source handoff progress',
        runtime_C_H_changed=changed,runtime_C_H_total=len(previous['runtime_C_H_unchanged']),
        voices_unchanged=previous['voices_unchanged'],old_bridge_sha256=sha(old),bridge_sha256=sha(dll),abi=9,
        verification=verification,UI=ui,web=web,observation=observation,
        core_checks=dict(original=5,new_selector=1,independent_source=6),
        source_files={name:sha(repo/name) for name in sorted(sources)},
        freeze=str(a.freeze),base_freeze=str(base),base_manifest_sha256=sha(base/'manifest.json'),
        new_timbre_accepted=False,goal_complete=False,physical_rpm_measured=False,
        persistent_service_restarted=False,spatial_added=False,ADI_optimization=False,new_download=False,commit_or_push=False,
        unresolved=['startup mechanical sound quality','idle variation quality','confirmed full-band afterfire','other event timbres','full RPM/load/state coverage'])
    save(repo/'research/startup_handoff_v1_verification.json',milestone)
    sources.add('research/startup_handoff_v1_verification.json')
    a.freeze.mkdir(parents=True,exist_ok=False)
    for name in sorted(sources):
        target=a.freeze/'repo'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,target)
    shutil.copytree(work,a.freeze/'evidence',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    binaries=a.freeze/'binaries';binaries.mkdir()
    shutil.copy2(dll,binaries/'vsl_source_bridge_v10.dll');shutil.copy2(old,binaries/'vsl_source_bridge_v9.dll')
    (a.freeze/'README.md').write_text('# 启动到怠速衔接 V1 冻结增量\n\n'
        '基于 startup_material_context_v1/delivery1 及其基础链；不是独立源码构建包。先恢复基础，再覆盖repo。'
        'V10行为修正保持ABI9／配方7／行程8，严格二进制身份仍区分V9。\n\n'
        'evidence包含V9原版／去接火诊断、V10修正／时序候选的实际C音频和变块重放，'
        '原声、23原生通道、200Hz遥测、事件身份、六频带与交叉功率，及26精确／12空挡回归。'
        'core-red、review1/web1、ui1失败留痕保留；review2/web2与ui2是最终界面验证。'
        '89声源保持，没有新音色认可、实测RPM或空间／算力优化。完整目标仍继续。\n',encoding='utf-8')
    files=[dict(path=path.relative_to(a.freeze).as_posix(),bytes=path.stat().st_size,sha256=sha(path))
           for path in sorted(a.freeze.rglob('*')) if path.is_file()]
    save(a.freeze/'manifest.json',dict(schema='vsl.startup-handoff-delta-freeze/1',
        base_freeze=str(base),base_manifest_sha256=sha(base/'manifest.json'),files=files,goal_complete=False))
    print(dict(result='frozen',files=len(files),bytes=sum(row['bytes'] for row in files),manifest_sha256=sha(a.freeze/'manifest.json')),flush=True)


if __name__=='__main__':main()
