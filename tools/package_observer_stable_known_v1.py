"""Freeze terminal small stable-QR evidence; exclude the live full288 run."""
import argparse, shutil, subprocess
from pathlib import Path
from research_archive_v1 import load, save, sha, freeze, verify, append_index


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace',type=Path,required=True)
    a=p.parse_args()
    repo=Path(__file__).resolve().parents[1]
    e=a.workspace/'references/analysis/observer_stable_residual_v1'
    root=a.workspace/'baselines/observer_stable_known_v1'
    stage=e/'known_package1'
    folders=('controls1','controls_audit1','known1','known_audit1','known_mapped1','known_mapped_audit1','storage_audit1','known_review1')
    parents={}
    inputs={}
    for name in ('observer_representer_v1','observer_krylov_v1'):
        parent=a.workspace/'baselines'/name
        summary=load(repo/'research'/f'{name}_summary.json')
        assert sha(parent/'manifest.json')==summary['manifest_sha256']
        manifest=load(parent/'manifest.json')
        parents[name]=(parent,{r['path']:r['sha256'] for r in manifest['files']})
        for filename in ('manifest.json','validation.json'):
            inputs[f'upstream/{name}/{filename}']=parent/filename
    inherited=load(repo/'research/observer_krylov_v1_summary.json')
    parent,entries=parents['observer_krylov_v1']
    protected={}
    for name,count in (('C_files_sha256.json',670),('voice_files_sha256.json',82),('F2_files_sha256.json',3)):
        path=parent/'evidence'/name
        assert sha(path)==entries['evidence/'+name]
        values=load(path)
        assert len(values)==count and all(sha(repo/n)==d for n,d in values.items())
        protected[name]=values
    names=set()
    for flags in (['ls-files','-z'],['ls-files','--others','--exclude-standard','-z']):
        names.update(subprocess.check_output(['git']+flags,cwd=repo).decode('utf-8').split('\0'))
    names.discard('')
    assert {n for n in names if Path(n).suffix in ('.c','.h')}==set(protected['C_files_sha256.json'])
    assert sha(repo/'handoff/C文件索引.csv')==entries['source/handoff/C文件索引.csv']
    hearings=inherited['protected_hearings_sha256']
    assert all(sha(repo/n)==d for n,d in hearings.items())
    locations={}
    def bind(path,digest):
        path=Path(path)
        assert sha(path)==digest
        if path.is_relative_to(e):
            relative=path.relative_to(e)
            assert relative.parts[0] in folders, str(path)
            target='evidence/'+relative.as_posix()
        else:
            matched=False
            for name,(base,manifest) in parents.items():
                if path.is_relative_to(base):
                    relative=path.relative_to(base).as_posix()
                    assert manifest[relative]==digest
                    key=f'upstream/{name}/{relative}'
                    inputs[key]=path
                    target='inputs/'+key
                    matched=True
                    break
            assert matched,str(path)
        locations[str(path)]=target
    for folder,result in (('controls1','observer_stable_controls_measured'),('known1','observer_stable_known_measured'),('known_mapped1','observer_stable_known_measured')):
        r=load(e/folder/'report.json')
        assert r['result']==result
        for name,digest in r['sources'].items(): assert sha(repo/name)==sha(e/folder/'exact_sources'/name)==digest
        for name,digest in r.get('inputs',{}).items(): bind(name,digest)
        for case in r['cases']: assert sha(e/folder/case['file'])==case['sha256']
        if folder!='controls1': assert r['all_qualified'] and len(r['cases'])==12
    audits=(('controls_audit1','controls1','tools/audit_observer_stable_controls_v1.py'),
        ('known_audit1','known1','tools/audit_observer_stable_known_v1.py'),
        ('known_mapped_audit1','known_mapped1','tools/audit_observer_stable_known_v1.py'))
    for folder,producer,script in audits:
        r=load(e/folder/'report.json')
        assert r['result'].startswith('independent_') and r['result'].endswith('_passed')
        assert r['producer_sha256']==sha(e/producer/'report.json')
        assert r['auditor_sha256']==sha(e/folder/'executed_audit.py')==sha(repo/script)
        for j,(name,digest) in enumerate(r.get('oracles_sha256',{}).items()):
            assert sha(repo/name)==sha(e/folder/f'executed_oracle_{j}.py')==digest
    storage=load(e/'storage_audit1/report.json')
    assert storage['result']=='independent_observer_stable_storage_passed'
    assert storage['RAM_report_sha256']==sha(e/'known1/report.json')
    assert storage['mapped_report_sha256']==sha(e/'known_mapped1/report.json')
    assert storage['auditor_sha256']==sha(e/'storage_audit1/executed_audit.py')==sha(repo/'tools/audit_observer_stable_storage_v1.py')
    for case in storage['cases']:
        for name,digest in case['raw_basis_files_sha256'].items(): assert sha(e/'known_mapped1'/name)==digest
    pub=load(e/'known_review1/report.json')
    review=load(e/'known_review1/metrics_verification.json')
    visual=load(e/'known_review1/visual_review.json')
    assert review['result']=='independent_observer_stable_known_publication_passed'
    assert review['producer_sha256']==sha(e/'known_review1/report.json')
    assert visual['scientific_figures_individually_viewed']==2 and visual['accepted_for_publication']
    assert visual['images_sha256']==pub['images']
    for name,digest in pub['inputs'].items(): bind(name,digest)
    for name,digest in pub['images'].items(): assert sha(e/'known_review1'/name)==digest
    # The full run is deliberately not opened here, even for its progress file.
    stage.mkdir(parents=True,exist_ok=False)
    for folder in folders: shutil.copytree(e/folder,stage/folder)
    for name,values in protected.items(): save(stage/name,values)
    shutil.copy2(__file__,stage/'executed_package.py')
    inputs['data_AGENTS']=a.workspace/'AGENTS.md'
    sources=[n.removeprefix('source/') for n in entries if n.startswith('source/') and (repo/n.removeprefix('source/')).is_file()]
    sources += [n for n in names if any(v in n for v in ('observer_stable','krylov_diagnostic')) and Path(n).suffix in ('.py','.json','.md')]
    sources += ['research/稳定残差声源提取控制V1.md']
    validation=dict(result='observer_stable_known_frozen',results=pub['summary'],original_input_archive_locations=locations,
        upstream_manifests_sha256={n:sha(v[0]/'manifest.json') for n,v in parents.items()},
        C_H_exact=670,voice_parameters_exact=82,F2_files_exact=3,C_index_exact=True,protected_hearings_sha256=hearings,
        selected_terminal_evidence_directories=list(folders),live_full_output_included=False,
        known_cases=12,backend_runs=2,not_24_distinct_observations=True,estimator_controls=7,
        old_eight_direct_stopping_failures_retained_in_parent=True,fitted_parameters_bitwise_equal_old=True,
        scientific_figures_individually_viewed=2,original_gates_and_objective_unchanged=True,
        native48k_or_C_or_timbre_qualified=False,runtime_default_driver_owned_take_room_changed=False,
        old_68CTest_not_repeated=True,downloaded=False,pushed=False,full_goal='active',
        previous_goal_turn_classification='MCPS recheck: resource evidence only, no synthesis improvement',
        next='Observe session51412/PID35128; only after terminal run independent full audit; do not restart or fit material before gates')
    result=freeze(root,repo,sources,stage,inputs,validation)
    verify(root)
    save(repo/'research/observer_stable_known_v1_summary.json',dict(validation,**result))
    append_index(repo/'handoff/阶段索引.csv',['observer_stable_known_v1','baselines/observer_stable_known_v1/manifest.json',
        result['file_count'],result['manifest_sha256'],'7controls/12known RAM+mapped PASS;full output excluded',
        '670C-H82voice3F2/index exact;no source/audio promotion',
        'research/稳定残差声源提取控制V1.md | research/observer_stable_known_v1_summary.json','baselines/observer_stable_known_v1/validation.json'])
    print(dict(result='observer_stable_known_frozen',**result),flush=True)


if __name__=='__main__':
    main()
