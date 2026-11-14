"""Verify protected inputs and archive the optional joint-detail recipe integration."""
import argparse,csv,io,shutil,subprocess,xml.etree.ElementTree as ET
from pathlib import Path
from research_archive_v1 import load,save,sha,freeze,verify,append_index
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--stage',choices=['index','freeze','verify'],required=True);a=p.parse_args()
repo=Path(__file__).resolve().parents[1];e=a.workspace/'references/analysis/catalog_decel_v1'
root=a.workspace/'baselines/catalog_decel_v1';build=repo/'build-catalog-decel-v1'
if a.stage=='verify':verify(root);print('catalog joint-detail archive verified');raise SystemExit
old=load(e/'before_C_files_sha256.json');voices=load(e/'before_voice_files_sha256.json')
assert len(old)==643 and len(voices)==72 and all(sha(repo/n)==h for n,h in voices.items())
names=subprocess.check_output(['git','ls-files','-z'],cwd=repo).decode('utf-8').split('\0')
names+=subprocess.check_output(['git','ls-files','--others','--exclude-standard','-z'],cwd=repo).decode('utf-8').split('\0')
names=sorted(set(n for n in names if n));current={n:sha(repo/n) for n in names if Path(n).suffix in ('.c','.h')}
changed={n for n in old if old[n]!=current[n]}
assert changed=={'modules/drive_recipe/bank.c','modules/drive_catalog/catalog.c','modules/drive_catalog/catalog.h',
                'experiments/catalog_drive_v1/models.c','experiments/catalog_drive_v1/contract.c','experiments/catalog_drive_v1/ui_checks.c'}
added={'experiments/catalog_drive_v1/decel_models.c','experiments/catalog_drive_v1/decel_models.h','experiments/catalog_drive_v1/recipe_checks.c'}
assert set(current)-set(old)==added and len(current)==646
for n in ['experiments/modal_idle_v1/F2_fixed_idle.msource','experiments/modal_texture_v1/F2_amplitude.mtexture','experiments/spectral_texture_v1/F2_fine_static.sfir']:
    assert sha(repo/n)==sha(a.workspace/'baselines/catalog_bridge_v1/source'/n)
parent=a.workspace/'baselines/E_decel_source_v1';manifest=load(parent/'manifest.json')
parent_hashes={v['path']:v['sha256'] for v in manifest['files']}
for dest,src in [('E slowing cabin.model','evidence/fit2/E Decel Earlier/voice.model'),('E slowing cabin.sres','evidence/stereo1/E slowing cabin.sres')]:
    path=repo/'voices/E_decel_source_v1'/dest
    assert sha(path)==parent_hashes[src]==sha(parent/src);voices[path.relative_to(repo).as_posix()]=sha(path)
index=repo/'handoff/C文件索引.csv';rows=list(csv.reader(index.open(encoding='utf-8-sig')))
if a.stage=='index':
    assert len(rows)==644 and all(row[4]==old[row[0]] for row in rows[1:])
    for row in rows[1:]:row[4]=current[row[0]]
    for n in sorted(added):
        role='E冻结DNA与双声道细节配方的非实时事务装载' if 'decel_models' in n else '双声道配方独立功率撤出／直接声核／失效／零量契约核查'
        rows.append([n,'目录配方接入','catalog_drive_v1',role,current[n]])
    output=io.StringIO(newline='');csv.writer(output,lineterminator='\n').writerows(rows)
    index.write_text(output.getvalue(),encoding='utf-8',newline='\n')
    print('Indexed646 C/H:6 changed,637 preserved,3 added;72 original voices exact,2 frozen E parameters added');raise SystemExit
assert len(rows)==647 and all(row[4]==current[row[0]] for row in rows[1:])
for phase in ['focused1','full1','host1']:
    r=load(e/phase/'report.json');assert r['result']=='passed'
    assert all(sha(repo/n)==h==sha(e/phase/'exact_sources'/n) for n,h in r['sources'].items())
tests=ET.parse(e/'full1/ctest.xml').getroot().findall('.//testcase')
assert len(tests)==66 and all(t.find('failure') is None and t.find('error') is None for t in tests)
ui=load(e/'host1/ui.json');reg=load(e/'regress1/report.json')
assert ui['result']=='pass' and ui['voices']==9 and len(ui['records'])==9 and ui['cross_voice_replay_and_live_restore']
assert reg['result']=='passed' and len(reg['old_cases'])==8 and len(reg['new_cases'])==len(reg['crossing'])==9
for k in range(9):
    assert sha(build/f'catalog-check/voice_{k}.wav')==sha(e/f'regress1/new_render/voice_{k}.wav')
    report=load(build/f'catalog-check/voice_{k}.json')
    assert report['render_id']==reg['new_render_id'] and report['owned_replay_PCM_exact'] and report['driver_2_12_exact'] and report['stems_2_12_exact']
