"""Verify source protection and archive exact driving layer-monitor evidence."""
import argparse,csv,io,shutil,subprocess,xml.etree.ElementTree as ET
from pathlib import Path
from research_archive_v1 import sha,save,load,freeze,verify,append_index
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--stage',choices=['index','freeze','verify'],required=True);a=p.parse_args()
repo=Path(__file__).resolve().parents[1];evidence=a.workspace/'references/analysis/layer_monitor_v1';root=a.workspace/'baselines/layer_monitor_v1'
before=evidence/'before';old_index=before/'source/handoff/C文件索引.csv'
old={row[0]:row[4] for row in list(csv.reader(old_index.open(encoding='utf-8-sig')))[1:]}
allowed={'experiments/atlas_monitor_v1/audio.c','experiments/atlas_monitor_v1/audio.h','experiments/atlas_monitor_v1/ui.c',
         'experiments/drive_resonance_v1/ui_checks.c','modules/atlas_drive/render.c','modules/atlas_drive/render.h',
         'modules/atlas_monitor/render.c','modules/atlas_take/player.c','modules/atlas_take/player.h'}
names=subprocess.check_output(['git','ls-files','-z'],cwd=repo).decode('utf-8').split('\0')
names+=subprocess.check_output(['git','ls-files','--others','--exclude-standard','-z'],cwd=repo).decode('utf-8').split('\0')
names=sorted(set(n for n in names if n and (repo/n).is_file()))
current={n:sha(repo/n) for n in names if Path(n).suffix in ('.c','.h')}
assert len(old)==619 and set(old)<=set(current)
assert all(sha(before/'source'/n)==h for n,h in old.items())
changed={n for n,h in old.items() if current[n]!=h};new=set(current)-set(old)
assert changed==allowed,(changed,allowed)
assert len(current)==627 and len(new)==8 and all(n.startswith(('modules/layer_monitor/','experiments/layer_monitor_v1/')) for n in new)
voices=load(before/'voice_hashes.json');assert len(voices)==67 and all(sha(repo/n)==h for n,h in voices.items())
for n in ['experiments/modal_idle_v1/F2_fixed_idle.msource','experiments/modal_texture_v1/F2_amplitude.mtexture',
          'experiments/spectral_texture_v1/F2_fine_static.sfir','experiments/idle_state_v1/study.h']:
    assert (repo/n).read_bytes()==subprocess.check_output(['git','show','8edd49a:'+n],cwd=repo),n
index=repo/'handoff/C文件索引.csv'
if a.stage=='index':
    rows=list(csv.reader(index.open(encoding='utf-8-sig')));assert len(rows)==620
    assert all(old[row[0]]==row[4] for row in rows[1:])
    for row in rows[1:]:row[4]=current[row[0]]
    for n in sorted(new):rows.append([n,'驾驶分层监听',Path(n).parts[1],
        '六条干声总线／18ms监听切换' if n.startswith('modules/') else '分层算术／新旧逐字节／原生设备验证',current[n]])
    out=io.StringIO(newline='');csv.writer(out,lineterminator='\n').writerows(rows);index.write_text(out.getvalue(),encoding='utf-8',newline='\n')
    print(dict(C_H=627,modified=9,old_unchanged=610,new=8,voices_unchanged=67));raise SystemExit
rows=list(csv.reader(index.open(encoding='utf-8-sig')));assert len(rows)==628 and all(current[row[0]]==row[4] for row in rows[1:])
if a.stage=='verify':verify(root);print('layer-monitor freeze verified');raise SystemExit

assert load(evidence/'old_build1/report.json')['result']=='failed'
assert load(evidence/'focused1/report.json')['result']=='failed'
assert load(evidence/'old_build2/report.json')['result']=='passed'
assert load(evidence/'focused2/report.json')['result']=='passed'
assert load(evidence/'full1/report.json')['result']=='passed'
tests=ET.parse(evidence/'full1/ctest.xml').getroot().findall('.//testcase')
assert len(tests)==63 and all(t.find('failure') is None and t.find('error') is None for t in tests)
for stage in ['focused2','full1']:
    report=load(evidence/stage/'report.json')
    for n,h in report['sources'].items():
        assert sha(evidence/stage/'exact_sources'/n)==h
        if n in current:assert current[n]==h,(stage,n)
