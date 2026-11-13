"""Archive isolated fast-detail C implementation and real muted device evidence."""
import argparse,json,subprocess
from pathlib import Path
from research_archive_v1 import sha,load,save,freeze,verify,append_index
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--stage',choices=['freeze','verify'],required=True);a=p.parse_args()
repo=Path(__file__).resolve().parents[1];evidence=a.workspace/'references/analysis/idle_microtexture_c_v1'
root=a.workspace/'baselines/idle_microtexture_c_v1';parent=a.workspace/'baselines/idle_microtexture_v1'
old=load(parent/'inputs/C_files_sha256.json');voices=load(parent/'inputs/voice_files_sha256.json')
assert len(old)==600 and len(voices)==67 and all(sha(repo/key)==value for key,value in {**old,**voices}.items())
if a.stage=='verify':verify(root);print('freeze verified');raise SystemExit
report=load(evidence/'verify1/report.json');assert report['result']=='isolated_fast_detail_C_and_muted_device_verified'
assert report['tests']==6 and len(report['comparisons'])==30 and report['maximum_FS_error']<1e-7
assert report['device']['frames']==384123 and report['device']['offline_exact'] and report['device']['muted']
for name,h in report['sources'].items():assert sha(evidence/'verify1/exact_sources'/name)==sha(repo/name)==h
for row in report['commands']:assert row['return_code']==0 and sha(evidence/'verify1'/(row['label']+'.log'))==row['log_sha256']
for row in report['comparisons']:
    paths=list((evidence/'verify1').rglob('*_'+row['bus']+'.wav'))
    assert any(sha(path)==row['sha256'] for path in paths)
current={path.relative_to(repo).as_posix():sha(path) for folder in ['src','modules','experiments','tests','tools','handoff']
    for path in (repo/folder).rglob('*') if path.suffix.lower() in ['.c','.h'] and path.is_file()}
assert all(current.get(key)==value for key,value in old.items());new=set(current)-set(old);assert len(new)==12 and len(current)==612
launch=json.loads((evidence/'ui_launch.json').read_text(encoding='utf-8-sig'))
assert launch['Responding'] and launch['MainWindowTitle']=='Vehicle Sound Lab · Fast Idle'
save(evidence/'C_files_sha256.json',current)
source=list(report['sources'])+['tools/package_idle_microtexture_c_v1.py','research/怠速快速颗粒C监听V1.md',
    'modules/spectral_motion/README.md','AGENTS.md','handoff/研究续接.md','handoff/开发留痕.md']
validation=dict(schema='vsl.idle-microtexture-c-freeze/1',result='optional_C_source_and_muted_device_verified_timbre_pending',
    parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    tests=6,comparisons=30,maximum_FS_error=report['maximum_FS_error'],device=report['device'],
    sample_controls1_479_byte_exact=True,core_independent_of_detail_controls=True,sustained_prefix_exact=True,
    old_C_H_unchanged=600,new_C_H=12,current_C_H=612,old_voices_unchanged=67,
    old61_driving_tests_repeated=False,original_binaries_and_takes_preserved=True,
    source_parameters_refitted=False,room=False,recorded_trajectory=False,
    native_UI_compiled_and_process_responding=True,native_UI_manual_or_visual_verified=False,
    driver_integrated=False,timbre_acceptance=False,hard_realtime=False,original_listening_question_repeated=False,
    next='Judge existing idle grain/sand/tremor before production driving/take adoption; preserve phase/RPM/load/spatial evidence limits')
inputs={'C_files_sha256.json':evidence/'C_files_sha256.json','voice_files_sha256.json':parent/'inputs/voice_files_sha256.json',
    'parent_manifest.json':parent/'manifest.json','parent_fast_profile.json':parent/'evidence/trial1/profile.json',
    'parent_source_profile.json':parent/'inputs/F2_parent_profile.json','data_workspace_AGENTS.md':a.workspace/'AGENTS.md'}
result=freeze(root,repo,source,evidence,inputs,validation);verify(root)
save(repo/'research/idle_microtexture_c_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['idle_microtexture_c_v1','baselines/idle_microtexture_c_v1/manifest.json',result['file_count'],result['manifest_sha256'],
    '6module/host tests;all9frozen candidates/30comparisons;actual384123frame muted device exact;C600unchanged+12new',
    'Native UI compiled/responding but manual/visual/listening unverified;no driver/default/take promotion;singleframe budget378overruns retained',
    'research/怠速快速颗粒C监听V1.md | research/idle_microtexture_c_v1_summary.json','baselines/idle_microtexture_c_v1/validation.json'])
print(result)
