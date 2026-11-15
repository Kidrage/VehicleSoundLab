"""Freeze all inference attempts, blind-spot evidence and unchanged contracts."""
import argparse,shutil,subprocess
from pathlib import Path
from research_archive_v1 import load,save,sha,freeze,verify,append_index


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace',type=Path,required=True);a=p.parse_args()
    repo=Path(__file__).resolve().parents[1]
    e=a.workspace/'references/analysis/observer_inverse_v1'
    root=a.workspace/'baselines/observer_inverse_v1'
    parent=a.workspace/'baselines/quantile_surface_v1'
    assert sha(parent/'manifest.json')==load(repo/'research/quantile_surface_v1_summary.json')['manifest_sha256']
    protected={}
    for name,count in (('C_files_sha256.json',670),('voice_files_sha256.json',82),('F2_files_sha256.json',3)):
        values=load(parent/'evidence'/name)
        assert len(values)==count and all(sha(repo/n)==d for n,d in values.items())
        save(e/name,values);protected[name]=values
    names=set()
    for flags in (['ls-files','-z'],['ls-files','--others','--exclude-standard','-z']):
        names.update(subprocess.check_output(['git']+flags,cwd=repo).decode('utf-8').split('\0'))
    names.discard('')
    assert {n for n in names if Path(n).suffix in ('.c','.h')}==set(protected['C_files_sha256.json'])
    pm={row['path']:row['sha256'] for row in load(parent/'manifest.json')['files']}
    assert sha(repo/'handoff/C文件索引.csv')==pm['source/handoff/C文件索引.csv']
    hearings=load(parent/'validation.json')['protected_hearings_sha256']
    assert all(sha(repo/n)==d for n,d in hearings.items())
    producers={n:load(e/n/'report.json') for n in ('known1','precondition_known1','batched_known1','refinement_known1','real1','real2','real3','visibility1','visibility2')}
    historical=[];allinputs={}
    for folder,record in producers.items():
        assert record['result']!='running' and record['result']!='failed'
        for name,digest in record.get('sources',{}).items():
            assert sha(e/folder/'exact_sources'/name)==digest
            if sha(repo/name)!=digest:historical.append(dict(attempt=folder,file=name,executed_sha256=digest,current_sha256=sha(repo/name)))
        for path,digest in record.get('inputs',{}).items():
            assert sha(path)==digest
            if path in allinputs:assert allinputs[path]==digest
            allinputs[path]=digest
    audits={}
    specs=(('known_audit1','known1','independent_observer_inverse_known_passed'),
        ('precondition_known_audit1','precondition_known1','independent_observer_inverse_precondition_known_passed'),
        ('batched_known_audit1','batched_known1','independent_observer_inverse_known_passed'),
        ('refinement_known_audit1','refinement_known1','independent_observer_inverse_refinement_known_passed'),
        ('original_real_audit1','real1','independent_observer_inverse_original_passed'),
        ('real_audit1','real2','independent_observer_inverse_real_passed'),
        ('real_audit2','real3','independent_observer_inverse_real_passed'),
        ('visibility_audit1','visibility1','independent_observer_inverse_visibility_passed'),
        ('visibility_audit2','visibility2','independent_observer_inverse_visibility_passed'))
    for name,producer,result in specs:
        audit=load(e/name/'report.json')
        assert audit['result']==result and audit['producer_sha256']==sha(e/producer/'report.json')
        assert audit['auditor_sha256']==sha(e/name/'executed_audit.py')
        audits[name]=audit
    weak=load(e/'weakbands_audit2/report.json')
    assert weak['result']=='independent_observer_inverse_weakbands_passed' and weak['captures']==54
    for path,digest in weak['studies'].items():assert sha(Path(path)/'report.json')==digest
    assert weak['auditor_sha256']==sha(e/'weakbands_audit2/executed_audit.py')
    review=e/'review1';pub=load(review/'report.json');ma=load(review/'metrics_verification.json')
    visual=load(review/'visual_review.json');decision=load(review/'decision.json')
    assert pub['result']=='observer_inverse_review_ready' and ma['result']=='independent_observer_inverse_publication_passed'
    assert ma['all24_rows_verified'] and ma['all18_solver_records_verified'] and ma['all_aggregates_and_improvement_regression_counts_verified']
    for path,digest in pub['inputs'].items():assert sha(path)==digest
    for name,digest in pub['sources'].items():assert sha(repo/name)==sha(review/'exact_sources'/name)==digest
    for key in ('figure_inputs','solve_inputs','summary'):
        assert sha(review/(key+'.json'))==pub[key+'_sha256']==ma[key+'_sha256']
    assert ma['auditor_sha256']==sha(review/'executed_metrics_audit.py')==sha(repo/'tools/audit_observer_inverse_review_v1.py')
    assert visual['scientific_figures_individually_viewed']==2 and visual['accepted_for_publication']
    for name,digest in pub['images'].items():assert sha(review/name)==digest==visual['images_sha256'][name]
    assert not decision['native_or_runtime_promoted']
    assert not list(e.rglob('*.wav'))
    inputs={'data_AGENTS':a.workspace/'AGENTS.md'};locations={}
    for path,digest in allinputs.items():
        path=Path(path)
        if path.is_relative_to(e):locations[str(path)]='evidence/'+path.relative_to(e).as_posix()
        else:
            assert path.is_relative_to(a.workspace/'baselines')
            rel=path.relative_to(a.workspace/'baselines').as_posix()
            inputs['upstream/'+rel]=path;locations[str(path)]='inputs/upstream/'+rel
    for name in ('observer_forward_known_v1','conditional_phase_time_v1','coefficient_geometry_v1','quantile_surface_v1'):
        folder=a.workspace/'baselines'/name
        assert sha(folder/'manifest.json')==load(repo/f'research/{name}_summary.json')['manifest_sha256']
        for file in ('manifest.json','validation.json'):inputs['upstream/'+name+'/'+file]=folder/file
    for file in ('v9_recheck.json','arithmetic_audit.json'):
        inputs['resource/adi21569_v10/'+file]=a.workspace/'references/analysis/adi21569_estimate_v10'/file
    validation=dict(result='observer_inverse_frozen',source_models=6,engines=1,published_rows=24,
        all18_final_solver_records_retained=True,all_correction_checkpoints_retained=True,
        all_source_native_warp_arrays_preserved=True,historical_executed_sources=historical,
        original_input_archive_locations=locations,known_and_real_audits=audits,weakband_audit=weak,
        results=load(review/'summary.json'),decision=decision,scientific_figures_individually_viewed=2,
        C_H_exact=670,voice_parameters_exact=82,F2_files_exact=3,C_index_exact=True,
        protected_hearings_sha256=hearings,runtime_default_driver_owned_take_room_changed=False,
        new_stochastic_source=False,native48k_or_C_or_timbre_qualified=False,
        old_68CTest_not_repeated=True,downloaded=False,pushed=False,full_goal='active',next=decision['next'])
    sources=[n for n in names if Path(n).suffix in ('.c','.h','.cmake','.in') or n.endswith('CMakeLists.txt')]
    sources+=list(protected['voice_files_sha256.json'])+list(protected['F2_files_sha256.json'])+list(hearings)
    sources+=[n for n in names if ('observer_inverse' in n or 'observer_forward' in n) and Path(n).suffix in ('.py','.json','.md')]
    sources+=['tools/research_archive_v1.py','tools/verify_research_archive_independent_v1.py',
        'tools/circular_phase_lift_v1/audit_oracle.py','tools/conditional_phase_time_v1/observer.py',
        'tools/carrier_transfer_v1/spectral.py','tools/carrier_transfer_v1/groups.py','tools/sound_dna/windowed.py',
        'research/同窗逆问题与边界诊断V1.md','handoff/ADI21569算力估算V10.md','research/adi21569_estimate_v10_summary.json',
        'tools/estimate_adi21569_v9.py','AGENTS.md','README.md','handoff/C文件索引.csv',
        'handoff/开发留痕.md','handoff/研究续接.md','handoff/当前代码阅读入口.md']
    shutil.copy2(__file__,e/'executed_package.py')
    result=freeze(root,repo,sources,e,inputs,validation);verify(root)
    save(repo/'research/observer_inverse_v1_summary.json',dict(validation,**result))
    append_index(repo/'handoff/阶段索引.csv',['observer_inverse_v1','baselines/observer_inverse_v1/manifest.json',
        result['file_count'],result['manifest_sha256'],'8equivalent+3dense+6correction;all6x3attempts/24outcomes;54weakband/visibility',
        '670C-H82voice3F2/index exact;in-sample diagnostics,not a sound preset',
        'research/同窗逆问题与边界诊断V1.md | research/observer_inverse_v1_summary.json','baselines/observer_inverse_v1/validation.json'])
    print(dict(result='observer_inverse_frozen',**result),flush=True)


if __name__=='__main__':main()
