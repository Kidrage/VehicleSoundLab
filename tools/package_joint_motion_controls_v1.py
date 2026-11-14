"""Freeze known-first motion/texture diagnostics and every executed attempt."""
import argparse
import csv
from pathlib import Path
import shutil
import subprocess
from research_archive_v1 import load,save,sha,freeze,verify,append_index


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace',type=Path,required=True)
    p.add_argument('--verify',action='store_true')
    a=p.parse_args();repo=Path(__file__).resolve().parents[1]
    e=a.workspace/'references/analysis/joint_motion_controls_v1'
    root=a.workspace/'baselines/joint_motion_controls_v1'
    if a.verify:
        m=verify(root);print(dict(result='archive_verified',files=m['file_count'],bytes=m['bytes']));return
    previous=a.workspace/'baselines/F3_driver_joint_v1'
    assert sha(previous/'manifest.json')==load(repo/'research/F3_driver_joint_v1_summary.json')['manifest_sha256']
    c_files,voices,f2=[load(previous/'evidence'/name) for name in ['C_files_sha256.json','voice_files_sha256.json','F2_files_sha256.json']]
    assert len(c_files)==670 and len(voices)==82 and len(f2)==3
    for n,h in dict(c_files,**voices,**f2).items():assert sha(repo/n)==h
    names=set()
    for flags in [['ls-files','-z'],['ls-files','--others','--exclude-standard','-z']]:
        names.update(subprocess.check_output(['git']+flags,cwd=repo).decode('utf8').split('\0'))
    names.discard('')
    assert {n for n in names if Path(n).suffix in ('.c','.h')}==set(c_files)
    index=list(csv.reader((repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig',newline='')))
    assert len(index)==671 and all(row[4]==c_files[row[0]] for row in index[1:])
    parent_entries={r['path']:r['sha256'] for r in load(previous/'manifest.json')['files']}
    assert sha(repo/'handoff/C文件索引.csv')==parent_entries['source/handoff/C文件索引.csv']
    for name,rows in [('C_files_sha256.json',c_files),('voice_files_sha256.json',voices),('F2_files_sha256.json',f2)]:save(e/name,rows)
    known,real=[load(e/n/'report.json') for n in ['known1','real1']]
    assert known['result']=='known_motion_and_AM_observed' and len(known['cases'])==19
    assert real['result']=='frozen_C_source_motion_texture_ablations_observed' and len(real['cases'])==16
    assert known['C_known_576000frame_WAV_exact']
    assert sha(e/'known1/local_atlas_export.exe')==known['binary_sha256']==real['binary_sha256']
    assert known['binary_sha256']=='90ce22a9169689121f3d2c41b49ae8994dfcb6f1f043f85c395efa4912990d6f'
    for folder,report in [('known1',known),('real1',real)]:
        for n,h in report['sources'].items():assert sha(repo/n)==sha(e/folder/'exact_sources'/n)==h
        for n,h in report['inputs'].items():assert sha(n)==h
        for cmd in report['commands']:assert cmd['exit_code']==0 and sha(e/folder/cmd['log'])==cmd['sha256']
        for row in report['cases']:
            assert sha(e/folder/row['label']/'arrays.npz')==row['arrays_sha256']
            for suffix,h in row.get('C_files_sha256',{}).items():assert sha((e/folder/row['label']/'C_source').with_suffix(suffix))==h
    old=a.workspace/'baselines/F3_local_atlas_v1'
    assert sha(old/'manifest.json')==load(repo/'research/F3_local_atlas_v1_summary.json')['manifest_sha256']
    old_entries={row['path']:row['sha256'] for row in load(old/'manifest.json')['files']}
    assert sha(e/'known1/C_known/replay.wav')==old_entries['evidence/known1/analytic.wav']
    audits={n:load(e/n/'report.json') for n in ['known_audit1','real_audit1','real_audit2']}
    for n in ['known_audit1','real_audit2']:
        audit=audits[n];count=19 if n.startswith('known') else 16;study='known1' if n.startswith('known') else 'real1'
        assert audit['result']=='independent_motion_observation_audit_passed'
        assert len(audit['cases'])==count and audit['windows']==137*count and audit['DFT_complex_values']==137*count*48
        assert audit['producer_report_sha256']==sha(e/study/'report.json')
        assert audit['auditor_sha256']==sha(e/n/'executed_audit.py')
    assert sha(repo/'tools/audit_joint_motion_controls_v1.py')==audits['real_audit2']['auditor_sha256']
    assert audits['real_audit1']['result']=='failed' and not audits['real_audit1']['cases']
    assert 'TypeError' in audits['real_audit1']['error'] and (e/'real_audit1/executed_audit.py').is_file()
    reviews={n:load(e/n/'report.json') for n in ['review1','review2']}
    for name,report in reviews.items():
        assert report['result']=='motion_texture_ablation_observations_published'
        assert report['known_report_sha256']==sha(e/'known1/report.json') and report['real_report_sha256']==sha(e/'real1/report.json')
        assert report['known_audit_report_sha256']==sha(e/'known_audit1/report.json') and report['real_audit_report_sha256']==sha(e/'real_audit2/report.json')
        assert report['pairs_sha256']==sha(e/name/'pairs.json')
        for image,h in report['images'].items():assert sha(e/name/image)==h
        for row in load(e/name/'pairs.json')['pairs']:assert sha(e/name/row['label']/'log_covariance_budget.npz')==row['arrays_sha256']
    assert reviews['review1']['pairs_sha256']==reviews['review2']['pairs_sha256']
    assert reviews['review1']['images']['known_motion_AM.png']==reviews['review2']['images']['known_motion_AM.png']
    assert not load(e/'review1/visual_review.json')['accepted_for_final_publication']
    visual=load(e/'review2/visual_review.json')
    assert visual['two_scientific_figures_individually_viewed'] and visual['accepted_for_final_publication']
    assert visual['images_sha256']==reviews['review2']['images']
    assert sha(repo/'tools/review_joint_motion_controls_v1.py')==sha(e/'review2/executed_review.py')
    validation=dict(result='motion_and_texture_ablations_verified',
        parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
        previous_goal_turn='Progress: original-driver capture and native joint budget committed8d94b66; current controlled source ablations distinguish motion from statistical texture.',
        C_H_exact=670,voice_parameters_exact=82,F2_exact=True,C_index_exact=True,new_C_H=0,
        known_cases=19,known_windows=2603,known_DFT_complex_values=124944,
        real_cases=16,real_windows=2192,real_DFT_complex_values=105216,
        known_audit={k:v for k,v in audits['known_audit1'].items() if k!='cases'},
        real_audit={k:v for k,v in audits['real_audit2'].items() if k!='cases'},
        known_C_576000frame_WAV_exact=True,frozen_C_binary_sha256=known['binary_sha256'],
        real_observations=real['cases'],known_observations=known['cases'],paired_budgets=12,
        signed_covariance_interactions_retained=True,
        source_only_not_full_driver=True,source_phase_to_amplitude_hypothesis_unproven=True,
        numeric_audit_list_type_failure_retained=True,figure_category_colour_correction_retained=True,
        scientific_figures_viewed=2,heard=False,new_audio_candidate=False,runtime_preset=False,
        runtime_DSP_model_default_driver_owned_take_room_changed=False,
        unchanged_68CTest_not_repeated=True,F2_F3_hearings='independently pending, no repeat or blind strengths',
        E_feedback='左右关系有改善，音色仍明显电子',downloaded=False,pushed=False,physical_7_1_4=False,
        full_goal='active',next='Qualify known amplitude-only/phase-only coefficient moments through original compiler and C magnitude mapping, then examine original F3 magnitudes/phases and stereo dependence before any joint texture replacement. Do not revive rejected A magnitude models or blindly remove common motion.')
    sources=[n for n in names if Path(n).suffix in ('.c','.h','.cmake','.in') or n.endswith('CMakeLists.txt')]
    sources+=list(voices)+list(f2)+list(known['sources'])
    sources+=['tools/audit_joint_motion_controls_v1.py','tools/review_joint_motion_controls_v1.py','tools/package_joint_motion_controls_v1.py',
        'tools/joint_motion_controls_v1/README.md','tools/local_atlas_v1/oracle.py','tools/sustain_osc_v1/oracle.py',
        'tools/idle_texture_v1/profile.py','tools/sound_dna/statistics.py','tools/research_archive_v1.py',
        'research/变速与统计纹理分离诊断V1.md','README.md','AGENTS.md',
        'handoff/C文件索引.csv','handoff/开发留痕.md','handoff/研究续接.md','handoff/当前代码阅读入口.md']
    inputs=dict(data_AGENTS=a.workspace/'AGENTS.md',parent_driver_manifest=previous/'manifest.json',
        parent_driver_validation=previous/'validation.json',frozen_C_build_source_zip=old/'source.zip',
        frozen_C_parent_manifest=old/'manifest.json',native_measurement_plan=a.workspace/'baselines/F3_joint_envelopes_v1/source/research/F3_joint_envelopes_v1_plan.json')
    shutil.copy2(__file__,e/'executed_package.py')
    result=freeze(root,repo,sources,e,inputs,validation);verify(root)
    save(repo/'research/joint_motion_controls_v1_summary.json',dict(validation,**result))
    append_index(repo/'handoff/阶段索引.csv',[
        'joint_motion_controls_v1','baselines/joint_motion_controls_v1/manifest.json',result['file_count'],result['manifest_sha256'],
        '19known2603windows124944DFT;16C2192windows105216DFT;sparse-clock-phase;12signed-log-budgets;2figures',
        '670C-H82voices/F2 exact;static mean HFstd<.001dB versus texture1.1..2.3;motion/AM distinction;old audit and visual failures kept;no runtime migration',
        'research/变速与统计纹理分离诊断V1.md | research/joint_motion_controls_v1_summary.json','baselines/joint_motion_controls_v1/validation.json'])
    print(result)


if __name__=='__main__':main()