integration=load(evidence/'integration1/report.json');device=load(evidence/'integration1/device/device.json');ui=load(evidence/'integration1/ui.json')
assert integration['result']=='passed' and device['result']==ui['result']=='pass'
assert device['canonical_hash']==device['heard_full_replay_hash'] and device['canonical_hash']!=device['heard_record_hash']
assert device['canonical_portable_pcm_exact'] and device['control_events']==4 and ui['manual_mouse_verified'] is False
assert load(evidence/'compatibility1/report.json')['result']=='passed'
for case in ['base2','base12','fine2','fine12']:
    for suffix in ['_pcm.bin','_trace.csv']:
        assert sha(evidence/'old_build2/probe'/(case+suffix))==sha(evidence/'integration1/canonical_new'/(case+suffix))
    assert integration['canonical'][case]['stem_sum_error']<2e-7
save(evidence/'C_files_sha256.json',current);save(evidence/'voice_files_sha256.json',voices)
binary=evidence/'bin';binary.mkdir()
for n in ['VslAtlasMonitor.exe','VslAtlasTake_render.exe','layer_canonical_probe.exe','layer_listen_checks.exe','layer_monitor_device.exe']:
    shutil.copy2(repo/'build-layer-monitor-v1/bin/Release'/n,binary/n)
source=[n for n in names if Path(n).suffix in ('.c','.h','.in','.cmake') or n.endswith('CMakeLists.txt')]
source += [n for n in names if n.startswith('modules/layer_monitor/') and n.endswith('.md')]
source += list(voices) #Actual runtime profiles, not only their digests.
source += ['tools/prepare_layer_monitor_v1.py','tools/build_layer_monitor_v1.py','tools/verify_layer_monitor_v1.py',
    'tools/package_layer_monitor_v1.py','tools/compat_layer_monitor_v1.py','tools/research_archive_v1.py','research/layer_monitor_v1_plan.json','research/驾驶分层监听V1.md',
    'Build-Layer-Monitor-Study.ps1','Launch-Layer-Monitor-Study.cmd','README.md','AGENTS.md','handoff/C模块与接口.md',
    'handoff/算法说明.md','handoff/C文件索引.csv','handoff/研究续接.md','handoff/开发留痕.md','research/怠速优化当前状态.md',
    'experiments/modal_idle_v1/F2_fixed_idle.msource','experiments/modal_texture_v1/F2_amplitude.mtexture','experiments/spectral_texture_v1/F2_fine_static.sfir']
validation=dict(schema='vsl.layer-monitor-freeze/1',result='dry_monitor_and_canonical_recording_verified',
    git_parent=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    C_H_total=627,C_H_modified=9,C_H_added=8,C_H_old_unchanged=610,voices_unchanged=67,
    distinct_CTests=63,canonical_old_new_cases=4,canonical_old_new_frames=384123*4,canonical_old_new_pcm_trace_and_hashes_exact=True,
    source_and_dry_layers_2_12_exact=True,max_dry_sum_error=max(v['stem_sum_error'] for v in integration['canonical'].values()),
    monitor_choices=7,ramp_frames=864,take_schema=10,take_fields=32,device=device,UI=ui,
    own_window_png_visually_reviewed=True,independent_computer_use_unavailable=True,
    old_schema10_frozen_player_verified=True,new_player_rejects_old_identity=True,
    first_attempts_preserved=['old_build1 missing fixture stop_frame','focused1 Winsock listen identifier collision; concurrent probe fixture edit'],
    timbre_changed=False,pending_idle_complex75_promoted=False,new_timbre_accepted=False,actual_7_1_4_verified=False,
    next='Judge pending material-derived idle rhythm candidate; then independent C transplant if supported, idle transitions and source-evidenced acceleration.',
    full_goal='active',freeze='baselines/layer_monitor_v1')
inputs={'C_files_sha256.json':evidence/'C_files_sha256.json','voice_files_sha256.json':evidence/'voice_files_sha256.json',
    'data_workspace_AGENTS.md':a.workspace/'AGENTS.md','prior_second_observer_manifest.json':a.workspace/'baselines/accel_observer_second_v1/manifest.json',
    'pending_idle_manifest.json':a.workspace/'baselines/idle_complex75_v1/manifest.json'}
result=freeze(root,repo,source,evidence,inputs,validation);verify(root)
save(repo/'research/layer_monitor_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['layer_monitor_v1','baselines/layer_monitor_v1/manifest.json',result['file_count'],result['manifest_sha256'],
    '7listening choices;63CTest;old/new4PCM+trace+hashes exact;native canonical take+solo replay',
    'No new timbre approval;idle_complex75 pending;physical7.1.4/manual mouse unverified',
    'research/驾驶分层监听V1.md | research/layer_monitor_v1_summary.json','baselines/layer_monitor_v1/validation.json'])
print(result)
