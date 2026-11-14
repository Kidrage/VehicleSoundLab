"""Protect prior C/models and freeze the actual unified catalog integration."""
import argparse,csv,io,shutil,subprocess,xml.etree.ElementTree as ET
from pathlib import Path
from research_archive_v1 import load,save,sha,freeze,verify,append_index
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--stage',choices=['index','freeze','verify'],required=True);a=p.parse_args()
repo=Path(__file__).resolve().parents[1];parent=a.workspace/'baselines/layer_monitor_v1';root=a.workspace/'baselines/drive_catalog_v1'
evidence=a.workspace/'references/analysis/drive_catalog_v1'
old=load(parent/'inputs/C_files_sha256.json');voices=load(parent/'inputs/voice_files_sha256.json')
names=subprocess.check_output(['git','ls-files','-z'],cwd=repo).decode('utf-8').split('\0')
names+=subprocess.check_output(['git','ls-files','--others','--exclude-standard','-z'],cwd=repo).decode('utf-8').split('\0')
names=sorted(set(n for n in names if n and (repo/n).is_file()))
current={n:sha(repo/n) for n in names if Path(n).suffix in ('.c','.h')}
assert len(old)==627 and set(old)<=set(current)
changed={n for n,h in old.items() if current[n]!=h};new=set(current)-set(old)
assert changed=={'experiments/atlas_monitor_v1/ui.c'} and len(new)==10 and len(current)==637
assert all(n.startswith(('modules/drive_catalog/','experiments/catalog_drive_v1/')) for n in new)
assert len(voices)==67 and all(sha(repo/n)==h for n,h in voices.items())
for n in ['experiments/modal_idle_v1/F2_fixed_idle.msource','experiments/modal_texture_v1/F2_amplitude.mtexture','experiments/spectral_texture_v1/F2_fine_static.sfir']:
    assert sha(repo/n)==sha(parent/'source'/n),n
index=repo/'handoff/C文件索引.csv'
if a.stage=='index':
    rows=list(csv.reader(index.open(encoding='utf-8-sig')));assert len(rows)==628 and all(row[4]==old[row[0]] for row in rows[1:])
    before=evidence/'before';before.mkdir()
    for n in ['experiments/atlas_monitor_v1/ui.c','handoff/CMakeLists.txt','handoff/C文件索引.csv']:
        dest=before/n;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(parent/'source'/n,dest)
    for row in rows[1:]:row[4]=current[row[0]]
    for n in sorted(new):rows.append([n,'统一音色目录',Path(n).parts[1],
        '非实时只读资源／目录与声层能力' if n.startswith('modules/') else '已有配方装载／会话生命周期／实际驾驶录放与自身UI验证',current[n]])
    output=io.StringIO(newline='');csv.writer(output,lineterminator='\n').writerows(rows);index.write_text(output.getvalue(),encoding='utf-8',newline='\n')
    print(dict(C_H=637,modified=1,new=10,old_unchanged=626,voices_unchanged=67));raise SystemExit
rows=list(csv.reader(index.open(encoding='utf-8-sig')));assert len(rows)==638 and all(row[4]==current[row[0]] for row in rows[1:])
if a.stage=='verify':verify(root);print('catalog freeze verified');raise SystemExit
assert load(evidence/'focused1/report.json')['result']=='passed'
assert load(evidence/'host1/report.json')['result']=='failed' and load(evidence/'host1/ui.json')['failed_line']==54
assert load(evidence/'host2/report.json')['result']=='passed'
assert load(evidence/'full1/report.json')['result']=='passed'
tests=ET.parse(evidence/'full1/ctest.xml').getroot().findall('.//testcase')
assert len(tests)==65 and all(t.find('failure') is None and t.find('error') is None for t in tests)
for phase in ['host2','full1']:
    for n,h in load(evidence/phase/'report.json')['sources'].items():
        assert sha(evidence/phase/'exact_sources'/n)==h
        if n in current:assert current[n]==h,(phase,n)
