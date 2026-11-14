"""Protect synthesis/assets and freeze the optional native stationary catalog entry."""
import argparse,csv,io,shutil,subprocess,xml.etree.ElementTree as ET
from pathlib import Path
from research_archive_v1 import load,save,sha,freeze,verify,append_index
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--stage',choices=['index','freeze','verify'],required=True);a=p.parse_args()
repo=Path(__file__).resolve().parents[1];parent=a.workspace/'baselines/stationary_bridge_v1'
root=a.workspace/'baselines/catalog_bridge_v1';evidence=a.workspace/'references/analysis/catalog_bridge_v1'
build=repo/'build-catalog-bridge-v1'
if a.stage=='verify':verify(root);print('native catalog bridge archive verified');raise SystemExit
old=load(parent/'inputs/C_files_sha256.json');voices=load(parent/'inputs/voice_files_sha256.json')
assert len(old)==643 and len(voices)==72 and all(sha(repo/n)==h for n,h in voices.items())
allow={'modules/drive_catalog/catalog.c','modules/drive_catalog/catalog.h','experiments/catalog_drive_v1/models.c',
       'experiments/catalog_drive_v1/contract.c','experiments/catalog_drive_v1/ui_checks.c','experiments/atlas_monitor_v1/ui.c'}
current={n:sha(repo/n) for n in old};assert {n for n in old if current[n]!=old[n]}==allow
for n in ['experiments/modal_idle_v1/F2_fixed_idle.msource','experiments/modal_texture_v1/F2_amplitude.mtexture','experiments/spectral_texture_v1/F2_fine_static.sfir']:
    assert sha(repo/n)==sha(a.workspace/'baselines/drive_catalog_v1/source'/n)
index=repo/'handoff/C文件索引.csv';rows=list(csv.reader(index.open(encoding='utf-8-sig')))
assert len(rows)==644
if a.stage=='index':
    assert all(row[4]==old[row[0]] for row in rows[1:]);before=evidence/'before';before.mkdir()
    for n in sorted(allow|{'handoff/C文件索引.csv','handoff/CMakeLists.txt','experiments/catalog_drive_v1/CMakeLists.txt'}):
        dest=before/n;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(parent/'source'/n,dest)
    for row in rows[1:]:
        row[4]=current[row[0]]
        if row[0]=='modules/drive_catalog/catalog.c':row[3]='非实时音色身份、完整参数所有权及独立低频／辅助层实际能力'
    output=io.StringIO(newline='');csv.writer(output,lineterminator='\n').writerows(rows)
    index.write_text(output.getvalue(),encoding='utf-8',newline='\n')
    print('643 C/H indexed;6 catalog/UI/test changes,637 prior exact;72 parameters exact');raise SystemExit
assert all(row[4]==current[row[0]] for row in rows[1:])
assert load(evidence/'focused1/report.json')['result']=='failed'
assert 'LNK1104' in (evidence/'focused1/command_01.log').read_text(encoding='utf-8',errors='replace')
for phase in ['focused2','full1','host1']:
    report=load(evidence/phase/'report.json');assert report['result']=='passed'
    for n,h in report['sources'].items():
        assert sha(repo/n)==h and sha(evidence/phase/'exact_sources'/n)==h
tests=ET.parse(evidence/'full1/ctest.xml').getroot().findall('.//testcase')
assert len(tests)==65 and all(t.find('failure') is None and t.find('error') is None for t in tests)
ui=load(evidence/'host1/ui.json');reg=load(evidence/'regress1/report.json')
assert ui['result']=='pass' and ui['voices']==8 and len(ui['records'])==8 and ui['cross_voice_replay_and_live_restore']
assert reg['result']=='passed' and len(reg['cases'])==8 and all(v['full_old_new_wav_exact'] for v in reg['cases'])
for k in range(8):
    assert sha(build/f'catalog-check/voice_{k}.wav')==sha(evidence/f'regress1/new_render/voice_{k}.wav')
    assert load(evidence/f'regress1/new_render/voice_{k}.json')['render_id']=='ac51d5ddbad3414b389ed58ce55188f35eee5aa0829860207e5dfed3dfc9bff3'
    if k<7:assert sha(build/f'catalog-check/voice_{k}.wav')==sha(a.workspace/f'baselines/drive_catalog_v1/evidence/regress1/new_render/voice_{k}.wav')
