"""Protect the prior system; index and freeze the source-qualified bridge work."""
import argparse,csv,io,shutil,subprocess
from pathlib import Path
from research_archive_v1 import load,save,sha,freeze,verify,append_index
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--stage',choices=['index','freeze','verify'],required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
parent=a.workspace/'baselines/stationary_recipe_v1';root=a.workspace/'baselines/stationary_bridge_v1'
evidence=a.workspace/'references/analysis/stationary_bridge_v1'
if a.stage=='verify':verify(root);print('stationary bridge archive verified');raise SystemExit
old=load(parent/'inputs/C_files_sha256.json');voices=load(parent/'inputs/voice_files_sha256.json')
assert len(old)==640 and len(voices)==70
assert all(sha(repo/n)==h for n,h in old.items()) and all(sha(repo/n)==h for n,h in voices.items())
names=subprocess.check_output(['git','ls-files','-z'],cwd=repo).decode('utf-8').split('\0')
names+=subprocess.check_output(['git','ls-files','--others','--exclude-standard','-z'],cwd=repo).decode('utf-8').split('\0')
names=sorted(set(n for n in names if n and (repo/n).is_file()))
current={n:sha(repo/n) for n in names if Path(n).suffix in ('.c','.h')};new=set(current)-set(old)
assert len(current)==643 and len(new)==3 and all(n.startswith('experiments/stationary_bridge_v1/') for n in new)
index=repo/'handoff/C文件索引.csv';rows=list(csv.reader(index.open(encoding='utf-8-sig')))
if a.stage=='index':
    assert len(rows)==641 and all(row[4]==old[row[0]] for row in rows[1:])
    shutil.copy2(index,evidence/'prior_C_index.csv')
    for n in sorted(new):rows.append([n,'驻车中间声线候选','独立非实时实验宿主',
        '只装载原四个DNA与一个合格中间DNA及对应细节；两个未合格源窗排除' if n.endswith(('models.c','models.h')) else
        '原踏板场景、实际遥测、干声与自包含行程导出；不修改原驾驶控制器',current[n]])
    output=io.StringIO(newline='');csv.writer(output,lineterminator='\n').writerows(rows)
    index.write_text(output.getvalue(),encoding='utf-8',newline='\n');print('643 C/H indexed;640 prior exact');raise SystemExit
assert len(rows)==644 and all(row[4]==current[row[0]] for row in rows[1:])
fit=load(evidence/'fit2/report.json');audit=load(evidence/'audit2/report.json');drive=load(evidence/'drive1/report.json')
review=load(evidence/'review2/report.json');browser=load(evidence/'browser2/report.json')
assert fit['result']=='qualified_bridge_voices_rendered' and all(v['result']=='passed' for v in [audit,drive,review,browser])
assert len(fit['anchors'])==1 and len(fit['rejected'])==2 and not fit['geometric_support_connected']
assert load(evidence/'fit1/report.json')['result']=='failed'
assert len(drive['cases'])==10 and drive['old_player_owned_replays']==10 and review['clip_count']==browser['combinations']==23
assert drive['cases'][0]['render_id']=='ac51d5ddbad3414b389ed58ce55188f35eee5aa0829860207e5dfed3dfc9bff3'
for report in [fit,audit,drive]:
    for n,h in report['sources'].items():assert sha(repo/n)==h
for row in review['clips']:assert sha(evidence/'review2'/row['file'])==row['sha256']
voice=load(repo/'voices/stationary_bridge_v1/index.json')
for suffix,key in [('model','DNA_sha256'),('rdetail','detail_sha256')]:
    n='voices/stationary_bridge_v1/'+voice['name']+'.'+suffix
    assert sha(repo/n)==voice[key];voices[n]=sha(repo/n)
assert len(voices)==72
assert not any((repo/'voices/stationary_bridge_v1'/(v['name']+'.model')).exists() for v in fit['rejected'])
save(evidence/'C_files_sha256.json',current);save(evidence/'voice_files_sha256.json',voices)
dependency='tools/sustain_osc_v1/oracle.py'
parent_digests={v['path']:v['sha256'] for v in load(parent/'manifest.json')['files']}
assert sha(repo/dependency)==parent_digests['evidence/fit2/exact_sources/'+dependency]
save(evidence/'supplementary_dependency.json',dict(path=dependency,sha256=sha(repo/dependency),
    timing='Archive audit after execution; unchanged dependency bound to previous frozen fit source. Not claimed copied before this fit.'))
bin_dir=evidence/'bin';bin_dir.mkdir()
for source,label in [(evidence/'drive1/probe.exe','stationary_bridge_probe.exe'),
                     (Path(fit['commands'][0]['argv'][0]),'DNA_probe.exe'),
                     (Path(next(v['argv'][0] for v in fit['commands'] if v['log'].startswith('detail_'))),'detail_probe.exe')]:
    shutil.copy2(source,bin_dir/label)
