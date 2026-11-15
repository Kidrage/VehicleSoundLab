"""Freeze all18 controls, all90 raw comparators and unchanged runtime contracts."""
import argparse
import csv
from pathlib import Path
import shutil
import subprocess
from research_archive_v1 import load,save,sha,freeze,verify,append_index


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace',type=Path,required=True)
    a=p.parse_args();repo=Path(__file__).resolve().parents[1]
    evidence=a.workspace/'references/analysis/phase_stream_control_v1'
    root=a.workspace/'baselines/phase_stream_control_v1'
    carrier=a.workspace/'baselines/carrier_transfer_v1';parent=a.workspace/'baselines/conditional_phase_time_v1'
    assert sha(carrier/'manifest.json')==load(repo/'research/carrier_transfer_v1_summary.json')['manifest_sha256']
    assert sha(parent/'manifest.json')==load(repo/'research/conditional_phase_time_v1_summary.json')['manifest_sha256']
    entries={r['path']:r['sha256'] for r in load(carrier/'manifest.json')['files']}
    protected={}
    for name,count in (('C_files_sha256.json',670),('voice_files_sha256.json',82),('F2_files_sha256.json',3)):
        values=load(carrier/'evidence'/name);assert len(values)==count
        assert all(sha(repo/path)==digest for path,digest in values.items())
        save(evidence/name,values);protected[name]=values
    names=set()
    for flags in (['ls-files','-z'],['ls-files','--others','--exclude-standard','-z']):names.update(subprocess.check_output(['git']+flags,cwd=repo).decode('utf-8').split('\0'))
    names.discard('')
    assert {n for n in names if Path(n).suffix in ('.c','.h')}==set(protected['C_files_sha256.json'])
    assert sha(repo/'handoff/C文件索引.csv')==entries['source/handoff/C文件索引.csv']
    rows=list(csv.reader((repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig',newline='')))
    assert len(rows)==671 and all(row[4]==protected['C_files_sha256.json'][row[0]] for row in rows[1:])
    hearings=load(carrier/'validation.json')['protected_hearings_sha256'];assert all(sha(repo/path)==digest for path,digest in hearings.items())
    known=load(evidence/'known1/report.json');ka=load(evidence/'known_audit1/report.json')
    assert known['result']=='phase_stream_known_ready' and ka['result']=='independent_phase_stream_known_passed'
    assert ka['producer_sha256']==sha(evidence/'known1/report.json') and ka['auditor_sha256']==sha(repo/'tools/audit_phase_stream_known_v1.py')==sha(evidence/'known_audit1/executed_audit.py')
    producer=load(evidence/'real1/report.json');audit=load(evidence/'real_audit1/report.json')
    assert producer['result']=='phase_stream_all18_ready' and audit['result']=='independent_phase_stream_real_passed'
    assert audit['producer_sha256']==sha(evidence/'real1/report.json')
    assert audit['auditor_sha256']==sha(repo/'tools/audit_phase_stream_real_v1.py')==sha(evidence/'real_audit1/executed_audit.py')
    assert audit['oracle_sha256']==sha(repo/'tools/circular_phase_lift_v1/audit_oracle.py')==sha(evidence/'real_audit1/executed_oracle.py')
    for desc,folder in ((known,evidence/'known1'),(producer,evidence/'real1')):
        for name,digest in desc['sources'].items():assert sha(repo/name)==sha(folder/'exact_sources'/name)==digest
    for path,digest in producer['inputs'].items():assert sha(path)==digest
    assert (audit['waveforms'],audit['matrices'],audit['observer_rows'])==(18,34704,4338)
    review=evidence/'review1';published=load(review/'report.json');metrics=load(review/'metrics_verification.json')
    assert published['result']=='phase_stream_review_ready' and metrics['all108_rows_and_aggregates_verified']
    assert published['producer_sha256']==sha(evidence/'real1/report.json') and published['audit_sha256']==sha(evidence/'real_audit1/report.json')
    for name,digest in published['sources'].items():assert sha(repo/name)==sha(review/'exact_sources'/name)==digest
    for name,digest in published['images'].items():assert sha(review/name)==digest
    assert metrics['auditor_sha256']==sha(repo/'tools/audit_phase_stream_review_v1.py')==sha(review/'executed_metrics_audit.py')
    for key in ('summary','figure_inputs'):assert sha(review/(key+'.json'))==published[key+'_sha256']==metrics[key+'_sha256']
    visual=load(review/'visual_review.json');assert visual['accepted_for_publication'] and visual['scientific_figures_individually_viewed']==2
    assert visual['images_sha256']==published['images']
    decision=load(review/'decision.json');assert not decision['native_or_runtime_promoted'] and decision['all108_outcomes_retained']
    assert not list(evidence.rglob('*.wav'))
    validation=dict(result='phase_stream_control_frozen',parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
        previous_goal_turn='Progress:ADI V8 cost planning only; no synthesis. This stage resumes declared stream-vs-mapping isolation.',
        known_controls=8,known_audit=ka,new_waveforms=18,original_comparator_waveforms=90,source_models=6,seeds=3,frames=65536,
        real_audit=audit,results=load(review/'summary.json'),decision=decision,normalized_coordinate_only=True,
        scientific_figures_individually_viewed=2,all108_rows_and_aggregates_verified=True,full_complex_signed_Gram_preserved=True,
        C_H_exact=670,voice_parameters_exact=82,F2_files_exact=3,C_index_exact=True,protected_hearings_sha256=hearings,
        runtime_default_driver_owned_take_room_changed=False,new_C_H=0,native48k_aliasing_qualified=False,
        new_listening_question=False,old_68CTest_not_repeated=True,downloaded=False,pushed=False,physical_7_1_4=False,full_goal='active',next=decision['next'])
    sources=[n for n in names if Path(n).suffix in ('.c','.h','.cmake','.in') or n.endswith('CMakeLists.txt')]
    sources+=list(protected['voice_files_sha256.json'])+list(protected['F2_files_sha256.json'])+list(hearings)
    sources+=[n for n in names if ('phase_stream' in n and Path(n).suffix in ('.py','.json','.md'))]
    sources+=list(known['sources'])+list(producer['sources'])+list(published['sources'])
    sources+=['tools/research_archive_v1.py','tools/verify_research_archive_independent_v1.py','tools/circular_phase_lift_v1/audit_oracle.py',
        'tools/sound_dna/statistics.py','research/独立相位流原边际对照V1.md','AGENTS.md','README.md',
        'handoff/C文件索引.csv','handoff/开发留痕.md','handoff/研究续接.md','handoff/当前代码阅读入口.md']
    inputs=dict(data_AGENTS=a.workspace/'AGENTS.md',carrier_manifest=carrier/'manifest.json',carrier_validation=carrier/'validation.json',
        time_parent_manifest=parent/'manifest.json',time_parent_validation=parent/'validation.json',
        frozen_C_build_source_zip=a.workspace/'baselines/F3_local_atlas_v1/source.zip')
    for path in producer['inputs']:
        path=Path(path);inputs['time_inputs/'+path.relative_to(parent).as_posix()]=path
    raw=load(carrier/'evidence/real1/report.json');inputs['carrier_raw/report.json']=carrier/'evidence/real1/report.json'
    count=0
    for row in raw['cases']:
        for seed in row['seeds']:
            for desc in seed['variants'].values():
                relative=Path('evidence/real1')/row['label']/desc['file'];path=carrier/relative
                assert sha(path)==desc['sha256']==entries[relative.as_posix()]
                inputs['carrier_raw/'+row['label']+'/'+desc['file']]=path;count+=1
    assert count==90
    shutil.copy2(__file__,evidence/'executed_package.py')
    result=freeze(root,repo,sources,evidence,inputs,validation);verify(root)
    save(repo/'research/phase_stream_control_v1_summary.json',dict(validation,**result))
    append_index(repo/'handoff/阶段索引.csv',['phase_stream_control_v1','baselines/phase_stream_control_v1/manifest.json',
        result['file_count'],result['manifest_sha256'],'8known;18fullnew+90rawcomparators;34704newcomplexGram;108publishedrows;2figures',
        '670C-H82voice3F2/index exact;finite stream/mapping isolation;no native/runtime adoption',
        'research/独立相位流原边际对照V1.md | research/phase_stream_control_v1_summary.json','baselines/phase_stream_control_v1/validation.json'])
    print(dict(result='phase_stream_control_frozen',**result),flush=True)


if __name__=='__main__':main()