for n in ['default','stationary','decel','replay','restored']:assert (e/f'host1/ui.json.{n}.png').is_file()
save(e/'C_files_sha256.json',current);save(e/'voice_files_sha256.json',voices)
binary=e/'bin';binary.mkdir()
for n in ['VslAtlasMonitor','VslAtlasTake_render','catalog_contract_checks','catalog_render_checks','catalog_recipe_checks']:
    shutil.copy2(build/f'bin/Release/{n}.exe',binary/f'{n}.exe')
sources=[n for n in names if Path(n).suffix in ('.c','.h','.cmake','.in') or n.endswith('CMakeLists.txt')]
sources+=list(voices)+['tools/build_catalog_drive_v1.py','tools/regress_catalog_decel_v1.py','tools/package_catalog_decel_v1.py','tools/research_archive_v1.py',
 'research/catalog_decel_v1_plan.json','research/减速双声道配方接入V1.md','voices/E_decel_source_v1/index.json',
 'modules/drive_catalog/README.md','modules/drive_recipe/README.md','Build-Voice-Catalog.ps1','Launch-Voice-Catalog.cmd',
 'README.md','AGENTS.md','handoff/C文件索引.csv','handoff/C模块与接口.md','handoff/算法说明.md','handoff/研究续接.md','handoff/开发留痕.md',
 'research/怠速优化当前状态.md','research/E_decel_source_v1_listening.json',
 'experiments/modal_idle_v1/F2_fixed_idle.msource','experiments/modal_texture_v1/F2_amplitude.mtexture','experiments/spectral_texture_v1/F2_fine_static.sfir']
validation=dict(result='optional_E_joint_detail_recipe_in_shared_catalog',git_parent=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
 C_H_total=646,C_H_changed=6,C_H_prior_exact=637,C_H_added=3,original_voice_parameters_exact=72,added_parameters_from_frozen_source=2,
 DSP_change='validator accepts already validated Rvs detail for withdrawal; tick algorithms unchanged',
 presets=9,V10_contexts=7,analytic_examples=2,new_real_engines=0,new_source_fit=False,new_timbre_accepted=False,
 default_selection_changed=False,pending_idle_changed=False,automatic_state_mapping_added=False,room_added=False,
 distinct_CTests=66,native_UI=ui,images_visually_reviewed=5,manual_mouse_verified=False,
 actual_render_frames_per_preset=192123,original_eight_WAV_exact=True,old_player_old_eight_WAV_exact=True,
 new_player_new_nine_WAV_exact=True,strict_cross_renderer_rejection=True,render_id_before=reg['old_render_id'],render_id_after=reg['new_render_id'],
 source_driver_and_dry_stems_2_12_exact=True,owned_irregular_block_replay_exact=True,take_schema=10,take_controls=32,
 old_live_windows_preserved=True,failed_build_test_attempts=[],physical_7_1_4_verified=False,full_goal='active',
 next='Human idle/joint-detail hearing and independent source/state support. No automatic chaos, strength sweep or pending idle C migration.')
inputs={'original_C_files_sha256.json':e/'before_C_files_sha256.json','C_files_sha256.json':e/'C_files_sha256.json',
 'original_voice_files_sha256.json':e/'before_voice_files_sha256.json','voice_files_sha256.json':e/'voice_files_sha256.json',
 'prior_catalog_manifest.json':a.workspace/'baselines/catalog_bridge_v1/manifest.json','E_source_manifest.json':parent/'manifest.json',
 'data_AGENTS.md':a.workspace/'AGENTS.md'}
result=freeze(root,repo,sources,e,inputs,validation);verify(root)
save(repo/'research/catalog_decel_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['catalog_decel_v1','baselines/catalog_decel_v1/manifest.json',result['file_count'],result['manifest_sha256'],
 '9optional presets;66CTest;8old PCM exact;9owned replay;strict renderer separation;native muted controls',
 '7V10contexts+2analytic;no idle/timbre/state/physical7.1.4 acceptance',
 'research/减速双声道配方接入V1.md | research/catalog_decel_v1_summary.json','baselines/catalog_decel_v1/validation.json'])
print(result)
