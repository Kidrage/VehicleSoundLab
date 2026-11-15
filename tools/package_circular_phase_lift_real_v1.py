"""Freeze all lift outcomes, raw parents, audits and protected runtime contracts."""
import argparse
import csv
from pathlib import Path
import shutil
import subprocess
from research_archive_v1 import load,save,sha,freeze,verify,append_index


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace',type=Path,required=True)
    parser.add_argument('--audit',default='real_audit1')
    parser.add_argument('--review',default='review1')
    args=parser.parse_args()
    repo=Path(__file__).resolve().parents[1]
    evidence=args.workspace/'references/analysis/circular_phase_lift_real_v1'
    root=args.workspace/'baselines/circular_phase_lift_real_v1'
    carrier=args.workspace/'baselines/carrier_transfer_v1'
    parent=args.workspace/'baselines/conditional_phase_time_v1'
    assert sha(carrier/'manifest.json')==load(repo/'research/carrier_transfer_v1_summary.json')['manifest_sha256']
    assert sha(parent/'manifest.json')==load(repo/'research/conditional_phase_time_v1_summary.json')['manifest_sha256']
    entries={row['path']:row['sha256'] for row in load(carrier/'manifest.json')['files']}
    protected={}
    for name,count in [('C_files_sha256.json',670),('voice_files_sha256.json',82),('F2_files_sha256.json',3)]:
        values=load(carrier/'evidence'/name)
        assert len(values)==count and all(sha(repo/path)==digest for path,digest in values.items())
        save(evidence/name,values)
        protected[name]=values
    names=set()
    for flags in (['ls-files','-z'],['ls-files','--others','--exclude-standard','-z']):
        names.update(subprocess.check_output(['git']+flags,cwd=repo).decode('utf-8').split('\0'))
    names.discard('')
    assert {name for name in names if Path(name).suffix in ('.c','.h')}==set(protected['C_files_sha256.json'])
    assert sha(repo/'handoff/C文件索引.csv')==entries['source/handoff/C文件索引.csv']
    rows=list(csv.reader((repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig',newline='')))
    assert len(rows)==671 and all(row[4]==protected['C_files_sha256.json'][row[0]] for row in rows[1:])
    hearings=load(carrier/'validation.json')['protected_hearings_sha256']
    assert all(sha(repo/path)==digest for path,digest in hearings.items())
    producer=load(evidence/'real1/report.json')
    assert producer['result']=='all90_frozen_phase_lift_candidates_ready'
    assert len(producer['cases'])==6 and sum(len(seed['variants']) for case in producer['cases'] for seed in case['seeds'])==90
    for name,digest in producer['sources'].items():
        assert sha(repo/name)==sha(evidence/'real1/exact_sources'/name)==digest
    for path,digest in producer['inputs'].items():
        assert sha(path)==digest
    audit=load(evidence/args.audit/'report.json')
    assert audit['result']=='independent_circular_phase_lift_real_passed'
    assert audit['producer_sha256']==sha(evidence/'real1/report.json')
    assert audit['auditor_sha256']==sha(repo/'tools/audit_circular_phase_lift_real_v1.py')==sha(evidence/args.audit/'executed_audit.py')
    assert audit['oracle_sha256']==sha(repo/'tools/circular_phase_lift_v1/audit_oracle.py')==sha(evidence/args.audit/'executed_audit_oracle.py')
    assert audit['waveforms']==90 and audit['matrices']==173520 and audit['no_crossing_grouped_waves_bit_exact']==36
    review=evidence/args.review
    published=load(review/'report.json')
    assert published['result']=='circular_phase_lift_review_ready'
    assert published['producer_sha256']==sha(evidence/'real1/report.json') and published['audit_sha256']==sha(evidence/args.audit/'report.json')
    for name,digest in published['sources'].items():
        assert sha(repo/name)==sha(review/'exact_sources'/name)==digest
    for name,digest in published['images'].items():
        assert sha(review/name)==digest
    assert sha(review/'summary.json')==published['summary_sha256']
    assert sha(review/'figure_inputs.json')==published['figure_inputs_sha256']
    visual=load(review/'visual_review.json')
    assert visual['accepted_for_publication'] and visual['scientific_figures_individually_viewed']==2
    assert visual['images_sha256']==published['images']
    metrics=load(review/'metrics_verification.json')
    assert metrics['all90_rows_and_aggregates_verified'] and metrics['literal_and_numerical_equivalence_counts_verified']
    assert metrics['auditor_sha256']==sha(repo/'tools/audit_circular_phase_lift_review_v1.py')
    assert metrics['summary_sha256']==sha(review/'summary.json') and metrics['figure_inputs_sha256']==sha(review/'figure_inputs.json')
    decision=load(review/'decision.json')
    assert not decision['native_or_runtime_promoted'] and decision['all90_outcomes_retained']
    assert not list(evidence.rglob('*.wav'))
    validation=dict(result='circular_phase_lift_real_frozen',parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
        previous_goal_turn='Progress:carrier attribution and8half-angleknown controls independently audited/archived/committed a0bb4f7.',
        source_models=6,seeds=3,alternatives=5,paired_raw_lift_outcomes=90,frames=65536,
        normalized_coordinate_only=True,known_controls=8,known_controls_frozen_in_parent=True,
        real_audit=audit,results=load(review/'summary.json'),decision=decision,
        scientific_figures_individually_viewed=2,all90_rows_and_aggregates_verified=True,
        signed_group_and_complex_LR_terms_preserved=True,C_H_exact=670,voice_parameters_exact=82,F2_files_exact=3,C_index_exact=True,
        protected_hearings_sha256=hearings,new_C_H=0,runtime_default_driver_owned_take_room_changed=False,
        native48k_aliasing_qualified=False,new_listening_question=False,old_68CTest_not_repeated=True,
        downloaded=False,pushed=False,physical_7_1_4=False,full_goal='active',next=decision['next'])
    sources=[name for name in names if Path(name).suffix in ('.c','.h','.cmake','.in') or name.endswith('CMakeLists.txt')]
    sources+=list(protected['voice_files_sha256.json'])+list(protected['F2_files_sha256.json'])+list(hearings)
    sources+=[name for name in names if 'circular_phase_lift' in name and Path(name).suffix in ('.py','.md','.json')]
    sources+=list(producer['sources'])+['tools/research_archive_v1.py','tools/verify_research_archive_independent_v1.py',
        'tools/sound_dna/statistics.py','research/冻结声纹连续相位对照V1.md','research/相位半角与连续提升控制V1.md',
        'AGENTS.md','README.md','handoff/C文件索引.csv','handoff/开发留痕.md','handoff/研究续接.md','handoff/当前代码阅读入口.md']
    inputs=dict(data_AGENTS=args.workspace/'AGENTS.md',carrier_manifest=carrier/'manifest.json',carrier_validation=carrier/'validation.json',
        time_parent_manifest=parent/'manifest.json',time_parent_validation=parent/'validation.json',
        frozen_C_build_source_zip=args.workspace/'baselines/F3_local_atlas_v1/source.zip')
    for path in producer['inputs']:
        path=Path(path)
        if path.is_relative_to(parent):inputs['time_inputs/'+path.relative_to(parent).as_posix()]=path
    known=carrier/'evidence/followup_known/circular_phase_lift_v1'
    for path in known.rglob('*'):
        if path.is_file():inputs['known_controls/'+path.relative_to(known).as_posix()]=path
    original=load(carrier/'evidence/real1/report.json')
    inputs['carrier_raw/report.json']=carrier/'evidence/real1/report.json'
    for case in original['cases']:
        for seed in case['seeds']:
            for desc in seed['variants'].values():
                relative=Path('evidence/real1')/case['label']/desc['file']
                path=carrier/relative
                assert sha(path)==desc['sha256']==entries[relative.as_posix()]
                inputs['carrier_raw/'+case['label']+'/'+desc['file']]=path
    shutil.copy2(__file__,evidence/'executed_package.py')
    result=freeze(root,repo,sources,evidence,inputs,validation)
    verify(root)
    save(repo/'research/circular_phase_lift_real_v1_summary.json',dict(validation,**result))
    append_index(repo/'handoff/阶段索引.csv',['circular_phase_lift_real_v1','baselines/circular_phase_lift_real_v1/manifest.json',
        result['file_count'],result['manifest_sha256'],'8parentknown;90pairedwave;173520complexGram;fullOSC/unwrap/STFT;2figures',
        '670C-H82voice3F2/index exact;normalized temporal hypothesis only;no runtime promotion',
        'research/冻结声纹连续相位对照V1.md | research/circular_phase_lift_real_v1_summary.json','baselines/circular_phase_lift_real_v1/validation.json'])
    print(dict(result='circular_phase_lift_real_frozen',**result))


if __name__=='__main__':
    main()