ui=load(evidence/'host2/ui.json');reg=load(evidence/'regress1/report.json')
assert ui['result']=='pass' and ui['checks']==207 and ui['cross_voice_replay_and_live_restore'] and len(ui['records'])==7
assert reg['result']=='passed' and len(reg['cases'])==7 and all(c['full_old_new_wav_exact'] for c in reg['cases'])
for k in range(7):
    assert sha(repo/f'build-catalog-drive-v1/catalog-check/voice_{k}.wav')==sha(evidence/f'regress1/new_render/voice_{k}.wav')
    assert load(evidence/f'regress1/new_render/voice_{k}.json')['render_id']=='ac51d5ddbad3414b389ed58ce55188f35eee5aa0829860207e5dfed3dfc9bff3'
for n in ['ui.json.default.png','ui.json.replay.png','ui.json.restored.png']:assert (evidence/'host2'/n).is_file()
save(evidence/'C_files_sha256.json',current);save(evidence/'voice_files_sha256.json',voices)
binary=evidence/'bin';binary.mkdir()
for n in ['VslAtlasMonitor.exe','VslAtlasTake_render.exe','catalog_contract_checks.exe','catalog_render_checks.exe']:
    shutil.copy2(repo/'build-catalog-drive-v1/bin/Release'/n,binary/n)
source=[n for n in names if Path(n).suffix in ('.c','.h','.cmake','.in') or n.endswith('CMakeLists.txt')]
source+=list(voices)+['modules/drive_catalog/README.md','tools/build_catalog_drive_v1.py','tools/regress_catalog_drive_v1.py',
    'tools/package_catalog_drive_v1.py','tools/research_archive_v1.py','research/drive_catalog_v1_plan.json','research/统一音色目录V1.md',
    'Build-Voice-Catalog.ps1','Launch-Voice-Catalog.cmd','README.md','AGENTS.md','handoff/算法说明.md','handoff/C模块与接口.md',
    'handoff/研究续接.md','handoff/开发留痕.md','handoff/C文件索引.csv','research/怠速优化当前状态.md',
    'experiments/modal_idle_v1/F2_fixed_idle.msource','experiments/modal_texture_v1/F2_amplitude.mtexture','experiments/spectral_texture_v1/F2_fine_static.sfir']
validation=dict(schema='vsl.drive-catalog-freeze/1',result='unified_owned_presets_and_existing_renderer_verified',
    git_parent=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    C_H_total=637,C_H_modified=1,C_H_added=10,C_H_old_unchanged=626,voices_unchanged=67,DSP_C_unchanged=True,
    presets=7,V10_contexts=5,analytic_examples=2,distinct_real_engines_fitted_this_turn=0,
    distinct_CTests=65,actual_render_frames_per_preset=192123,old_new_full_WAV_exact=7,
    source_driver_and_dry_stems_2_12_exact=True,owned_irregular_block_replay_exact=True,
    renderer_identity_unchanged=True,take_schema=10,take_fields=32,UI=ui,UI_three_images_visually_reviewed=True,
    manual_mouse_verified=False,pending_idle_complex75_promoted=False,new_timbre_accepted=False,physical_7_1_4_verified=False,
    attempts_preserved=['host1 recorded voice menu lock failure','host2 corrected capability/menu/owned replay and live restore passed'],
    next='Continue source-evidenced idle/acceleration timbres and state transitions;pending idle hearing remains independent. No automatic high-chaos continuation.',
    full_goal='active',freeze='baselines/drive_catalog_v1')
inputs={'prior_manifest.json':parent/'manifest.json','previous_C_files_sha256.json':parent/'inputs/C_files_sha256.json',
    'C_files_sha256.json':evidence/'C_files_sha256.json','voice_files_sha256.json':evidence/'voice_files_sha256.json',
    'data_workspace_AGENTS.md':a.workspace/'AGENTS.md','pending_idle_manifest.json':a.workspace/'baselines/idle_complex75_v1/manifest.json'}
result=freeze(root,repo,source,evidence,inputs,validation);verify(root)
save(repo/'research/drive_catalog_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['drive_catalog_v1','baselines/drive_catalog_v1/manifest.json',result['file_count'],result['manifest_sha256'],
    '7owned recipes;65CTest;7actual prior-player WAV exact;207 native UI/device checks;2/12sources',
    '5 V10 contexts+2 analytic examples;no new real-engine fitting;idle candidate pending;physical7.1.4/manual mouse unverified',
    'research/统一音色目录V1.md | research/drive_catalog_v1_summary.json','baselines/drive_catalog_v1/validation.json'])
print(result)
