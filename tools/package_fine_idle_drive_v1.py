"""Index and freeze the optional fine-idle driving integration and all executed attempts."""
import argparse,csv,io,subprocess,shutil,xml.etree.ElementTree as ET
from pathlib import Path
from research_archive_v1 import sha,load,save,freeze,verify,append_index
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--stage',choices=['index','freeze','verify'],required=True);a=p.parse_args()
repo=Path(__file__).resolve().parents[1];parent=a.workspace/'baselines/spectral_texture_c_v1'
evidence=a.workspace/'references/analysis/fine_idle_drive_v1';root=a.workspace/'baselines/fine_idle_drive_v1'
old=load(parent/'inputs/C_files_sha256.json');voices=load(parent/'inputs/voice_files_sha256.json')
names=subprocess.check_output(['git','ls-files','-z'],cwd=repo).decode().split('\0')
names+=subprocess.check_output(['git','ls-files','--others','--exclude-standard','-z'],cwd=repo).decode().split('\0')
names=sorted(set(n for n in names if n and (repo/n).is_file()))
current={n:sha(repo/n) for n in names if Path(n).suffix.lower() in ['.c','.h']}
assert len(old)==591 and set(old)<=set(current)
assert len(voices)==67 and all(sha(repo/n)==h for n,h in voices.items())
new=set(current)-set(old);changed={n for n in old if old[n]!=current[n]}
assert len(new)==9 and len(current)==600
assert all(current[n]==h for n,h in old.items() if n.startswith('src/'))
for n in ['experiments/modal_idle_v1/F2_fixed_idle.msource','experiments/modal_texture_v1/F2_amplitude.mtexture',
          'experiments/spectral_texture_v1/F2_fine_static.sfir','experiments/idle_state_v1/study.h']:
    raw=subprocess.check_output(['git','show','HEAD:'+n],cwd=repo)
    assert raw==(repo/n).read_bytes(),n
index=repo/'handoff/C文件索引.csv'

if a.stage=='index':
    rows=list(csv.reader(io.StringIO(index.read_text(encoding='utf-8-sig'))));assert len(rows)==592
    assert all(row[4]==old[row[0]] for row in rows[1:])
    shutil.copy2(index,evidence/'previous_C文件索引.csv')
    for row in rows[1:]:row[4]=current[row[0]]
    for n in sorted(new):
        role='独立细谱怠速参数／状态／非实时生命周期' if n.startswith('modules/') else '细谱怠速参数宿主／核查／设备验证'
        rows.append([n,'细谱怠速驾驶接入',Path(n).parts[1],role,current[n]])
    stream=io.StringIO(newline='');csv.writer(stream,lineterminator='\n').writerows(rows)
    index.write_text(stream.getvalue(),encoding='utf-8',newline='\n')
    print(dict(total=len(current),new=len(new),modified=len(changed),unchanged=len(old)-len(changed)));raise SystemExit

