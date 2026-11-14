"""Freeze common/relative phase evidence, all attempts and unchanged runtime."""
import argparse
import csv
from pathlib import Path
import shutil
import subprocess
from research_archive_v1 import load,save,sha,freeze,verify,append_index


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace',type=Path,required=True);p.add_argument('--verify',action='store_true')
    a=p.parse_args();repo=Path(__file__).resolve().parents[1]
    evidence=a.workspace/'references/analysis/relative_phase_v1';root=a.workspace/'baselines/relative_phase_v1'
    if a.verify:
        m=verify(root);print(dict(result='archive_verified',files=m['file_count'],bytes=m['bytes']));return
    parent=a.workspace/'baselines/radial_copula_v1'
    assert sha(parent/'manifest.json')==load(repo/'research/radial_copula_v1_summary.json')['manifest_sha256']
    protected={}
    for name,count in [('C_files_sha256.json',670),('voice_files_sha256.json',82),('F2_files_sha256.json',3)]:
        values=load(parent/'evidence'/name);assert len(values)==count
        assert all(sha(repo/n)==h for n,h in values.items());save(evidence/name,values);protected[name]=values
    names=set()
    for args in [['ls-files','-z'],['ls-files','--others','--exclude-standard','-z']]:
        names.update(subprocess.check_output(['git']+args,cwd=repo).decode('utf-8').split('\0'))
    names.discard('')
    assert {n for n in names if Path(n).suffix in ('.c','.h')}==set(protected['C_files_sha256.json'])
    index=list(csv.reader((repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig',newline='')))
    assert len(index)==671 and all(row[4]==protected['C_files_sha256.json'][row[0]] for row in index[1:])
    entries={r['path']:r['sha256'] for r in load(parent/'manifest.json')['files']}
    assert sha(repo/'handoff/C文件索引.csv')==entries['source/handoff/C文件索引.csv']
    stage_names=['known1','known_audit1','known_audit2','real1','real_audit1','real_audit2',
                 'audio1','audio_audit1','review1','review_audit1','browser1']
    r={n:load(evidence/n/'report.json') for n in stage_names}
    assert r['known1']['result']=='relative_phase_known_controls_passed' and len(r['known1']['cases'])==9
    assert r['known_audit1']['result']=='failed' and len(r['known_audit1']['cases'])==8
    assert r['real1']['result']=='six_source_relative_phase_evidence_ready' and len(r['real1']['cases'])==6
    for n in ('known1','real1','audio1','review1'):
        for name,h in r[n]['sources'].items():assert sha(repo/name)==sha(evidence/n/'exact_sources'/name)==h
        for name,h in r[n]['inputs'].items():assert sha(name)==h
    for n,owner in [('known_audit2','known1'),('real_audit1','real1'),('real_audit2','real1')]:
        assert r[n]['result']=='independent_relative_phase_audit_passed'
        assert r[n]['producer_sha256']==sha(evidence/owner/'report.json')
        assert r[n]['auditor_sha256']==sha(evidence/n/'executed_audit.py')
    assert r['real_audit2']['all_JSON_descriptors_and_aggregate_decision_recomputed']
    assert r['real_audit2']['auditor_sha256']==sha(repo/'tools/audit_relative_phase_v1.py')
    for n in ('known1','real1'):
        for row in r[n]['cases']:
            folder=evidence/n/row['label']
            for filename,key in [('profile.npz','profile_sha256'),('training.npz','training_sha256')]:assert sha(folder/filename)==row[key]
            for q in row.get('QMC',[]):assert sha(folder/f'QMC_{q["seed"]}.npz')==q['sha256']
    assert r['audio1']['result']=='relative_phase_paired_audio_ready'
    assert r['audio_audit1']['result']=='independent_relative_phase_audio_audit_passed' and r['audio_audit1']['new_waves']==12
    assert r['audio_audit1']['producer_sha256']==sha(evidence/'audio1/report.json')
    assert r['audio_audit1']['auditor_sha256']==sha(repo/'tools/audit_relative_phase_audio_v1.py')==sha(evidence/'audio_audit1/executed_audit.py')
    for row in r['audio1']['cases']:
        folder=evidence/'audio1'/row['label'];assert sha(folder/'profile.npz')==row['profile_sha256']
        for audio in row['audio']+row.get('block37_copies',[]):assert sha(folder/audio['file'])==audio['sha256']
        for t in row['temporal']:assert sha(folder/f'temporal_{t["seed"]}.npz')==t['sha256']
    assert r['audio1']['cases'][0]['block37_1024_both_variants_PCM_exact']
    assert r['review1']['result']=='relative_phase_one_player_review_ready' and len(r['review1']['clips'])==20
    for row in r['review1']['clips']:assert sha(evidence/'review1'/row['file'])==row['sha256'] and row['peak_FS']<.95
    for n,h in r['review1']['images'].items():assert sha(evidence/'review1'/n)==h
    assert r['review_audit1']['result']=='relative_phase_review_wave_metrics_verified' and r['review_audit1']['wave_checks']==20
    assert r['review_audit1']['producer_sha256']==sha(evidence/'review1/report.json')
    assert r['review_audit1']['auditor_sha256']==sha(repo/'tools/audit_relative_phase_review_v1.py')==sha(evidence/'review_audit1/executed_audit.py')
    assert r['browser1']['result']=='pass' and r['browser1']['metadata_checks']==20
    assert sha(evidence/'browser1/executed_check.cjs')==sha(repo/'tools/check_radial_copula_v1.cjs')
    visual=load(evidence/'review1/visual_review.json')
    assert visual['two_scientific_figures_individually_viewed'] and visual['desktop_mobile_individually_viewed']
    assert visual['images_sha256']==r['review1']['images'] and visual['browser_report_sha256']==sha(evidence/'browser1/report.json')
    validation=dict(result='relative_phase_coordinates_audio_and_evidence_frozen',
        parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
        previous_goal_turn='No synthesis progress: ADI estimate recheck. This turn fixes the identified stereo phase representation and generates paired audible candidates.',
        C_H_exact=670,voice_parameters_exact=82,F2_files_exact=3,C_index_exact=True,new_C_H=0,
        known_controls=9,known_audit=r['known_audit2'],source_models=6,QMC_cases=18,QMC_draws=4096,
        real_audit=r['real_audit2'],stereo_comparison=r['real1']['stereo_comparison'],CV_error_L2=r['real1']['CV_error_L2'],
        new_paired_waves=12,same_amplitudes_in_each_pair=True,block37_1024_both_variants_PCM_exact=True,
        audio_audit=r['audio_audit1'],actual_wave_audit=r['review_audit1'],browser=r['browser1'],
        scientific_figures_individually_viewed=2,desktop_mobile_individually_viewed=True,
        all_failures_and_exact_executed_sources_preserved=True,
        hearing=load(repo/'research/relative_phase_v1_listening.json'),
        parent_amplitude_and_old_F2_F3_hearings='independently pending; not repeated',
        E_feedback='左右关系有改善，音色仍明显电子',
        runtime_default_driver_owned_take_room_changed=False,old_68CTest_not_repeated=True,
        ADI_target_or_CPU_bound_verified=False,new_spatial_timbre_accepted=False,
        downloaded=False,pushed=False,physical_7_1_4=False,full_goal='active',
        next='Listen for wobble/blur; inspect relative-phase moments and amplitude-product association at five fixed-phase regressions, then time/window law. No strength/rank/rho sweep or unqualified lowrate replacement. Future C port through the original single driver requires numeric/CPU/hearing validation.')
    sources=[n for n in names if Path(n).suffix in ('.c','.h','.cmake','.in') or n.endswith('CMakeLists.txt')]
    sources+=list(protected['voice_files_sha256.json'])+list(protected['F2_files_sha256.json'])
    sources+=[n for n in names if 'relative_phase' in n and n.startswith(('tools/','research/'))]
    sources+=[n for n in r['known1']['sources'] if n!='research/relative_phase_v1_plan.json']
    sources+=['tools/check_radial_copula_v1.cjs','tools/research_archive_v1.py',
        'research/左右相对相位声源V1.md','AGENTS.md','README.md','handoff/C文件索引.csv',
        'handoff/开发留痕.md','handoff/研究续接.md','handoff/当前代码阅读入口.md']
    shutil.copy2(__file__,evidence/'executed_package.py')
    result=freeze(root,repo,sources,evidence,dict(data_AGENTS=a.workspace/'AGENTS.md',
        parent_manifest=parent/'manifest.json',parent_validation=parent/'validation.json',
        frozen_C_build_source_zip=a.workspace/'baselines/F3_local_atlas_v1/source.zip'),validation)
    verify(root);save(repo/'research/relative_phase_v1_summary.json',dict(validation,**result))
    append_index(repo/'handoff/阶段索引.csv',[
        'relative_phase_v1','baselines/relative_phase_v1/manifest.json',result['file_count'],result['manifest_sha256'],
        '9known;6models18QMC;12paired8sOSC;both37-1024exact;20oneplayer;independentAR-inverseCDF-OSC-WAVFFT;2fig2screenshots',
        '670C-H82voice3F2/Cindex exact;stereo24/24vsoldphase19/24vsfixed;time incomplete;hearingpending;allfailureskept',
        'research/左右相对相位声源V1.md | research/relative_phase_v1_summary.json','baselines/relative_phase_v1/validation.json'])
    print(result)


if __name__=='__main__':main()
