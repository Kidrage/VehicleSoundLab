"""Freeze all coefficient-geometry attempts and unchanged runtime/parameter contracts."""
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
    evidence=a.workspace/'references/analysis/coefficient_geometry_v1'
    root=a.workspace/'baselines/coefficient_geometry_v1'
    if a.verify:
        m=verify(root);print(dict(result='archive_verified',files=m['file_count'],bytes=m['bytes']));return
    previous=a.workspace/'baselines/joint_motion_controls_v1'
    assert sha(previous/'manifest.json')==load(repo/'research/joint_motion_controls_v1_summary.json')['manifest_sha256']
    protected={}
    for name,count in [('C_files_sha256.json',670),('voice_files_sha256.json',82),('F2_files_sha256.json',3)]:
        rows=load(previous/'evidence'/name)
        assert len(rows)==count
        for n,h in rows.items():assert sha(repo/n)==h,n
        save(evidence/name,rows);protected[name]=rows
    names=set()
    for flags in [['ls-files','-z'],['ls-files','--others','--exclude-standard','-z']]:
        names.update(subprocess.check_output(['git']+flags,cwd=repo).decode('utf-8').split('\0'))
    names.discard('')
    assert {n for n in names if Path(n).suffix in ('.c','.h')}==set(protected['C_files_sha256.json'])
    index=list(csv.reader((repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig',newline='')))
    assert len(index)==671 and all(row[4]==protected['C_files_sha256.json'][row[0]] for row in index[1:])
    parent_entries={row['path']:row['sha256'] for row in load(previous/'manifest.json')['files']}
    assert sha(repo/'handoff/C文件索引.csv')==parent_entries['source/handoff/C文件索引.csv']
    reports={name:load(evidence/name/'report.json') for name in
             ['known1','known_audit1','known_audit2','known_audit3','real1','real_audit1','real_audit2','review1']}
    known,real=reports['known1'],reports['real1']
    assert known['result']=='known_AM_PM_geometry_observed' and len(known['cases'])==4
    assert real['result']=='six_F3_coefficient_geometries_observed' and len(real['cases'])==6
    for folder,report in [('known1',known),('real1',real)]:
        for n,h in report['sources'].items():assert sha(repo/n)==sha(evidence/folder/'exact_sources'/n)==h
        for n,h in report['inputs'].items():assert sha(n)==h
        for command in report['commands']:
            assert command['exit_code']==0 and sha(evidence/folder/command['log'])==command['sha256']
    assert known['C_known_576000frame_WAV_exact']
    assert sha(evidence/'known1/local_atlas_export.exe')==known['binary_sha256']=='90ce22a9169689121f3d2c41b49ae8994dfcb6f1f043f85c395efa4912990d6f'
    for row in known['cases']:
        folder=evidence/'known1'/row['label']
        assert sha(folder/'moments.npz')==row['arrays_sha256']
        assert sha(folder/'voice.model')==row['model_sha256'] and len(row['renders'])==3
        for render in row['renders']:
            for suffix,h in render['C_files_sha256'].items():assert sha((folder/f'C_seed{render["seed"]}').with_suffix(suffix))==h
            assert sha(folder/f'wave_seed{render["seed"]}.npz')==render['wave_arrays_sha256']
        if row['label']=='PM_only':
            assert row['block37_512_WAV_exact'] and sha(folder/'C_block37.wav')==row['renders'][0]['C_files_sha256']['.wav']
    for row in real['cases']:
        folder=evidence/'real1'/row['label']
        assert row['source_DOUBLE_rebuild_FLOAT_exact'] and len(row['variants'])==3
        assert sha(folder/'source.npz')==row['source_arrays_sha256']
        for variant in row['variants']:assert sha(folder/variant['label']/'moments.npz')==variant['arrays_sha256']
    for name in ['known_audit2','known_audit3','real_audit1','real_audit2']:
        report=reports[name];study='known1' if name.startswith('known') else 'real1'
        assert report['result']=='independent_coefficient_geometry_audit_passed'
        assert report['producer_report_sha256']==sha(evidence/study/'report.json')
        assert report['auditor_sha256']==sha(evidence/name/'executed_audit.py')
    for name in ['known_audit3','real_audit2']:
        assert sha(repo/'tools/audit_coefficient_geometry_v1.py')==reports[name]['auditor_sha256']
        assert reports[name]['max_mean_normalized_moment_error']<=2e-9
    failed=reports['known_audit1']
    assert failed['result']=='failed' and 'AssertionError' in failed['error']
    assert (evidence/'known_audit1/executed_audit.py').is_file()
    assert reports['known_audit3']['C_renders']==12 and reports['real_audit2']['direct_DFT_complex_values']==138240
    review=reports['review1']
    assert review['result']=='coefficient_geometry_observations_published'
    for key,name in [('known','known1'),('real','real1'),('known_audit','known_audit3'),('real_audit','real_audit2')]:
        assert review[key+'_report_sha256']==sha(evidence/name/'report.json')
    assert review['reviewer_sha256']==sha(repo/'tools/review_coefficient_geometry_v1.py')==sha(evidence/'review1/executed_review.py')
    assert sha(evidence/'review1/observations.json')==review['observations_sha256']
    for n,h in review['images'].items():assert sha(evidence/'review1'/n)==h
    visual=load(evidence/'review1/visual_review.json')
    assert visual['two_scientific_figures_individually_viewed'] and visual['accepted_for_final_publication']
    assert visual['images_sha256']==review['images']
    observed=review['observations']
    assert observed['coordinates']==observed['F3_Gaussian_CV_larger_than_observed_coordinates']==48
    validation=dict(result='coefficient_geometry_mechanism_and_source_moments_verified',
        parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
        previous_goal_turn='No synthesis progress: MCPS estimate revalidated. This stage establishes a controlled representation mechanism and six-source mismatch, changing the next synthesis action.',
        C_H_exact=670,voice_parameters_exact=82,F2_exact=True,C_index_exact=True,new_C_H=0,
        known_controls=4,known_C_renders=12,known_seeds=3,known_576000frame_WAV_exact=True,known_PM_37_512_WAV_exact=True,
        real_anchors=6,real_counterfactual_variants=18,real_coefficient_rows=240,real_DFT_complex_values=138240,
        source_DOUBLE_rebuild_FLOAT_exact=True,known_audit=reports['known_audit3'],real_audit=reports['real_audit2'],
        observations=observed,known_near_empty_FFT_log_audit_failure_retained=True,
        weak_band_mean_normalized_gate_added=True,all_attempts_retained=True,scientific_figures_viewed=2,
        source_counterfactual_is_physical_component=False,coefficient_power_is_native_waveform_power=False,
        electronic_timbre_cause_proven=False,heard=False,new_audio_candidate=False,
        runtime_DSP_model_default_driver_owned_take_room_changed=False,unchanged_68CTest_not_repeated=True,
        F2_F3_hearings='independently pending; no repeat or blind strengths',E_feedback='左右关系有改善，音色仍明显电子',
        downloaded=False,pushed=False,physical_7_1_4=False,full_goal='active',
        next='Separately qualify positive amplitude and phase representation: known AM/PM no cross-talk, then six-source mean/fourth/stereo/time evidence before offline audio/C adoption. Do not revive rejected A magnitude models, simply delete shared factors or add independent HF noise.')
    sources=[n for n in names if Path(n).suffix in ('.c','.h','.cmake','.in') or n.endswith('CMakeLists.txt')]
    sources+=list(protected['voice_files_sha256.json'])+list(protected['F2_files_sha256.json'])+list(known['sources'])
    sources+=['tools/audit_coefficient_geometry_v1.py','tools/review_coefficient_geometry_v1.py','tools/package_coefficient_geometry_v1.py',
        'tools/coefficient_geometry_v1/README.md','tools/local_atlas_v1/oracle.py','tools/sustain_osc_v1/oracle.py',
        'tools/local_voice_batch_v1/audit_kernels.py','tools/research_archive_v1.py',
        'research/复数统计与幅度串扰诊断V1.md','README.md','AGENTS.md',
        'handoff/C文件索引.csv','handoff/研究续接.md','handoff/开发留痕.md','handoff/当前代码阅读入口.md']
    old=a.workspace/'baselines/F3_local_atlas_v1'
    inputs=dict(data_AGENTS=a.workspace/'AGENTS.md',parent_manifest=previous/'manifest.json',parent_validation=previous/'validation.json',
                frozen_C_build_source_zip=old/'source.zip',frozen_C_parent_manifest=old/'manifest.json',
                native_measurement_plan=a.workspace/'baselines/F3_joint_envelopes_v1/source/research/F3_joint_envelopes_v1_plan.json')
    shutil.copy2(__file__,evidence/'executed_package.py')
    result=freeze(root,repo,sources,evidence,inputs,validation)
    verify(root)
    save(repo/'research/coefficient_geometry_v1_summary.json',dict(validation,**result))
    append_index(repo/'handoff/阶段索引.csv',[
        'coefficient_geometry_v1','baselines/coefficient_geometry_v1/manifest.json',result['file_count'],result['manifest_sha256'],
        '4AM-PM12originalC;6frozenF3x3variants;240rows138240DFT;polynomialWick;2viewedfigures',
        '670C-H82voices/F2/Cindex exact;constantmagPM becomesAM;48/48GaussianCV1.40..4.46x;no timbre/default promotion;all audit attempts kept',
        'research/复数统计与幅度串扰诊断V1.md | research/coefficient_geometry_v1_summary.json','baselines/coefficient_geometry_v1/validation.json'])
    print(result)


if __name__=='__main__':
    main()
