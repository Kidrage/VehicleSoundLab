"""Audit native/tool/UI evidence and freeze the V8 authored-DNA delivery delta."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import shutil
import subprocess
from startup_response_evidence_v1 import sha,verify
from vehicle_controller.native import Bridge,Engine
from vehicle_controller import dna_bank as dna,take


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--freeze',type=Path,required=True);args=p.parse_args()
    repo=Path(__file__).resolve().parents[1];data=Path('E:/VehicleSoundLab');work=data/'references/analysis/dna_controller_v1'
    base=data/'baselines/event_policy_v1/delivery1';prior=read(base/'manifest.json')
    result=read(work/'verification2/report.json');ui=read(work/'ui1/report.json');web=read(work/'web2/verification.json')
    assert result['result']==ui['result']==web['result']=='passed' and len(result['default_V7_exact'])==28
    for name in ('verification2','ui1'):verify(repo,read(work/name/'source_binding.json'))
    assert all(sha(repo/name)==expected for name,expected in read(work/'verification2/workbench-binding.json').items())
    assert ui['underflows']==0 and ui['full_32s_cycle'] and ui['saved_take_UI_32s_replay']
    saved=list((work/'ui1/takes').glob('*.vsltake.json'));assert len(saved)==1
    value=read(saved[0]);assert value['schema']=='vsl.source-controller-take/7'
    assert ui['final_state']['lifecycle']==0 and ui['final_state']['shifts']>0
    assert value['dna_bank']==read(work/'ui1/editor.dnabank.json')
    assert any(n['type']==1 and n['action']==1 for n in value['source_events'])
    assert any(n['type']==2 and n['action']==1 for n in value['source_events'])
    log2=data/'references/analysis/dna_controller_v1_build2.log';log3=data/'references/analysis/dna_controller_v1_dna-test3.log'
    text=log2.read_text(encoding='utf-8-sig')
    assert text.count('...   Passed')==4 and '80% tests passed, 1 tests failed out of 5' in text
    assert '100% tests passed out of 1' in log3.read_text(encoding='utf-8-sig')
    old={r['path'][5:]:r for r in prior['files'] if r['path'].startswith('repo/')}
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
    allowed={'modules/vehicle_source/dna_assets.c','modules/vehicle_source/dna_assets.h',
        'experiments/vehicle_source_v1/bridge.c','experiments/vehicle_source_v1/bridge.h','experiments/vehicle_source_v1/dna_checks.c'}
    assert set(changes)==allowed,changes
    bridge=Bridge(repo);assert bridge.abi()==8 and bridge.event_available_mask==6
    binaries={name:repo/path for name,path in (
        ('source-v8','build-vehicle-source-v8/bin/Release/vsl_source_bridge.dll'),
        ('source-v7','build-vehicle-source-v7/bin/Release/vsl_source_bridge.dll'),
        ('author-v2','build-event-synth-v2/bin/Release/vsl_event_author_bridge.dll'))}
    assert sha(binaries['source-v8'])==result['bridge_sha256'] and sha(binaries['source-v7'])==result['old_bridge_sha256']
    prior_binary=next(r for r in prior['files'] if r['path']=='binaries/source-v7/vsl_source_bridge.dll')
    assert sha(binaries['source-v7'])==prior_binary['sha256']
    assert sha(binaries['author-v2'])=='2043597cb96ab7902431bebb84ed2552ccf30277ace8d9160663ca357819fed1'
    # Observe the REAL constructor paths; prove all temporary model files are
    # gone before the first native audio process call, while the voice still works.
    native=bridge.open_dna;observed=[]
    def observe(selection,paths,count,ratio,seed,align):
        observed.extend(Path(paths[i].decode('utf-8')) for i in range(count))
        assert all(path.is_file() for path in observed)
        return native(selection,paths,count,ratio,seed,align)
    bridge.open_dna=observe
    with Engine(bridge,0,dna_bank=value['dna_bank']) as engine:
        assert observed and all(not p.exists() for p in observed)
        engine.set(dict(engine.controls,mode=0,rpm=3000.,ignition=1,start_id=1))
        assert any(any(engine.process(480)) for _ in range(200))
    subprocess.run(['git','diff','--check'],cwd=repo,check=True)
    summary=dict(schema='vsl.dna-controller-milestone/1',result='passed',previous_goal_turn='no_progress',current_goal_turn='progress',
        verification=result,ui=ui,web=web,required_CTests=dict(total_distinct_passed=5,
            original_four=dict(log=str(log2),sha256=sha(log2)),authored_dna=dict(log=str(log3),sha256=sha(log3))),
        temp_model_files_removed_before_audio=True,source_C_H_changes=sorted(changes),voices_unchanged=voices,
        binaries={name:dict(path=str(path),sha256=sha(path)) for name,path in binaries.items()},formal_event_mask=6,
        base_freeze=str(base),base_manifest_sha256=sha(base/'manifest.json'),freeze=str(args.freeze),
        persistent_app_restarted=False,owned_test_services_windows_closed=True,new_download=False,commit_or_push=False,
        goal_complete=False,new_timbre_accepted=False,
        unresolved=['startup hearing','confirmed full-band afterfire','other independent event timbres','full RPM/load/state sound quality'],
        retained_failures=['build2 DNA fixture inherited catalog gains','verification1 checked before RPM settled','web1 did not await asynchronous project selection'])
    take.save(repo/'research/dna_controller_v1_verification.json',summary)
    args.freeze.mkdir(parents=True,exist_ok=False)
    selected=['src','modules','voices','experiments/vehicle_source_v1','tools/vehicle_controller','tools/vehicle_scenarios',
        'tools/event_authoring','tools/event_designer','tools/sound_designer','tools/sound_dna','tools/run_vehicle_controller.py',
        'tools/verify_dna_controller_v1.py','tools/verify_dna_controller_ui_v1.py','tools/verify_dna_controller_web_v1.py',
        'tools/verify_dna_controller_web_v1.cjs','tools/finalize_dna_controller_v1.py','tools/verify_event_policy_v1.py',
        'tools/startup_response_evidence_v1.py','Build-Vehicle-Source.ps1','Launch-Vehicle-Controller.cmd',
        'handoff/工作台DNA驾驶接入与控制台V8.md','handoff/当前代码阅读入口.md','AGENTS.md','research/dna_controller_v1_verification.json']
    for name in selected:
        source=repo/name;target=args.freeze/'repo'/name;target.parent.mkdir(parents=True,exist_ok=True)
        if source.is_dir():shutil.copytree(source,target,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        else:shutil.copy2(source,target)
    shutil.copytree(work,args.freeze/'evidence',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    for path in sorted((data/'references/analysis').glob('dna_controller_v1_*.log')):
        shutil.copy2(path,args.freeze/'evidence'/path.name)
    for name,path in binaries.items():
        target=args.freeze/'binaries'/name/path.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
    readme='''# 工作台 DNA / 控制台 V8 冻结增量

本增量基于 event_policy_v1/delivery1，其基础链由 manifest 指明。恢复时在基础副本上覆盖 repo，并把 binaries/source-v8/vsl_source_bridge.dll 放入 repo/build-vehicle-source-v8/bin/Release。原基础与 V7 二进制保留。本目录不宣称可脱离基础独立构建。

verification2、web2、ui1 为正式功能证据。ui1 是自有静音窗口，两轮各 32 秒，窗口已关闭；web2 的限时本地服务已关闭，没有启动常驻控制器。build2 的旧四项通过，新增 DNA 测试夹具失败；修复夹具后的 dna-test3 通过新增项，共五项不同 C 检查通过。

verification1、web1 和早期日志保留失败；单锚点不代表全 RPM／负载／状态声纹。没有新音色认可、ADI 性能资格或完整回火音色验收。完整目标继续，常驻旧工作台／窗口未重启。
'''
    (args.freeze/'README.md').write_text(readme,encoding='utf-8')
    subprocess.run(['git','diff','--binary','--output='+str(args.freeze/'working-tree.patch')],cwd=repo,check=True)
    files=[dict(path=f.relative_to(args.freeze).as_posix(),bytes=f.stat().st_size,sha256=sha(f))
        for f in sorted(args.freeze.rglob('*')) if f.is_file()]
    take.save(args.freeze/'manifest.json',dict(schema='vsl.dna-controller-delta-freeze/1',created=datetime.now(timezone.utc).isoformat(),
        base_freeze=str(base),base_manifest_sha256=sha(base/'manifest.json'),goal_complete=False,files=files))
    print(json.dumps(dict(result='frozen',files=len(files),bytes=sum(r['bytes'] for r in files),path=str(args.freeze))),flush=True)


if __name__=='__main__':main()
