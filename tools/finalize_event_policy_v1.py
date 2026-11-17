"""Audit current V7 source and native evidence, then freeze the controller delta."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import shutil
import subprocess

from startup_response_evidence_v1 import sha,verify


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--freeze',type=Path,required=True);a=p.parse_args()
    repo=Path(__file__).resolve().parents[1];data=Path('E:/VehicleSoundLab')
    work=data/'references/analysis/event_policy_v1';base=data/'baselines/startup_timbre_v1/delivery1'
    result=read(work/'verification1/report.json');ui=read(work/'ui2/report.json')
    assert result['result']==ui['result']=='passed' and len(result['default_v6_exact'])==28
    for folder in ('verification1','ui2'):verify(repo,read(work/folder/'source_binding.json'))
    assert ui['second_full_32s_replay_exact'] and ui['saved_take_adopted_in_ui']
    assert ui['final_state']['underflows']==ui['replay_final_state']['underflows']==0
    saved=list((work/'ui2/takes').glob('*.vsltake.json'));assert len(saved)==1
    value=read(saved[0]);policy=value['event_policy']
    starts=[n for n in value['source_events'] if n['type']==3 and n['action']==1]
    assert len(starts)==3 and policy['afterfire_min_count']==policy['afterfire_max_count']==3
    gap=round(policy['afterfire_interval_min_seconds']*48000)
    assert gap==5760 and all(b['frame']-a['frame']==gap for a,b in zip(starts,starts[1:]))
    assert starts==ui['automatic_starts'] and ui['final_state']['lifecycle']==0
    logs={}
    for name,count in (('source-build2.log',4),('core-tests2.log',2)):
        text=(work/name).read_text(encoding='utf-8-sig')
        assert f'100% tests passed out of {count}' in text
        logs[name]=dict(tests=count,sha256=sha(work/name))
    old={r['path'][5:]:r for r in read(base/'manifest.json')['files'] if r['path'].startswith('repo/')}
    voices=[];changes=[]
    for path in sorted((repo/'voices').rglob('*')):
        if path.is_file():
            name=path.relative_to(repo).as_posix();assert name in old and sha(path)==old[name]['sha256'],name
            voices.append(dict(path=name,sha256=sha(path)))
    assert len(voices)==89
    for folder in ('src','modules','experiments/vehicle_source_v1'):
        for path in (repo/folder).rglob('*'):
            if path.is_file() and path.suffix in ('.c','.h'):
                name=path.relative_to(repo).as_posix()
                if name not in old or sha(path)!=old[name]['sha256']:changes.append(name)
    allowed={'modules/event_control/api.h','modules/event_control/policy.c','modules/event_control/configuration.c',
        'modules/vehicle_source/api.h','modules/vehicle_source/event_policy.c',
        'experiments/vehicle_source_v1/bridge.c','experiments/vehicle_source_v1/bridge.h','experiments/vehicle_source_v1/policy_checks.c'}
    assert set(changes)==allowed,changes
    binaries={
        'source-v7':repo/'build-vehicle-source-v7/bin/Release/vsl_source_bridge.dll',
        'source-v6':repo/'build-vehicle-source-v6/bin/Release/vsl_source_bridge.dll',
        'author-v2':repo/'build-event-synth-v2/bin/Release/vsl_event_author_bridge.dll'}
    assert sha(binaries['source-v7'])==result['bridge_sha256']
    assert sha(binaries['source-v6'])=='d6e383857365705bc60f6f4a4271c1c5a1793c0e3b485b4fb5a342dd990ebeb4'
    assert sha(binaries['author-v2'])=='2043597cb96ab7902431bebb84ed2552ccf30277ace8d9160663ca357819fed1'
    subprocess.run(['git','diff','--check'],cwd=repo,check=True)
    summary=dict(schema='vsl.event-policy-milestone/1',result='passed',previous_goal_turn='no_progress',current_goal_turn='progress',
        verification=result,ui=ui,required_CTests=logs,source_C_H_changes=sorted(changes),voices_unchanged=voices,
        binaries={name:dict(path=str(path),sha256=sha(path)) for name,path in binaries.items()},
        independently_checked_saved_take_three_gaps=True,base_freeze=str(base),base_manifest_sha256=sha(base/'manifest.json'),
        freeze=str(a.freeze),goal_complete=False,timbre_accepted=False,formal_event_mask=6,
        unresolved=['startup hearing','confirmed full-band afterfire','other event timbres and full-state quality'],
        persistent_app_restarted=False,owned_muted_test_windows_closed=True,new_download=False,commit_or_push=False,
        retained_failures=['research/event_policy_v1_initial_delay_failure.json','ui1 wrong dialog screenshot','core-tests1 no tests found'])
    write(repo/'research/event_policy_v1_verification.json',summary)
    a.freeze.mkdir(parents=True,exist_ok=False)
    # Explicit delta: current source bindings plus current authoring/launcher.
    selections=['src','modules','voices','experiments/vehicle_source_v1','tools/vehicle_controller','tools/vehicle_scenarios',
        'tools/event_authoring','tools/event_designer','tools/sound_designer','tools/run_vehicle_controller.py',
        'tools/verify_event_policy_v1.py','tools/verify_event_policy_ui_v1.py','tools/startup_response_evidence_v1.py',
        'tools/finalize_event_policy_v1.py','Build-Vehicle-Source.ps1','Launch-Vehicle-Controller.cmd',
        'handoff/事件触发配方与控制台V7.md','handoff/当前代码阅读入口.md','AGENTS.md',
        'research/event_policy_v1_initial_delay_failure.json','research/event_policy_v1_verification.json']
    for name in selections:
        source=repo/name;target=a.freeze/'repo'/name;target.parent.mkdir(parents=True,exist_ok=True)
        if source.is_dir():shutil.copytree(source,target,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        else:shutil.copy2(source,target)
    shutil.copytree(work,a.freeze/'evidence',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    for name,path in binaries.items():
        target=a.freeze/'binaries'/name/path.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
    for project in ('773ad53ffd964fa18a7abfaf4aa2821b','462af3cefda441aba34886ecfc96dbae','028a56d636574ab1bb902a1d3479ac7e'):
        shutil.copytree(data/'designs/events'/project,a.freeze/'candidate-projects'/project)
    readme='''# 控制台 V7 冻结增量

这是控制台／事件触发配方的源码、二进制与验证证据增量；完整基础为manifest所指的startup_timbre_v1/delivery1，不宣称本增量可脱离基础独立构建。恢复时在基础副本上覆盖repo，再将binaries/source-v7/vsl_source_bridge.dll放入repo/build-vehicle-source-v7/bin/Release。不要覆盖原基础或旧二进制。

ui2为正式界面核查，两轮各32秒，均为静音测试且窗口已关闭。verification1为真实V6对照和自定义策略核查。ui1保留截图错误，core-tests1没有执行测试，source-build2与core-tests2共六项C检查通过。

candidate-projects只含未验收候选，E仅1.2–14kHz，不能当作已确认全频回火；正式事件库没有晋升。完整系统目标、其他事件与音色验收继续，常驻旧服务未重启。
'''
    (a.freeze/'README.md').write_text(readme,encoding='utf-8')
    subprocess.run(['git','diff','--binary','--output='+str(a.freeze/'working-tree.patch')],cwd=repo,check=True)
    files=[dict(path=f.relative_to(a.freeze).as_posix(),bytes=f.stat().st_size,sha256=sha(f))
        for f in sorted(a.freeze.rglob('*')) if f.is_file()]
    write(a.freeze/'manifest.json',dict(schema='vsl.event-policy-delta-freeze/1',created=datetime.now(timezone.utc).isoformat(),
        base_freeze=str(base),base_manifest_sha256=sha(base/'manifest.json'),goal_complete=False,files=files))
    print(json.dumps(dict(result='frozen',files=len(files),bytes=sum(r['bytes'] for r in files),path=str(a.freeze))))


if __name__=='__main__':main()
