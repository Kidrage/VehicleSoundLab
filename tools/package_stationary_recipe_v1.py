"""Protect the prior system and freeze all executed stationary recipe attempts."""
import argparse,csv,io,shutil,subprocess
from pathlib import Path
from research_archive_v1 import load,save,sha,freeze,verify,append_index
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--stage',choices=['index','freeze','verify'],required=True);a=p.parse_args()
repo=Path(__file__).resolve().parents[1];parent=a.workspace/'baselines/drive_catalog_v1'
root=a.workspace/'baselines/stationary_recipe_v1';evidence=a.workspace/'references/analysis/stationary_recipe_v1'
if a.stage=='verify':verify(root);print('stationary recipe freeze verified');raise SystemExit
old=load(parent/'inputs/C_files_sha256.json');voices=load(parent/'inputs/voice_files_sha256.json')
assert len(old)==637 and len(voices)==67
assert all(sha(repo/n)==h for n,h in old.items()) and all(sha(repo/n)==h for n,h in voices.items())
names=subprocess.check_output(['git','ls-files','-z'],cwd=repo).decode('utf-8').split('\0')
names+=subprocess.check_output(['git','ls-files','--others','--exclude-standard','-z'],cwd=repo).decode('utf-8').split('\0')
names=sorted(set(n for n in names if n and (repo/n).is_file()))
current={n:sha(repo/n) for n in names if Path(n).suffix in ('.c','.h')}
new=set(current)-set(old)
assert len(current)==640 and len(new)==3 and all(n.startswith('experiments/stationary_recipe_v1/') for n in new)
index=repo/'handoff/C文件索引.csv';rows=list(csv.reader(index.open(encoding='utf-8-sig')))
if a.stage=='index':
    assert len(rows)==638 and all(row[4]==old[row[0]] for row in rows[1:])
    shutil.copy2(index,evidence/'prior_C_index.csv')
    for n in sorted(new):rows.append([n,'驻车配方候选','独立非实时实验宿主',
        '只装载原DNA与三个独立细节参数；原驾驶控制／混音／行程接口不变' if n.endswith(('models.c','models.h')) else
        '原踏板场景与实际遥测／分层／行程导出；离线文件IO在宿主',current[n]])
    output=io.StringIO(newline='');csv.writer(output,lineterminator='\n').writerows(rows)
    index.write_text(output.getvalue(),encoding='utf-8',newline='\n');print('640 C/H indexed;637 prior exact');raise SystemExit
assert len(rows)==641 and all(row[4]==current[row[0]] for row in rows[1:])
fit=load(evidence/'fit2/report.json');drive=load(evidence/'drive2/report.json')
review=load(evidence/'review2/report.json');browser=load(evidence/'browser2/report.json')
assert fit['result']=='four_stationary_candidates_rendered' and drive['result']==review['result']==browser['result']=='passed'
assert len(drive['cases'])==10 and drive['old_player_owned_replays']==10 and review['clip_count']==browser['combinations']==30
assert load(evidence/'fit1/report.json')['result']=='failed' and load(evidence/'drive1/report.json')['result']=='failed'
assert 'error C4013' in (evidence/'build1.log').read_text(encoding='utf-8',errors='replace')
assert sha(evidence/'fit1/A Stationary Low/detail.rdetail')==sha(evidence/'fit2/A Stationary Low/detail.rdetail')
for n,h in drive['sources'].items():assert sha(repo/n)==h and sha(evidence/'drive2/exact_sources'/n)==h
for n,h in fit['sources'].items():assert sha(repo/n)==h and sha(evidence/'fit2/exact_sources'/n)==h
maximum=[]
for row in fit['anchors'][1:]:
    errors=[abs(v) for run in row['renders'] for band in run['metrics'] for v in band['power_delta_db']]
    maximum.append(max(errors));assert max(errors)<.5 and row['C_detail_oracle_FS']<=1e-10
    n='voices/stationary_recipe_v1/'+row['name']+'.rdetail';assert sha(repo/n)==row['detail_sha256']
    voices[n]=sha(repo/n)
