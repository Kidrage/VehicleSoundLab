"""Freeze every input-path outcome, failed attempts and unchanged C contracts."""
import argparse
import csv
from pathlib import Path
import shutil
import subprocess
from research_archive_v1 import load,save,sha,freeze,verify,append_index


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace',type=Path,required=True)
    p.add_argument('--audit',default='real_audit3')
    p.add_argument('--review',default='review1')
    a=p.parse_args();repo=Path(__file__).resolve().parents[1]
    evidence=a.workspace/'references/analysis/phase_input_paths_v1';root=a.workspace/'baselines/phase_input_paths_v1'
    carrier=a.workspace/'baselines/carrier_transfer_v1';parent=a.workspace/'baselines/conditional_phase_time_v1'
    stream=a.workspace/'baselines/phase_stream_control_v1'
    for folder,summary in ((carrier,'carrier_transfer_v1'),(parent,'conditional_phase_time_v1'),(stream,'phase_stream_control_v1')):
        assert sha(folder/'manifest.json')==load(repo/f'research/{summary}_summary.json')['manifest_sha256']
    entries={r['path']:r['sha256'] for r in load(carrier/'manifest.json')['files']};protected={}
    for name,count in (('C_files_sha256.json',670),('voice_files_sha256.json',82),('F2_files_sha256.json',3)):
        values=load(carrier/'evidence'/name);assert len(values)==count and all(sha(repo/path)==digest for path,digest in values.items())
        save(evidence/name,values);protected[name]=values
    names=set()
    for flags in (['ls-files','-z'],['ls-files','--others','--exclude-standard','-z']):names.update(subprocess.check_output(['git']+flags,cwd=repo).decode('utf-8').split('\0'))
    names.discard('');assert {n for n in names if Path(n).suffix in ('.c','.h')}==set(protected['C_files_sha256.json'])
    assert sha(repo/'handoff/C文件索引.csv')==entries['source/handoff/C文件索引.csv']
    rows=list(csv.reader((repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig',newline='')))
    assert len(rows)==671 and all(row[4]==protected['C_files_sha256.json'][row[0]] for row in rows[1:])
    hearings=load(carrier/'validation.json')['protected_hearings_sha256'];assert all(sha(repo/path)==digest for path,digest in hearings.items())
    known=load(evidence/'known2/report.json');ka=load(evidence/'known_audit2/report.json')
    assert known['result']=='phase_input_known_ready' and ka['result']=='independent_phase_input_known_passed' and ka['cases']==9
    assert ka['producer_sha256']==sha(evidence/'known2/report.json') and ka['auditor_sha256']==sha(repo/'tools/audit_phase_input_known_v1.py')==sha(evidence/'known_audit2/executed_audit.py')
    assert ka['oracle_sha256']==sha(repo/'tools/phase_input_paths_v1/audit_oracle.py')==sha(evidence/'known_audit2/executed_oracle.py')
    producer=load(evidence/'real1/report.json');audit=load(evidence/a.audit/'report.json')
    assert producer['result']=='phase_input_all54_sets_ready' and audit['result']=='independent_phase_input_real_passed'
    assert audit['producer_sha256']==sha(evidence/'real1/report.json') and audit['auditor_sha256']==sha(repo/'tools/audit_phase_input_real_v1.py')==sha(evidence/a.audit/'executed_audit.py')
    for i,(name,digest) in enumerate(audit['oracles_sha256'].items()):assert digest==sha(repo/name)==sha(evidence/a.audit/f'executed_oracle_{i}.py')
    for desc,folder in ((known,evidence/'known2'),(producer,evidence/'real1')):
        for name,digest in desc['sources'].items():assert sha(repo/name)==sha(folder/'exact_sources'/name)==digest
    for path,digest in producer['inputs'].items():assert sha(path)==digest
    assert (audit['sets'],audit['counterfactuals'],audit['observer_rows'],audit['term_matrices'])==(54,216,52056,104112)
    review=evidence/a.review;published=load(review/'report.json');metrics=load(review/'metrics_verification.json')
    assert published['result']=='phase_input_review_ready' and metrics['all216_rows54_budgets_and_aggregates_verified']
    assert published['producer_sha256']==sha(evidence/'real1/report.json') and published['audit_sha256']==sha(evidence/a.audit/'report.json')
    for name,digest in published['sources'].items():assert sha(repo/name)==sha(review/'exact_sources'/name)==digest
    for name,digest in published['images'].items():assert sha(review/name)==digest
    assert metrics['auditor_sha256']==sha(repo/'tools/audit_phase_input_review_v1.py')==sha(review/'executed_metrics_audit.py')
    for key in ('summary','figure_inputs'):assert sha(review/(key+'.json'))==published[key+'_sha256']==metrics[key+'_sha256']
    visual=load(review/'visual_review.json');assert visual['accepted_for_publication'] and visual['scientific_figures_individually_viewed']==2 and visual['images_sha256']==published['images']
    decision=load(review/'decision.json');assert not decision['native_or_runtime_promoted'] and decision['all216_counterfactuals54_budgets_retained']
    followup=a.workspace/'references/analysis/quantile_surface_v1'
    qknown=load(followup/'known1/report.json');qaudit=load(followup/'known_audit1/report.json')
    assert qknown['result']=='quantile_surface_known_ready' and qknown['controls']==7 and not qknown['material_read']
    assert qaudit['result']=='independent_quantile_surface_known_passed' and qaudit['queries']==9474
    assert qaudit['producer_sha256']==sha(followup/'known1/report.json')
    assert qaudit['auditor_sha256']==sha(repo/'tools/audit_quantile_surface_known_v1.py')==sha(followup/'known_audit1/executed_audit.py')
    assert qaudit['P_derivative_bound_verified'] and qaudit['changed_conditional_moment_explicitly_verified']
    for name,digest in qknown['sources'].items():assert sha(repo/name)==sha(followup/'known1/exact_sources'/name)==digest
    assert load(evidence/'known_audit1/report.json')['result']=='failed' and load(evidence/'real_audit1/report.json')['result']=='failed'
    assert not list(evidence.rglob('*.wav'))
    validation=dict(result='phase_input_paths_frozen',parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
        previous_goal_turn='Progress: ADI21569 resource recheck,1813 inputs exact and independent Decimal sums; no synthesis change. Previous synthesis stage36b5c20.',
        known_controls=9,known_audit=ka,source_models=6,seeds=3,conditional_decoders=3,sets=54,counterfactuals=216,frames=65536,
        declared_anchors=dict(normalized_P=1.,uniform=.5),real_audit=audit,results=load(review/'summary.json'),decision=decision,
        anchor_dependent_not_physical_shares=True,full_complex_signed_interference_preserved=True,all216_rows54_budgets_verified=True,
        scientific_figures_individually_viewed=2,failed_known_and_parallel_audit_attempts_preserved=True,
        followup_quantile_surface_known_controls=7,followup_quantile_surface_audit=qaudit,
        followup_new_phase_law_changes_conditional_moments=True,followup_real_material_started=False,
        C_H_exact=670,voice_parameters_exact=82,F2_files_exact=3,C_index_exact=True,protected_hearings_sha256=hearings,new_C_H=0,
        runtime_default_driver_owned_take_room_changed=False,native48k_aliasing_qualified=False,new_listening_question=False,
        old_68CTest_not_repeated=True,downloaded=False,pushed=False,physical_7_1_4=False,full_goal='active',next=decision['next'])
    sources=[n for n in names if Path(n).suffix in ('.c','.h','.cmake','.in') or n.endswith('CMakeLists.txt')]
    sources+=list(protected['voice_files_sha256.json'])+list(protected['F2_files_sha256.json'])+list(hearings)
    sources+=[n for n in names if 'phase_input' in n and Path(n).suffix in ('.py','.json','.md')]
    sources+=list(known['sources'])+list(producer['sources'])+list(published['sources'])+list(audit['oracles_sha256'])
    sources+=list(qknown['sources'])+['tools/audit_quantile_surface_known_v1.py',
        'research/quantile_surface_v1_plan.json','research/条件分位面已知控制V1.md']
    sources+=['tools/research_archive_v1.py','tools/verify_research_archive_independent_v1.py','tools/sound_dna/statistics.py',
        'tools/estimate_adi21569_v8.py','handoff/ADI21569算力估算V8.md',
        'research/条件相位输入路径V1.md','AGENTS.md','README.md','handoff/C文件索引.csv','handoff/开发留痕.md','handoff/研究续接.md','handoff/当前代码阅读入口.md']
    inputs=dict(data_AGENTS=a.workspace/'AGENTS.md',carrier_manifest=carrier/'manifest.json',carrier_validation=carrier/'validation.json',
        time_parent_manifest=parent/'manifest.json',time_parent_validation=parent/'validation.json',
        stream_manifest=stream/'manifest.json',stream_validation=stream/'validation.json',
        frozen_C_build_source_zip=a.workspace/'baselines/F3_local_atlas_v1/source.zip')
    resource=a.workspace/'references/analysis/adi21569_recheck_phase_input_v1'
    resource_receipt=load(resource/'arithmetic_recheck.json')
    assert resource_receipt['input_hashes_revalidated']==1813 and resource_receipt['no_runtime_or_model_change']
    assert resource_receipt['estimate_sha256']==sha(resource/'estimate.json')
    for name in ('estimate.json','arithmetic_recheck.json'):inputs['resource_recheck/'+name]=resource/name
    for folder in ('known1','known_audit1'):
        for path in (followup/folder).rglob('*'):
            if path.is_file():inputs['quantile_surface_known/'+path.relative_to(followup).as_posix()]=path
    for path in producer['inputs']:
        path=Path(path)
        if path.is_relative_to(parent):inputs['time_inputs/'+path.relative_to(parent).as_posix()]=path
        elif path.is_relative_to(carrier):inputs['carrier_inputs/'+path.relative_to(carrier).as_posix()]=path
        else:raise ValueError(path)
    shutil.copy2(__file__,evidence/'executed_package.py')
    result=freeze(root,repo,sources,evidence,inputs,validation);verify(root)
    save(repo/'research/phase_input_paths_v1_summary.json',dict(validation,**result))
    append_index(repo/'handoff/阶段索引.csv',['phase_input_paths_v1','baselines/phase_input_paths_v1/manifest.json',result['file_count'],result['manifest_sha256'],
        '9known;54sets216waves;104112complexGrams;all216rows54budgets;2figures','670C-H82voice3F2/index exact;anchored path diagnostics only',
        'research/条件相位输入路径V1.md | research/phase_input_paths_v1_summary.json','baselines/phase_input_paths_v1/validation.json'])
    print(dict(result='phase_input_paths_frozen',**result),flush=True)


if __name__=='__main__':main()
