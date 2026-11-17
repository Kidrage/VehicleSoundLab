"""Bind complete vehicle authoring to actual browser/native/UI proofs and freeze."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import shutil
import subprocess
import soundfile as sf
import numpy as np
from research_archive_v1 import sha, save, load
from startup_response_evidence_v1 import verify


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--freeze',type=Path,required=True);a=p.parse_args()
    repo=Path(__file__).resolve().parents[1];data=Path('E:/VehicleSoundLab')
    work=data/'references/analysis/vehicle_system_workbench_v1';context=data/'references/analysis/D_event_context_v1'
    base=data/'baselines/state_recipe_workbench_v1/delivery1';runtime=data/'baselines/state_dna_controller_v1/delivery1'
    native=load(work/'verification1/report.json');web=load(work/'web1/verification.json');ui=load(work/'ui2/report.json')
    regressions={name:load(work/name/'verification.json') for name in ('dna-only-regression1','single-state-regression1')}
    assert all(row['result']=='passed' for row in (native,web,ui,*regressions.values()))
    assert native['variable_block_replay_PCM_events_state_exact'] and native['empty_event_selection_silences_compiled_candidates']
    assert native['invalid_preserves_snapshot']==5 and web['downloaded_full_preset_actual_C']
    assert ui['one_file_restore_all_settings'] and ui['saved_take_32s_UI_replay'] and ui['underflows']==0
    assert ui['downloaded_preset_sha256']==web['preset_sha256']==sha(work/'web1/browser.preset.json')
    assert native['event_start_counts']==ui['event_start_counts'] and ui['event_start_counts']['afterfire']==3
    assert all(ui['event_start_counts'].values()) and {1,2,3}<=set(ui['state_weights_observed'])
    assert web['browser']['no_autoplay'] and web['browser']['driver_not_launched'] and web['own_service_closed']
    assert all(row.get('own_service_closed',row.get('owned_service_closed',False)) for row in regressions.values())
    # Earlier native execution predates only verified UI presentation and one
    # duplicate GET branch removal. Authoring/native contracts must be exact.
    allowed={'tools/sound_designer/server.py','tools/sound_designer/web/vehicles.js','tools/vehicle_controller/ui.py'}
    deltas={}
    for label,allowed_changes in (('verification1',allowed),('web1',{'tools/vehicle_controller/ui.py'})):
        old=load(work/label/'source_binding.json');changed=[]
        for name,expected in old.items():
            assert sha(work/label/'exact_sources'/name)==expected,name
            if sha(repo/name)!=expected:
                assert name in allowed_changes,name
                changed.append(name)
        deltas[label]=changed
    verify(repo,load(work/'ui2/source_binding.json'))
    for name,evidence in (
        ('verify_vehicle_system_workbench_v1.py','verification1/executed_verification.py'),
        ('verify_vehicle_system_workbench_web_v1.py','web1/executed_verification.py'),
        ('verify_vehicle_system_workbench_web_v1.cjs','web1/verify_vehicle_system_workbench_web_v1.cjs'),
        ('verify_vehicle_system_controller_ui_v1.py','ui2/executed_verification.py')):
        assert sha(repo/'tools'/name)==sha(work/evidence),name
    prior=load(runtime/'manifest.json');old={r['path'][5:]:r for r in prior['files'] if r['path'].startswith('repo/')}
    unchanged=[]
    for folder in ('src','modules','experiments/vehicle_source_v1'):
        for file in sorted((repo/folder).rglob('*')):
            if file.is_file() and file.suffix in ('.c','.h'):
                name=file.relative_to(repo).as_posix();assert sha(file)==old[name]['sha256'],name;unchanged.append(name)
    voices=[]
    for file in sorted((repo/'voices').rglob('*')):
        if file.is_file():
            name=file.relative_to(repo).as_posix();assert sha(file)==old[name]['sha256'],name;voices.append(name)
    assert len(voices)==89
    dll=repo/'build-vehicle-source-v9/bin/Release/vsl_source_bridge.dll'
    old_dll=next(r for r in prior['files'] if r['path']=='binaries/source-v9/vsl_source_bridge.dll')
    assert sha(dll)==old_dll['sha256']==native['bridge_sha256']==web['bridge_sha256']==ui['bridge_sha256']
    # Independently verify D's unprocessed 36..46s context and frame bindings.
    folder=context/'flames1/D_tailpipe_flames';report=load(folder/'report.json');source=report['source']
    assert sha(source['path'])==source['sha256'] and report['monitor_gain']==.25
    assert sha(data/'references/raw/D_21q_wpc-pVA.mkv')==report['video_sha256']
    original,sr=sf.read(folder/'original.wav',dtype='float32',always_2d=True)
    monitor,mr=sf.read(folder/'monitor.wav',dtype='float32',always_2d=True)
    with sf.SoundFile(source['path']) as stream:
        stream.seek(source['first_frame']);raw=stream.read(source['last_frame']-source['first_frame'],dtype='float32',always_2d=True)
    assert sr==mr==48000 and np.array_equal(original,raw) and np.array_equal(monitor,raw*np.float32(.25))
    assert len(report['frames'])==51
    for row in report['frames']:assert sha(folder/row['file'])==row['sha256']
    assert not report['physical_identity_confirmed']
    d_audit=dict(result='passed',source_sha256=source['sha256'],video_sha256=report['video_sha256'],
        frames_verified=51,original_PCM_exact=True,monitor_only_quarter_gain=True,source_seconds=[36,46],
        observed_flame_examples=[37.8,39.6,40.,40.2,41.,41.6,42.,43.8,45.6],
        acoustic_afterfire_identity_confirmed=False,listening_question_pending=True,
        outro_candidate_55_445_not_engine=True,no_new_fit_or_download=True)
    save(context/'audit1.json',d_audit)
    subprocess.run(['git','diff','--check'],cwd=repo,check=True)
    milestone=dict(schema='vsl.vehicle-system-workbench-milestone/1',result='passed',
        previous_goal_turn='no progress: source/render compute scope answer only',current_goal_turn='progress',
        native=native,web=web,ui=ui,regressions=regressions,verified_source_deltas=deltas,
        runtime_C_H_unchanged=unchanged,voices_unchanged=voices,bridge_sha256=sha(dll),
        D_context=d_audit,base_freeze=str(base),base_manifest_sha256=sha(base/'manifest.json'),freeze=str(a.freeze),
        persistent_app_restarted=False,new_download=False,commit_or_push=False,optimization_or_ADI=False,
        spatial_added=False,new_timbre_accepted=False,goal_complete=False,
        unresolved=['startup hearing','confirmed full-band afterfire','other event timbres','full RPM/load/state quality'])
    save(repo/'research/vehicle_system_workbench_v1_verification.json',milestone)
    a.freeze.mkdir(parents=True,exist_ok=False)
    names=('tools/sound_designer','tools/vehicle_controller/ui.py',
        'tools/verify_vehicle_system_workbench_v1.py','tools/verify_vehicle_system_workbench_web_v1.py',
        'tools/verify_vehicle_system_workbench_web_v1.cjs','tools/verify_vehicle_system_controller_ui_v1.py',
        'tools/finalize_vehicle_system_workbench_v1.py','tools/audit_vehicle_system_workbench_v1.py',
        'handoff/工作台整车参数V2.md','handoff/当前代码阅读入口.md',
        'research/vehicle_system_workbench_v1_verification.json','AGENTS.md')
    for name in names:
        source,target=repo/name,a.freeze/'repo'/name;target.parent.mkdir(parents=True,exist_ok=True)
        if source.is_dir():shutil.copytree(source,target,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        else:shutil.copy2(source,target)
    shutil.copytree(work,a.freeze/'evidence',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    shutil.copytree(context,a.freeze/'D_context',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    (a.freeze/'README.md').write_text(
        '# 工作台整车参数 V2 冻结增量\n\n'
        '基于 state_recipe_workbench_v1/delivery1 及其基础链，先恢复基础再覆盖 repo。'
        '本增量不能脱离基础独立构建；V9 C、89个声源文件与V9 DLL保持。\n\n'
        'verification1 为实际C完整流程和参数合同；web1 为Chrome编辑/HTTP下载/历史；'
        'ui2 为最终源码的独立静音窗口一次导入和两次32秒流程/回放；ui1保留早期目录名称显示。'
        '旧四组和单状态回归保留。D_context为已批准原声/逐帧核查，不是回火音色晋升。\n\n'
        '测试夹具不是实车音色；真实启动/全频回火/其他事件与整车标定继续。'
        '自有测试服务、浏览器和窗口关闭，既有常驻服务未更新；没有新下载、上传、渲染或DSP优化。\n',encoding='utf-8')
    subprocess.run(['git','diff','--binary','--output='+str(a.freeze/'working-tree.patch')],cwd=repo,check=True)
    files=[dict(path=f.relative_to(a.freeze).as_posix(),bytes=f.stat().st_size,sha256=sha(f))
        for f in sorted(a.freeze.rglob('*')) if f.is_file()]
    save(a.freeze/'manifest.json',dict(schema='vsl.vehicle-system-workbench-delta-freeze/1',
        created=datetime.now(timezone.utc).isoformat(),base_freeze=str(base),base_manifest_sha256=sha(base/'manifest.json'),
        goal_complete=False,files=files))
    print(dict(result='frozen',files=len(files),bytes=sum(r['bytes'] for r in files),manifest_sha256=sha(a.freeze/'manifest.json')),flush=True)


if __name__=='__main__':main()