assert len(voices)==70
for row in review['clips']:
    assert sha(evidence/'review2'/row['file'])==row['sha256']
save(evidence/'C_files_sha256.json',current);save(evidence/'voice_files_sha256.json',voices)
bin_dir=evidence/'bin';bin_dir.mkdir();shutil.copy2(evidence/'drive2/probe.exe',bin_dir/'stationary_recipe_probe.exe')
sources=[n for n in names if Path(n).suffix in ('.c','.h','.cmake','.in') or n.endswith('CMakeLists.txt')]
sources+=list(voices)+['voices/stationary_recipe_v1/index.json','experiments/stationary_recipe_v1/README.md',
 'tools/sound_dna/statistics.py','tools/run_stationary_recipe_v1.py',
 'tools/verify_stationary_recipe_v1.py','tools/review_stationary_recipe_v1.py','tools/package_stationary_recipe_v1.py',
 'tools/check_stationary_recipe_v1.cjs','tools/stationary_recipe_v1/parameters.py','tools/stationary_recipe_v1/review.html',
 'tools/research_archive_v1.py','research/stationary_recipe_v1_plan.json','research/驻车共振细节与驾驶V1.md',
 'README.md','AGENTS.md','handoff/算法说明.md','handoff/C模块与接口.md','handoff/研究续接.md',
 'handoff/开发留痕.md','handoff/C文件索引.csv','research/怠速优化当前状态.md']
validation=dict(result='three_stationary_fits_and_same_controller_audio_candidate',
 C_H=640,prior_C_H_exact=637,added_C_H=3,prior_voice_files_exact=67,new_detail_profiles=3,
 raw_recordings_fitted=1,new_real_engines=0,stationary_root_hz=[row['root_hz'] for row in fit['anchors'][1:]],
 maximum_LR_band_errors_db=maximum,C_Python_detail_identical=True,
 low_anchor_not_promoted=True,old65CTests_not_repeated=True,actual_driving=drive,
 browser=browser,figures_and_desktop_mobile_screenshots_viewed=True,review_URL=review['url'],
 renderer_identity_unchanged=True,renderer_id=drive['cases'][0]['render_id'],schema=10,control_fields=32,
 native_UI_default_changed=False,native_device_newly_verified=False,human_accepted=False,
 pending_F2_idle_changed=False,moving35_changed=False,actual_7_1_4_verified=False,
 failures_preserved=['fit1 missing probe warmup','build1 missing engine function declaration',
                    'drive1 missing12channel replay argument','review1 support text correction after old checks passed'],
 next='Hear stationary candidate; fill source-supported anchor/condition gaps. F2 idle candidate still pending. Do not infer full engine/state/space qualification from these renders.',
 full_goal='active',git_parent=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip())
inputs={'previous_manifest.json':parent/'manifest.json','previous_C_files_sha256.json':parent/'inputs/C_files_sha256.json',
        'C_files_sha256.json':evidence/'C_files_sha256.json','voice_files_sha256.json':evidence/'voice_files_sha256.json',
        'data_AGENTS.md':a.workspace/'AGENTS.md'}
result=freeze(root,repo,sources,evidence,inputs,validation);verify(root)
save(repo/'research/stationary_recipe_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['stationary_recipe_v1','baselines/stationary_recipe_v1/manifest.json',
 result['file_count'],result['manifest_sha256'],'3sourcefit;12staticrenders;10Cdriving+oldplayerWAVexact;zero/chunk/2-12;30browser',
 'low not promoted;human pending;no default/device/new-engine/physical7.1.4 acceptance',
 'research/驻车共振细节与驾驶V1.md | research/stationary_recipe_v1_summary.json','baselines/stationary_recipe_v1/validation.json'])
print(result)