for n in ['ui.json.default.png','ui.json.stationary.png','ui.json.replay.png','ui.json.restored.png']:assert (evidence/'host1'/n).is_file()
save(evidence/'C_files_sha256.json',current);save(evidence/'voice_files_sha256.json',voices)
binary=evidence/'bin';binary.mkdir()
for n in ['VslAtlasMonitor.exe','VslAtlasTake_render.exe','catalog_contract_checks.exe','catalog_render_checks.exe']:
    shutil.copy2(build/'bin/Release'/n,binary/n)
names=subprocess.check_output(['git','ls-files','-z'],cwd=repo).decode('utf-8').split('\0')
names+=subprocess.check_output(['git','ls-files','--others','--exclude-standard','-z'],cwd=repo).decode('utf-8').split('\0')
source=[n for n in sorted(set(names)) if n and (Path(n).suffix in ('.c','.h','.cmake','.in') or n.endswith('CMakeLists.txt'))]
source+=list(voices)+['modules/drive_catalog/README.md','tools/build_catalog_drive_v1.py','tools/regress_catalog_drive_v1.py',
 'tools/package_catalog_bridge_v1.py','tools/research_archive_v1.py','research/catalog_bridge_v1_plan.json','research/驻车声线接入统一窗口V1.md',
 'Build-Voice-Catalog.ps1','Launch-Voice-Catalog.cmd','README.md','AGENTS.md','handoff/算法说明.md','handoff/C模块与接口.md',
 'handoff/研究续接.md','handoff/开发留痕.md','handoff/C文件索引.csv','voices/stationary_bridge_v1/index.json',
 'experiments/modal_idle_v1/F2_fixed_idle.msource','experiments/modal_texture_v1/F2_amplitude.mtexture','experiments/spectral_texture_v1/F2_fine_static.sfir']
validation=dict(result='optional_stationary_voice_in_native_shared_driver',git_parent=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
 C_H_total=643,C_H_changed=6,C_H_prior_exact=637,C_H_added=0,voice_parameters_exact=72,DSP_unchanged=True,
 presets=8,V10_contexts=6,analytic_examples=2,new_real_engines=0,new_source_fitting=False,new_timbre_accepted=False,
 default_selection_changed=False,pending_idle_changed=False,low_capability_from_actual_config=True,
 native_UI=ui,images_visually_reviewed=4,manual_mouse_verified=False,
 actual_render_frames_per_preset=192123,original_seven_WAV_exact=True,old_player_new_eight_WAV_exact=True,
 source_driver_and_dry_stems_2_12_exact=True,owned_irregular_block_replay_exact=True,
 renderer_id_unchanged=True,distinct_CTests=65,take_schema=10,take_controls=32,
 isolated_build='build-catalog-bridge-v1;old live processes were preserved',
 failed_attempts_preserved=['focused1 linker LNK1104: existing live old executable locked; no source/test failure'],
 physical_7_1_4_verified=False,full_goal='active',next='Source/state acoustic gaps and other engines remain; pending F2 hearing is independent. No automatic higher-chaos work.')
inputs={'prior_manifest.json':parent/'manifest.json','previous_C_files_sha256.json':parent/'inputs/C_files_sha256.json',
 'C_files_sha256.json':evidence/'C_files_sha256.json','voice_files_sha256.json':evidence/'voice_files_sha256.json',
 'data_AGENTS.md':a.workspace/'AGENTS.md','original_catalog_manifest.json':a.workspace/'baselines/drive_catalog_v1/manifest.json'}
result=freeze(root,repo,source,evidence,inputs,validation);verify(root)
save(repo/'research/catalog_bridge_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['catalog_bridge_v1','baselines/catalog_bridge_v1/manifest.json',result['file_count'],result['manifest_sha256'],
 '8native presets;65CTest;7oldWAVexact;8frozen-player replay;actual low capability;native muted controls',
 '6V10contexts+2analytic examples;no new engine/source/hearing/physical7.1.4 acceptance',
 'research/驻车声线接入统一窗口V1.md | research/catalog_bridge_v1_summary.json','baselines/catalog_bridge_v1/validation.json'])
print(result)
