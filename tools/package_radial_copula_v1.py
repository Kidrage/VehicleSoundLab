"""Freeze positive radial/phase candidates, all failures and unchanged runtime contracts."""
import argparse
import csv
import os
from pathlib import Path
import shutil
import subprocess
import sys
from research_archive_v1 import load,save,sha,freeze,verify,append_index


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace',type=Path,required=True);p.add_argument('--verify',action='store_true')
    a=p.parse_args();repo=Path(__file__).resolve().parents[1]
    evidence=a.workspace/'references/analysis/radial_copula_v1';root=a.workspace/'baselines/radial_copula_v1'
    if a.verify:
        m=verify(root);print(dict(result='archive_verified',files=m['file_count'],bytes=m['bytes']));return
    for n in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[n]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    import soundfile as sf
    previous=a.workspace/'baselines/coefficient_geometry_v1'
    assert sha(previous/'manifest.json')==load(repo/'research/coefficient_geometry_v1_summary.json')['manifest_sha256']
    protected={}
    for n,count in [('C_files_sha256.json',670),('voice_files_sha256.json',82),('F2_files_sha256.json',3)]:
        values=load(previous/'evidence'/n);assert len(values)==count
        assert all(sha(repo/name)==h for name,h in values.items());save(evidence/n,values);protected[n]=values
    names=set()
    for flags in [['ls-files','-z'],['ls-files','--others','--exclude-standard','-z']]:
        names.update(subprocess.check_output(['git']+flags,cwd=repo).decode('utf-8').split('\0'))
    names.discard('')
    assert {n for n in names if Path(n).suffix in ('.c','.h')}==set(protected['C_files_sha256.json'])
    index=list(csv.reader((repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig',newline='')))
    assert len(index)==671 and all(row[4]==protected['C_files_sha256.json'][row[0]] for row in index[1:])
    old_entries={r['path']:r['sha256'] for r in load(previous/'manifest.json')['files']}
    assert sha(repo/'handoff/C文件索引.csv')==old_entries['source/handoff/C文件索引.csv']
    reports={n:load(evidence/n/'report.json') for n in ['known1','known_audit1','known_audit2','known_audit3','real1','real2','real_audit1','review1','browser1']}
    known,failed,real=reports['known1'],reports['real1'],reports['real2']
    assert known['result']=='known_radial_phase_separation_passed' and len(known['cases'])==7
    assert failed['result']=='failed' and 'multiple values' in failed['error']
    assert real['result']=='six_radial_copula_models_and_two_anchor_audio_ready' and len(real['cases'])==6
    for folder,r in [('known1',known),('real1',failed),('real2',real)]:
        for n,h in r['sources'].items():
            assert sha(evidence/folder/'exact_sources'/n)==h
            if n!='tools/run_radial_copula_v1.py':assert sha(repo/n)==h
        for n,h in r['inputs'].items():assert sha(n)==h
        for cmd in r['commands']:assert cmd['exit_code']==0 and sha(evidence/folder/cmd['log'])==cmd['sha256']
    assert sha(repo/'tools/run_radial_copula_v1.py')==real['sources']['tools/run_radial_copula_v1.py']
    for row in known['cases']:
        folder=evidence/'known1'/row['label']
        assert sha(folder/'profile.npz')==row['profile_sha256'] and sha(folder/'training.npz')==row['training_sha256']
        assert sha(folder/'known.wav')==row['wave_sha256'] and row['known_no_AM_PM_cross_talk']
    for row in real['cases']:
        folder=evidence/'real2'/row['label'];old=evidence/'real1'/row['label']
        for name,key in [('profile.npz','profile_sha256'),('training.npz','training_sha256')]:
            assert sha(folder/name)==sha(old/name)==row[key]
        for q in row['QMC']:
            name=f'QMC_{q["seed"]}.npz';assert sha(folder/name)==sha(old/name)==q['arrays_sha256']
        for audio in row['audio']:
            assert sha(folder/audio['file'])==audio['sha256']
            wave,rate=sf.read(folder/audio['file'],always_2d=True)
            assert wave.shape==(384000,2) and rate==48000 and np.isfinite(wave).all()
        for t in row.get('temporal',[]):assert sha(folder/f'temporal_{t["seed"]}.npz')==t['sha256']
    assert sum(len(row['audio']) for row in real['cases'])==18
    assert real['cases'][1]['block37_1024_maximum_PCM_error_FS']==0
    a0=sf.read(evidence/'real1/F3 Fifth First Mid/fixed_phase_1.wav',always_2d=True)[0]
    a1=sf.read(evidence/'real2/F3 Fifth First Mid/fixed_phase_1.wav',always_2d=True)[0]
    assert np.array_equal(a0,a1)
    assert reports['known_audit2']['result']=='failed' and (evidence/'known_audit2/executed_audit.py').is_file()
    for n,study in [('known_audit1','known1'),('known_audit3','known1'),('real_audit1','real2')]:
        r=reports[n];assert r['result']=='independent_radial_copula_audit_passed'
        assert r['producer_report_sha256']==sha(evidence/study/'report.json') and r['auditor_sha256']==sha(evidence/n/'executed_audit.py')
    assert reports['known_audit3']['unchanged_known_branch_and_helpers_AST_exact']
    assert reports['known_audit3']['auditor_sha256']==reports['real_audit1']['auditor_sha256']==sha(repo/'tools/audit_radial_copula_v1.py')
    assert reports['real_audit1']['QMC_cases']==18 and reports['real_audit1']['new_waveforms']==12
    review=reports['review1'];assert review['result']=='radial_copula_one_player_review_ready' and len(review['clips'])==20
    assert review['producer_report_sha256']==sha(evidence/'real2/report.json') and review['audit_report_sha256']==sha(evidence/'real_audit1/report.json')
    for n,h in review['sources'].items():assert sha(repo/n)==sha(evidence/'review1/exact_sources'/n)==h
    for n,h in review['inputs'].items():assert sha(n)==h
    for row in review['clips']:assert sha(evidence/'review1'/row['file'])==row['sha256'] and row['peak_FS']<.95
    for n,h in review['images'].items():assert sha(evidence/'review1'/n)==h
    browser=reports['browser1'];assert browser['result']=='pass' and browser['metadata_checks']==20
    assert sha(repo/'tools/check_radial_copula_v1.cjs')==sha(evidence/'browser1/executed_check.cjs')
    visual=load(evidence/'review1/visual_review.json')
    assert visual['two_scientific_figures_individually_viewed'] and visual['desktop_mobile_individually_viewed'] and visual['accepted_for_final_publication']
    assert visual['images_sha256']==review['images'] and visual['browser_report_sha256']==sha(evidence/'browser1/report.json')
    gap=load(evidence/'review1/stereo_gap.json');assert gap['joint_worse_coordinates']==18 and gap['coordinates']==24
    validation=dict(result='radial_phase_separation_and_isolated_OSC_candidates_verified',
        parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
        previous_goal_turn='Progress: coefficient geometry/C controls and six-source mismatch established. This stage constructs new positive radial/circular models and actual audible OSC candidates.',
        C_H_exact=670,voice_parameters_exact=82,F2_exact=True,C_index_exact=True,new_C_H=0,
        known_controls=7,known_audit=reports['known_audit3'],source_models=6,QMC_cases=18,QMC_draws_per_case=4096,
        distribution_validation=real['distribution_validation'],real_audit=reports['real_audit1'],new_generated_waveforms=12,
        original_C_baselines=6,short_original_references=2,review_clips=20,
        block37_1024_PCM_exact=True,metadata_only_repair_first_audio_PCM_exact=True,numeric_models_QMC_reused_exact=True,
        all_failures_retained=True,known_branch_helpers_AST_exact=True,stereo_gap=gap,
        marginal_amplitude_fourth_relative_error_range=load(evidence/'inspection_notes.json')['marginal_amplitude_fourth_relative_error_range'],
        scientific_figures_viewed=2,desktop_mobile_screenshots_viewed=True,browser=browser,
        hearing=load(repo/'research/radial_copula_v1_listening.json'),new_phase_branch_adopted=False,
        runtime_C_model_default_driver_owned_take_room_changed=False,unchanged_68CTest_not_repeated=True,
        E_feedback='左右关系有改善，音色仍明显电子',old_F2_F3_hearings='independently pending, no repeat',
        downloaded=False,pushed=False,physical_7_1_4=False,full_goal='active',
        next='Test shared phase plus explicit interchannel relative phase coordinates and amplitude association; validate actual complex coherence then time structure. Keep new fixed-phase amplitude hearing independent, no blind phase strength/rank/rho sweeps or default/C promotion.')
    sources=[n for n in names if Path(n).suffix in ('.c','.h','.cmake','.in') or n.endswith('CMakeLists.txt')]
    sources+=list(protected['voice_files_sha256.json'])+list(protected['F2_files_sha256.json'])+list(real['sources'])
    sources+=[n for n in names if n.startswith('tools/radial_copula_v1/')]
    sources+=['tools/audit_radial_copula_v1.py','tools/review_radial_copula_v1.py','tools/check_radial_copula_v1.cjs',
        'tools/package_radial_copula_v1.py','tools/research_archive_v1.py','research/幅相分离统计声源V1.md',
        'research/radial_copula_v1_listening.json','AGENTS.md','README.md',
        'handoff/C文件索引.csv','handoff/开发留痕.md','handoff/研究续接.md','handoff/当前代码阅读入口.md']
    inputs=dict(data_AGENTS=a.workspace/'AGENTS.md',parent_manifest=previous/'manifest.json',parent_validation=previous/'validation.json',
                frozen_C_build_source_zip=a.workspace/'baselines/F3_local_atlas_v1/source.zip')
    shutil.copy2(__file__,evidence/'executed_package.py')
    result=freeze(root,repo,sources,evidence,inputs,validation);verify(root)
    save(repo/'research/radial_copula_v1_summary.json',dict(validation,**result))
    append_index(repo/'handoff/阶段索引.csv',[
        'radial_copula_v1','baselines/radial_copula_v1/manifest.json',result['file_count'],result['manifest_sha256'],
        '7known;6models18x4096QMC;12new8secOSC;6Cbaseline2ref;20oneplayer;directAR-quantile-OSC;2plots2screenshots',
        '670C-H82voice/F2/Cindex exact;CVerror-90.73percent NOT timbre;phaseLR18/24worse not adopted;new fixedphase hearing pending;all failures kept',
        'research/幅相分离统计声源V1.md | research/radial_copula_v1_summary.json','baselines/radial_copula_v1/validation.json'])
    print(result)


if __name__=='__main__':main()
