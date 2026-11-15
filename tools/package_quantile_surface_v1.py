"""Freeze all new laws and failed attempts, old publication provenance and C."""
import argparse,csv,shutil,subprocess
from pathlib import Path
from research_archive_v1 import load,save,sha,freeze,verify,append_index


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True);a=p.parse_args()
    repo=Path(__file__).resolve().parents[1];e=a.workspace/'references/analysis/quantile_surface_v1';root=a.workspace/'baselines/quantile_surface_v1'
    carrier=a.workspace/'baselines/carrier_transfer_v1';parent=a.workspace/'baselines/conditional_phase_time_v1';stream=a.workspace/'baselines/phase_stream_control_v1'
    for folder in (carrier,parent,stream):assert sha(folder/'manifest.json')==load(repo/f'research/{folder.name}_summary.json')['manifest_sha256']
    entries={r['path']:r['sha256'] for r in load(carrier/'manifest.json')['files']};protected={}
    for name,count in (('C_files_sha256.json',670),('voice_files_sha256.json',82),('F2_files_sha256.json',3)):
        v=load(carrier/'evidence'/name);assert len(v)==count and all(sha(repo/n)==d for n,d in v.items());save(e/name,v);protected[name]=v
    names=set()
    for flags in (['ls-files','-z'],['ls-files','--others','--exclude-standard','-z']):names.update(subprocess.check_output(['git']+flags,cwd=repo).decode('utf-8').split('\0'))
    names.discard('');assert {n for n in names if Path(n).suffix in ('.c','.h')}==set(protected['C_files_sha256.json'])
    assert sha(repo/'handoff/C文件索引.csv')==entries['source/handoff/C文件索引.csv']
    index=list(csv.reader((repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig',newline='')));assert len(index)==671
    assert all(r[4]==protected['C_files_sha256.json'][r[0]] for r in index[1:])
    hearings=load(carrier/'validation.json')['protected_hearings_sha256'];assert all(sha(repo/n)==d for n,d in hearings.items())
    known=load(e/'known1/report.json');ka=load(e/'known_audit1/report.json')
    assert known['result']=='quantile_surface_known_ready' and ka['result']=='independent_quantile_surface_known_passed'
    assert ka['cases']==7 and ka['queries']==9474 and ka['producer_sha256']==sha(e/'known1/report.json')
    seam=load(e/'seam2/report.json');sa=load(e/'seam_audit2/report.json')
    assert seam['result']=='quantile_seam_known_ready' and sa['result']=='independent_quantile_seam_known_passed'
    assert sa['producer_sha256']==sha(e/'seam2/report.json') and sa['endcap_preparation_verified']
    for desc,folder in ((known,e/'known1'),(seam,e/'seam2')):
        for name,digest in desc['sources'].items():assert sha(repo/name)==sha(folder/'exact_sources'/name)==digest
    for audit,folder,name in ((ka,e/'known_audit1','tools/audit_quantile_surface_known_v1.py'),(sa,e/'seam_audit2','tools/audit_quantile_surface_seam_v1.py')):
        assert audit['auditor_sha256']==sha(repo/name)==sha(folder/'executed_audit.py')
    producer=load(e/'real2/report.json');audit=load(e/'real_audit2/report.json')
    assert producer['result']=='quantile_surface_all54_ready' and audit['result']=='independent_quantile_surface_real_passed'
    assert audit['producer_sha256']==sha(e/'real2/report.json')
    assert audit['auditor_sha256']==sha(repo/'tools/audit_quantile_surface_real_v1.py')==sha(e/'real_audit2/executed_audit.py')
    for i,(name,digest) in enumerate(audit['oracles_sha256'].items()):assert sha(repo/name)==sha(e/'real_audit2'/f'executed_oracle_{i}.py')==digest
    for name,digest in producer['sources'].items():assert sha(repo/name)==sha(e/'real2/exact_sources'/name)==digest
    for path,digest in producer['inputs'].items():assert sha(path)==digest
    assert (audit['waves'],audit['observer_rows'],audit['Gram_matrices'],audit['midpoint_moments'])==(54,13014,104112,160704)
    review=e/'review1';pub=load(review/'report.json');ma=load(review/'metrics_verification.json');visual=load(review/'visual_review.json');decision=load(review/'decision.json')
    assert pub['result']=='quantile_surface_review_ready' and ma['all162_rows_and_aggregates_verified'] and ma['all160704_moment_losses_verified']
    assert pub['producer_sha256']==sha(e/'real2/report.json') and pub['audit_sha256']==sha(e/'real_audit2/report.json')
    for name,digest in pub['sources'].items():assert sha(repo/name)==sha(review/'exact_sources'/name)==digest
    for name,digest in pub['images'].items():assert sha(review/name)==digest
    for name,digest in pub['inputs'].items():assert sha(name)==digest
    assert ma['auditor_sha256']==sha(repo/'tools/audit_quantile_surface_review_v1.py')==sha(review/'executed_metrics_audit.py')
    for key in ('summary','figure_inputs','moment_inputs'):assert sha(review/(key+'.json'))==pub[key+'_sha256']==ma[key+'_sha256']
    assert visual['accepted_for_publication'] and visual['scientific_figures_individually_viewed']==2 and visual['images_sha256']==pub['images']
    assert not decision['native_or_runtime_promoted'] and decision['all162_outcomes_and160704_moments_retained']
    assert load(e/'real1/report.json')['result']==load(e/'real_audit1/report.json')['result']=='failed'
    assert not list(e.rglob('*.wav'))
    validation=dict(result='quantile_surface_frozen',parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
        previous_goal_turn='Progress: ADI V9 resource estimate and completed original quantile producer/auditor; no target optimization or sound promotion.',
        known_controls=7,known_queries=9474,seam_controls=sa,source_models=6,saved_streams=3,new_maps=3,new_waves=54,all_published_outcomes=162,
        midpoint_moments=160704,real_audit=audit,results=load(review/'summary.json'),decision=decision,scientific_figures_individually_viewed=2,
        old108_literal_previously_audited=True,old_raw_wave_archives_still_required_for_full_historical_recompute=True,
        C_H_exact=670,voice_parameters_exact=82,F2_files_exact=3,C_index_exact=True,protected_hearings_sha256=hearings,
        runtime_default_driver_owned_take_room_changed=False,native48k_aliasing_qualified=False,old_68CTest_not_repeated=True,
        new_listening_question=False,downloaded=False,pushed=False,physical_7_1_4=False,full_goal='active',next=decision['next'])
    sources=[n for n in names if Path(n).suffix in ('.c','.h','.cmake','.in') or n.endswith('CMakeLists.txt')]
    sources+=list(protected['voice_files_sha256.json'])+list(protected['F2_files_sha256.json'])+list(hearings)
    sources+=[n for n in names if ('quantile_surface' in n or 'observer_forward' in n) and Path(n).suffix in ('.py','.json','.md')]
    sources+=list(known['sources'])+list(seam['sources'])+list(producer['sources'])+list(pub['sources'])+list(audit['oracles_sha256'])
    sources+=['tools/research_archive_v1.py','tools/verify_research_archive_independent_v1.py','tools/sound_dna/statistics.py',
        'tools/estimate_adi21569_v9.py','handoff/ADI21569算力估算V9.md','research/adi21569_estimate_v9_summary.json',
        'research/条件分位面实源对照V1.md','AGENTS.md','README.md','handoff/C文件索引.csv','handoff/开发留痕.md','handoff/研究续接.md','handoff/当前代码阅读入口.md']
    inputs=dict(data_AGENTS=a.workspace/'AGENTS.md',frozen_C_build_source_zip=a.workspace/'baselines/F3_local_atlas_v1/source.zip')
    for label,folder in (('carrier',carrier),('time_parent',parent),('old_stream',stream)):
        for file in ('manifest.json','validation.json'):inputs[label+'/'+file]=folder/file
    for name in ('figure_inputs.json','summary.json','report.json','metrics_verification.json'):
        inputs['old_stream/evidence/review1/'+name]=stream/'evidence/review1'/name
    for path in producer['inputs']:
        path=Path(path);assert path.is_relative_to(parent);inputs['time_parent/'+path.relative_to(parent).as_posix()]=path
    resource=a.workspace/'references/analysis/adi21569_estimate_v9/arithmetic_audit.json';rv=load(resource)
    assert rv['passed'] and rv['estimate_SHA256']==sha(repo/'research/adi21569_estimate_v9_summary.json')
    inputs['resource/adi21569_v9_arithmetic_audit.json']=resource
    shutil.copy2(__file__,e/'executed_package.py')
    result=freeze(root,repo,sources,e,inputs,validation);verify(root)
    save(repo/'research/quantile_surface_v1_summary.json',dict(validation,**result))
    append_index(repo/'handoff/阶段索引.csv',['quantile_surface_v1','baselines/quantile_surface_v1/manifest.json',result['file_count'],result['manifest_sha256'],
        '7known+seam;54new/162all;104112Grams;160704moments;allpublication/audit;2figures',
        '670C-H82voice3F2/index exact;new distribution not promoted','research/条件分位面实源对照V1.md | research/quantile_surface_v1_summary.json',
        'baselines/quantile_surface_v1/validation.json'])
    print(dict(result='quantile_surface_frozen',**result),flush=True)


if __name__=='__main__':main()