for source in [repo/'build-stationary-bridge-v1/CMakeCache.txt',repo/'build-stationary-bridge-v1/stationary_bridge_probe.vcxproj']:
    shutil.copy2(source,evidence/source.name)
sources=[n for n in names if Path(n).suffix in ('.c','.h','.cmake','.in') or n.endswith('CMakeLists.txt')]
sources+=list(voices)+['voices/stationary_bridge_v1/index.json','experiments/stationary_bridge_v1/README.md',
 'tools/run_stationary_bridge_v1.py','tools/publish_stationary_bridge_v1.py','tools/audit_stationary_bridge_v1.py',
 'tools/review_stationary_bridge_v1.py','tools/check_stationary_bridge_v1.cjs','tools/package_stationary_bridge_v1.py',
 'tools/verify_stationary_recipe_v1.py','tools/verify_exterior_warp_v1.py','tools/research_archive_v1.py','tools/sustain_osc_v1/oracle.py',
 'tools/drive_evidence_v1/sources.py','tools/idle_texture_v1/profile.py','tools/stationary_recipe_v1/parameters.py',
 'research/stationary_bridge_v1_plan.json','research/resonant_detail_v1_plan.json',
 'research/驻车中间声线V1.md','references/segments_v1.json','voices/exterior_anchors_v1/index.json','voices/stationary_recipe_v1/index.json',
 'README.md','AGENTS.md','handoff/算法说明.md','handoff/C模块与接口.md','handoff/研究续接.md','handoff/开发留痕.md','handoff/C文件索引.csv']
for package in ['stationary_bridge_v1','sound_dna','exterior_clock_v1','residual_osc_v1','resonant_detail_v1']:
    sources += [x.relative_to(repo).as_posix() for x in (repo/'tools'/package).iterdir() if x.is_file() and x.suffix in ('.py','.html')]
validation=dict(result='one_source_qualified_bridge_C_audio_candidate',requested_new_anchors=3,published_new_anchors=1,
    rejected_new_apertures=2,C_H=643,prior_C_H_exact=640,added_C_H=3,prior_voice_parameters_exact=70,new_parameters=2,
    root_hz=voice['root_hz'],source_seconds=voice['source_seconds'],max_training_LR_band_error_db=voice['maximum_LR_band_error_db'],
    C_Python_detail_identical=True,remaining_support_gaps_hz=fit['remaining_support_gaps_hz'],full_support_completed=False,
    audio_frames_new_detail={v['label']:v['detail_supported_frames'] for v in drive['cases'] if v['label'].endswith('_2_2_240')},
    geometry_not_measured_or_audible_coverage=True,known_rapid_fall_controls=audit['subsequent_rapid_fall_controls'],
    rapid_controls_timing='Declared after real-source failure; not retroactive pre-fit qualification or complete physical phase proof',
    actual_driving=drive,browser=browser,review_URL=review['url'],figures_and_browser_images_viewed=True,
    native_default_changed=False,pending_idle_changed=False,moving35_changed=False,human_accepted=False,new_real_engines=0,
    renderer_identity_unchanged=True,old65CTests_not_repeated=True,native_device_newly_verified=False,physical_7_1_4_verified=False,
    attempts='fit1 fail-first;fit2 save/exclude individually with unchanged gates;inline diagnostic persist error;Node launch path error;all retained;review2 wording only',
    next='Hear source-qualified candidate; improve remaining source/state gaps, retain pending F2 hearing and original phase qualifications. No automatic high-chaos studies.',
    full_goal='active',git_parent=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip())
inputs={'previous_manifest.json':parent/'manifest.json','previous_C_files_sha256.json':parent/'inputs/C_files_sha256.json',
        'C_files_sha256.json':evidence/'C_files_sha256.json','voice_files_sha256.json':evidence/'voice_files_sha256.json',
        'data_AGENTS.md':a.workspace/'AGENTS.md','original_clock.json':a.workspace/'baselines/exterior_anchors_v1/evidence/anchors_v2/build.json'}
result=freeze(root,repo,sources,evidence,inputs,validation);verify(root)
save(repo/'research/stationary_bridge_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['stationary_bridge_v1','baselines/stationary_bridge_v1/manifest.json',
 result['file_count'],result['manifest_sha256'],'1sourcefit;2source windows rejected;10Cdriving+oldplayerWAVexact;23browser',
 'support gaps remain;human pending;no default/device/new-engine/physical7.1.4 acceptance',
 'research/驻车中间声线V1.md | research/stationary_bridge_v1_summary.json','baselines/stationary_bridge_v1/validation.json'])
print(result)