rows=list(csv.reader(io.StringIO(index.read_text(encoding='utf-8-sig'))))
assert len(rows)==601 and all(current[row[0]]==row[4] for row in rows[1:])
if a.stage=='freeze':
    full=load(evidence/'full1/report.json');fixed=load(evidence/'fixtures1/report.json')
    assert full['result']=='failed' and fixed['result']=='passed' and fixed['tests']==2
    tests=ET.parse(evidence/'full1/ctest.xml').getroot().findall('.//testcase')
    failures={t.attrib['name'] for t in tests if t.find('failure') is not None}
    assert len(tests)==61 and failures=={'handoff_atlas_take_contract','handoff_full_recipe_driving_contract'}
    corrections={'experiments/atlas_take_v1/checks.c','experiments/full_recipe_drive_v1/checks.c'}
    for n,h in full['sources'].items():
        assert sha(evidence/'full1/exact_sources'/n)==h
        if n not in corrections and Path(n).suffix.lower() in ['.c','.h']:assert current[n]==h,n
    for n,h in fixed['sources'].items():
        assert sha(evidence/'fixtures1/exact_sources'/n)==h
        if Path(n).suffix.lower() in ['.c','.h']:assert current[n]==h,n
    assert load(evidence/'kernel1/report.json')['result']=='failed'
    assert load(evidence/'kernel2/report.json')['result']=='passed'
    legacy=load(evidence/'legacy1/report.json');assert legacy['result']=='passed' and legacy['WAV_exact']==84 and legacy['CSV_exact']==3
    device=load(evidence/'device1/device.json')
    assert device['result']=='pass' and device['frames']==384123 and device['schema']==10 and device['fields']==32
    assert device['external_models_destroyed'] and device['two_twelve_front_and_source_exact']
    assert device['record_hash']==device['play_hash']=='24060d7d761d429c'
    build=repo/'build-fine-idle-drive-v1/bin/Release';binary=evidence/'bin';binary.mkdir()
    for n in ['VslAtlasMonitor.exe','fine_idle_layer_checks.exe','fine_idle_owned_checks.exe','fine_idle_drive_device.exe',
              'VslAtlasTake_render.exe','VslAtlasDrive_probe.exe','idle_state_probe.exe']:
        shutil.copy2(build/n,binary/n)
    save(evidence/'C_files_sha256.json',current);save(evidence/'voice_files_sha256.json',voices)
    inputs={'C_files_sha256.json':evidence/'C_files_sha256.json','voice_files_sha256.json':evidence/'voice_files_sha256.json',
            'parent_manifest.json':parent/'manifest.json','data_workspace_AGENTS.md':a.workspace/'AGENTS.md'}
    sources=[n for n in names if Path(n).suffix.lower() in ['.c','.h','.in'] or n.endswith('CMakeLists.txt')]
    sources+=[n for n in names if n.startswith('modules/') and n.endswith('README.md') and
        any(s in n for s in ['fine_idle_layer','atlas_drive','atlas_monitor','atlas_take'])]
    sources+=['tools/build_fine_idle_drive_v1.py','tools/regress_fine_idle_drive_v1.py',
        'tools/package_fine_idle_drive_v1.py','tools/research_archive_v1.py','research/fine_idle_drive_v1_plan.json',
        'research/怠速细谱统一驾驶V1.md','experiments/modal_idle_v1/F2_fixed_idle.msource',
        'experiments/modal_texture_v1/F2_amplitude.mtexture','experiments/spectral_texture_v1/F2_fine_static.sfir',
        'Build-Fine-Idle-Drive-Study.ps1','Launch-Fine-Idle-Drive-Study.cmd','AGENTS.md','handoff/算法说明.md',
        'handoff/C模块与接口.md','handoff/C文件索引.csv','handoff/开发留痕.md','handoff/研究续接.md']
    validation=dict(schema='vsl.fine-idle-drive-freeze/1',result='optional_C_fixed_idle_integration_passed_pending_listening',
        git_parent=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
        C_H_total=len(current),C_H_added=len(new),C_H_modified=len(changed),C_H_unchanged=len(old)-len(changed),
        voice_files_unchanged=67,F2_profiles_and_study_constants_unchanged=True,
        tests_distinct_passed=61,first_full_test_passed=59,corrected_version_fixtures_passed=2,
        unchanged_runtime_sources_between_full_and_fixtures=True,old_WAV_exact=84,old_CSV_exact=3,
        driver_count=1,spatial_passes=1,source_gate='RUNNING && IDLE',source_ratio=1,actual_source_RPM_known=False,
        take_schema=10,fields=32,raw_parameters_owned=True,new_capture_stems=['idle_modal','idle_detail'],
        device=device,device_block_frames=512,device_budget_ms=512000/48000,
        new_UI_manual_visual_verified=False,new_timbre_accepted=False,old_builds_overwritten=False,
        next='Judge fixed-idle core motion/fine-spectrum quality;then evidence-backed RPM/load range. No new duplicate listening question.',
        freeze='baselines/fine_idle_drive_v1')
    result=freeze(root,repo,sources,evidence,inputs,validation);verify(root)
    summary=dict(validation,**result);save(repo/'research/fine_idle_drive_v1_summary.json',summary)
    append_index(repo/'handoff/阶段索引.csv',['fine_idle_drive_v1','baselines/fine_idle_drive_v1/manifest.json',result['file_count'],
        result['manifest_sha256'],'Optional full-C fine idle;61 distinct tests;84WAV/3CSV;muted device and owned replay',
        'Listening pending;fixed unknown sourceRPM;no hardRT/new manualUI/physical7.1.4',
        'research/怠速细谱统一驾驶V1.md | research/fine_idle_drive_v1_summary.json','baselines/fine_idle_drive_v1/validation.json'])
    print(result)
else:verify(root);print('freeze verified')
