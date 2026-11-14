"""Index and freeze a UI-only signed load input with unchanged DSP identity."""
import argparse
import csv
import io
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET
from research_archive_v1 import load,save,sha,freeze,verify,append_index

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--stage',choices=['index','freeze','verify'],required=True)
a=p.parse_args()
repo=Path(__file__).resolve().parents[1]
e=a.workspace/'references/analysis/bench_load_ui_v1'
root=a.workspace/'baselines/bench_load_ui_v1'
build=repo/'build-bench-load-v1'
if a.stage=='verify':verify(root);print('bench load UI archive verified');raise SystemExit
before=load(e/'before_C_files_sha256.json')
voices=load(e/'before_voice_files_sha256.json')
names=subprocess.check_output(['git','ls-files','-z'],cwd=repo).decode('utf-8').split('\0')
names+=subprocess.check_output(['git','ls-files','--others','--exclude-standard','-z'],cwd=repo).decode('utf-8').split('\0')
names=sorted(set(n for n in names if n))
current={n:sha(repo/n) for n in names if Path(n).suffix in ('.c','.h')}
changed={n for n in before if current[n]!=before[n]}
assert len(before)==len(current)==646 and set(before)==set(current)
assert changed=={'experiments/atlas_monitor_v1/ui.c','experiments/catalog_drive_v1/ui_checks.c'}
assert len(voices)==74 and all(sha(repo/n)==h for n,h in voices.items())
parent=a.workspace/'baselines/catalog_decel_v1'
f2=['experiments/modal_idle_v1/F2_fixed_idle.msource',
    'experiments/modal_texture_v1/F2_amplitude.mtexture',
    'experiments/spectral_texture_v1/F2_fine_static.sfir']
for n in f2:assert sha(repo/n)==sha(parent/'source'/n)
index=repo/'handoff/C文件索引.csv'
rows=list(csv.reader(index.open(encoding='utf-8-sig')))
assert len(rows)==647
if a.stage=='index':
    assert all(row[4]==before[row[0]] for row in rows[1:])
    for row in rows[1:]:row[4]=current[row[0]]
    target=io.StringIO(newline='');csv.writer(target,lineterminator='\n').writerows(rows)
    index.write_text(target.getvalue(),encoding='utf-8',newline='\n')
    save(e/'C_files_sha256.json',current);save(e/'voice_files_sha256.json',voices)
    print('646 C/H indexed:2 UI/check changes,644 exact;74voices/F2 exact');raise SystemExit
assert all(row[4]==current[row[0]] for row in rows[1:])
for phase in ('focused1','full1','host1'):
    result=load(e/phase/'report.json');assert result['result']=='passed'
    for n,h in result['sources'].items():assert sha(repo/n)==h==sha(e/phase/'exact_sources'/n)
tests=ET.parse(e/'full1/ctest.xml').getroot().findall('.//testcase')
assert len(tests)==66 and all(t.find('failure') is None and t.find('error') is None for t in tests)
ui=load(e/'host1/ui.json')
assert ui['result']=='pass' and ui['checks']==442 and ui['voices']==9 and ui['cross_voice_replay_and_live_restore']
assert ui['bench_load']['frames']==240123
assert all(v['queue_empty']==0 and v['budget_exceeded']==0 for v in ui['records']+[ui['bench_load']])
reg=load(e/'regress1/report.json')
assert reg['result']=='passed' and len(reg['nine_preserved'])==9 and len(reg['bench_replays'])==3 and reg['renderer_identity_unchanged']
assert sha(repo/'tools/regress_bench_load_ui_v1.py')==sha(e/'regress1/executed_regression.py')
assert sha(repo/'tools/review_bench_load_ui_v1.py')==sha(e/'review1/executed_review.py')
assert load(e/'review1/report.json')['result']=='six_native_images_ready'
bench=load(e/'host1/ui.json.bench.json')
assert bench['render_id']==load(parent/'validation.json')['render_id_after']
assert [v['load'] for v in bench['events']]==[.8,-.6,.25,0]
for n in ('default','bench','stationary','decel','replay','restored'):assert (e/'review1'/(n+'.png')).is_file()
binary=e/'bin';binary.mkdir()
for n in ('VslAtlasMonitor','VslAtlasTake_render'):
    shutil.copy2(build/f'bin/Release/{n}.exe',binary/f'{n}.exe')
sources=[n for n in names if Path(n).suffix in ('.c','.h','.cmake','.in') or n.endswith('CMakeLists.txt')]
sources+=list(voices)+f2+['tools/build_catalog_drive_v1.py','tools/regress_bench_load_ui_v1.py',
    'tools/review_bench_load_ui_v1.py','tools/package_bench_load_ui_v1.py','tools/research_archive_v1.py',
    'research/bench_load_ui_v1_plan.json','research/台架负载原生控制V1.md',
    'Build-Voice-Catalog.ps1','Launch-Voice-Catalog.cmd','README.md','AGENTS.md',
    'handoff/C文件索引.csv','handoff/C模块与接口.md','handoff/研究续接.md','handoff/开发留痕.md',
    'research/怠速优化当前状态.md','research/E_decel_source_v1_listening.json']
validation=dict(result='signed_load_input_operable_in_shared_native_bench',
    git_parent=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    C_H_total=646,C_H_changed=2,C_H_prior_exact=644,C_H_added=0,voice_parameters_exact=74,F2_exact=True,
    changed_C_H=sorted(changed),DSP_or_driver_changed=False,sound_model_fit=False,new_timbre_accepted=False,
    default_values_changed=False,mode_switch_changes_other_axis=False,renderer_identity_unchanged=True,
    render_id=bench['render_id'],take_schema=10,take_controls=32,distinct_CTests=66,
    native_UI=ui,actual_bench_control_events=bench['events'],actual_bench_frames=240123,
    actual_recording_state_checks=['RUNNING/FREE REV/.8','RUNNING/OVERRUN/-.6','FREE REV/.25'],
    original_nine_WAV_exact=True,new_bench_native_WAV_replayed_exact=True,
    frozen_same_identity_player_verified=True,new_bench_source_hash_2_12_exact=True,
    images_visually_reviewed=6,manual_mouse_verified=False,physical_load_calibrated=False,
    physical_7_1_4_verified=False,hard_realtime_claim=False,failed_attempts=[],
    old_live_windows_and_builds_preserved=True,pending_idle_and_E_hearing=True,full_goal='active',
    next='Source-supported state timbre, accepted idle hearing and independent multi-engine/spatial evidence; no automatic strength or higher-chaos work')
inputs={'original_C_files_sha256.json':e/'before_C_files_sha256.json','C_files_sha256.json':e/'C_files_sha256.json',
    'voice_files_sha256.json':e/'voice_files_sha256.json','prior_system_manifest.json':parent/'manifest.json',
    'prior_B_manifest.json':a.workspace/'baselines/B_shift_voice_v1/manifest.json','data_AGENTS.md':a.workspace/'AGENTS.md'}
result=freeze(root,repo,sources,e,inputs,validation);verify(root)
save(repo/'research/bench_load_ui_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['bench_load_ui_v1','baselines/bench_load_ui_v1/manifest.json',
    result['file_count'],result['manifest_sha256'],
    'Signed bench load;66CTest;442native checks;240123frame actual UI take;9old WAV exact;frozen replay and2/12source hash',
    'UI/check only2C changes;644C/H74voices exact;no new timbre/load calibration/hearing promotion;identity/schema unchanged',
    'research/台架负载原生控制V1.md | research/bench_load_ui_v1_summary.json','baselines/bench_load_ui_v1/validation.json'])
print(result)
