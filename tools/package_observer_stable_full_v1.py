"""Freeze the one terminal full solve and independent evidence, including failures."""
import argparse, math, os, shutil, subprocess
from pathlib import Path
from research_archive_v1 import load, save, sha, freeze, verify, append_index


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace',type=Path,required=True)
    a=p.parse_args()
    repo=Path(__file__).resolve().parents[1]
    e=a.workspace/'references/analysis/observer_stable_residual_v1'
    full=load(e/'full1/report.json')
    independent=load(e/'full_audit1/report.json')
    pub=load(e/'full_review1/report.json')
    metrics=load(e/'full_review1/metrics_verification.json')
    visual=load(e/'full_review1/visual_review.json')
    units=load(e/'frequency_units_audit1/report.json')
    watch=load(e/'full_watch1/report.json')
    identity=load(e/'stationarity_gap_audit1/report.json')
    alignment=load(e/'full_gap_alignment1/report.json')
    assert full['result']=='observer_stable_full_known_measured' and full['only_one_attempt']
    assert independent['result']=='independent_observer_stable_full_passed'
    assert independent['producer_sha256']==sha(e/'full1/report.json')
    assert metrics['result']=='independent_observer_stable_full_publication_passed'
    assert metrics['producer_sha256']==sha(e/'full_review1/report.json')
    assert visual['scientific_figures_individually_viewed']==2 and visual['accepted_for_publication']
    assert visual['images_sha256']==pub['images']
    assert units['result']=='independent_observer_stable_frequency_units_passed'
    assert units['auditor_sha256']==sha(e/'frequency_units_audit1/executed_audit.py')==sha(repo/'tools/audit_observer_stable_frequency_units_v1.py')
    assert watch['result']=='observer_stable_full_watch_and_audit_terminal'
    assert watch['producer_exit_code']==watch['audit_exit_code']==0
    assert watch['producer_report_sha256']==sha(e/'full1/report.json')
    assert watch['audit_report_sha256']==sha(e/'full_audit1/report.json')
    assert watch['watcher_sha256']==sha(e/'full_watch1/executed_watch.py')==sha(repo/'tools/watch_observer_stable_full_v1.py')
    assert identity['result']=='independent_observer_stationarity_gap_identity_passed'
    assert alignment['result']=='independent_observer_stable_gap_alignment_passed'
    assert len(identity['controls'])==6 and identity['new_solves']==0
    assert len(alignment['subspace_known_controls'])==5
    parents={}
    inputs={}
    for name in ('observer_representer_v1','observer_stable_known_v1'):
        base=a.workspace/'baselines'/name
        summary=load(repo/'research'/f'{name}_summary.json')
        assert sha(base/'manifest.json')==summary['manifest_sha256']
        entries={row['path']:row['sha256'] for row in load(base/'manifest.json')['files']}
        parents[name]=(base,entries)
        for file in ('manifest.json','validation.json'): inputs[f'upstream/{name}/{file}']=base/file
    known,entries=parents['observer_stable_known_v1']
    protected={}
    for name,count in (('C_files_sha256.json',670),('voice_files_sha256.json',82),('F2_files_sha256.json',3)):
        assert sha(known/'evidence'/name)==entries['evidence/'+name]
        values=load(known/'evidence'/name)
        assert len(values)==count and all(sha(repo/n)==digest for n,digest in values.items())
        protected[name]=values
    names=set()
    for flags in (['ls-files','-z'],['ls-files','--others','--exclude-standard','-z']):
        names.update(subprocess.check_output(['git']+flags,cwd=repo).decode('utf-8').split('\0'))
    names.discard('')
    assert {n for n in names if Path(n).suffix in ('.c','.h')}==set(protected['C_files_sha256.json'])
    assert sha(repo/'handoff/C文件索引.csv')==entries['source/handoff/C文件索引.csv']
    hearings=load(repo/'research/observer_stable_known_v1_summary.json')['protected_hearings_sha256']
    assert all(sha(repo/name)==digest for name,digest in hearings.items())
    folders=('full1','full_audit1','full_review1','frequency_units_audit1','full_watch1',
        'stationarity_gap_audit1','full_gap_alignment1')
    locations={}
    def bind(original,digest):
        original=Path(original)
        assert sha(original)==digest
        if original.is_relative_to(e) and original.relative_to(e).parts[0] in folders:
            target='evidence/'+original.relative_to(e).as_posix()
        else:
            # The producer prerequisite originally lived beside the full run.
            # It is now bound to the byte-identical, immutable known archive.
            if original.is_relative_to(e):
                base,manifest=parents['observer_stable_known_v1']
                relative='evidence/'+original.relative_to(e).as_posix()
                name='observer_stable_known_v1'
            else:
                candidates=[(n,b,m) for n,(b,m) in parents.items() if original.is_relative_to(b)]
                assert len(candidates)==1,str(original)
                name,base,manifest=candidates[0]
                relative=original.relative_to(base).as_posix()
            assert manifest[relative]==sha(base/relative)==digest
            key=f'upstream/{name}/{relative}'
            inputs[key]=base/relative
            target='inputs/'+key
        locations[str(original)]=target
    for name,digest in full['sources'].items(): assert sha(repo/name)==sha(e/'full1/exact_sources'/name)==digest
    for name,digest in full['inputs'].items(): bind(name,digest)
    assert sha(e/'full1/capture.npz')==full['capture_sha256']
    for name,digest in full['basis_files'].items(): assert sha(e/'full1'/name)==digest
    for name in ('U','V'):
        assert (e/'full1/basis'/(name+'.bin')).stat().st_size==8*math.prod(full['solver']['basis_shapes'][name])
    assert independent['auditor_sha256']==sha(e/'full_audit1/executed_audit.py')==sha(repo/'tools/audit_observer_stable_full_v1.py')
    for j,(name,digest) in enumerate(independent['oracles_sha256'].items()):
        assert sha(repo/name)==sha(e/'full_audit1'/f'executed_oracle_{j}.py')==digest
    for name,digest in pub['inputs'].items(): bind(name,digest)
    for folder,report in (('stationarity_gap_audit1',identity),('full_gap_alignment1',alignment)):
        tool='tools/audit_observer_stationarity_gap_v1.py' if folder=='stationarity_gap_audit1' else 'tools/audit_observer_stable_gap_alignment_v1.py'
        assert report['auditor_sha256']==sha(e/folder/'executed_audit.py')==sha(repo/tool)
        for name,digest in report['inputs'].items(): bind(name,digest)
        for j,(name,digest) in enumerate(report['sources'].items()):
            assert sha(repo/name)==sha(e/folder/f'executed_oracle_{j}.py')==digest
        array='frozen_full_normals.npz' if folder=='stationarity_gap_audit1' else 'normals.npz'
        key='full_capture_sha256' if folder=='stationarity_gap_audit1' else 'normals_sha256'
        assert sha(e/folder/array)==report[key]
    assert sha(e/'full_review1/executed_publication.py')==sha(repo/'tools/publish_observer_stable_full_v1.py')==pub['publisher_sha256']
    assert metrics['auditor_sha256']==sha(e/'full_review1/executed_metrics_audit.py')==sha(repo/'tools/audit_observer_stable_full_review_v1.py')
    assert all(sha(e/'full_review1'/name)==digest for name,digest in pub['images'].items())
    stage=e/'full_package1'
    stage.mkdir(exist_ok=False)
    # All selected directories are terminal and immutable. Same-volume
    # staging hard links avoid a second 13GB temporary copy; freeze makes its
    # own ordinary files, and no linked evidence is edited after this point.
    for folder in folders: shutil.copytree(e/folder,stage/folder,copy_function=os.link)
    for name,values in protected.items(): save(stage/name,values)
    shutil.copy2(__file__,stage/'executed_package.py')
    inputs['data_AGENTS']=a.workspace/'AGENTS.md'
    sources=[n.removeprefix('source/') for n in entries if n.startswith('source/') and (repo/n.removeprefix('source/')).is_file()]
    sources += [n for n in names if 'observer_stable' in n and Path(n).suffix in ('.py','.json','.md')]
    sources += ['research/稳定残差完整声源求解V1.md']
    sources += ['tools/audit_observer_stationarity_gap_v1.py','research/observer_stable_full_followup_v1_plan.json']
    validation=dict(result='observer_stable_full_frozen',results=pub['summary'],original_input_archive_locations=locations,
        upstream_manifests_sha256={n:sha(v[0]/'manifest.json') for n,v in parents.items()},
        C_H_exact=670,voice_parameters_exact=82,F2_files_exact=3,C_index_exact=True,protected_hearings_sha256=hearings,
        selected_terminal_evidence_directories=list(folders),one_same_full_attempt=True,solver_qualified=full['solver_qualified'],
        fidelity_qualified=full['fidelity_qualified'],full_basis_Grams_independently_verified=True,
        selected_projection_columns_independently_verified=len(independent['independently_checked_projection_columns']),
        scientific_figures_individually_viewed=2,original_gates_and_objective_unchanged=True,all_regressions_retained=True,
        independent_gap_identity_controls=6,terminal_complete_normal_alignment_verified=True,
        independent_subspace_controls=5,
        original_analysis_rate=65536,final_band_includes_Nyquist=True,native48k_or_C_or_timbre_qualified=False,
        runtime_default_driver_owned_take_room_changed=False,old_68CTest_not_repeated=True,downloaded=False,pushed=False,full_goal='active')
    root=a.workspace/'baselines/observer_stable_full_v1'
    result=freeze(root,repo,sources,stage,inputs,validation)
    verify(root)
    save(repo/'research/observer_stable_full_v1_summary.json',dict(validation,**result))
    append_index(repo/'handoff/阶段索引.csv',['observer_stable_full_v1','baselines/observer_stable_full_v1/manifest.json',
        result['file_count'],result['manifest_sha256'],f"one full288;solver={full['solver_qualified']};fidelity={full['fidelity_qualified']}",
        '670C-H82voice3F2/index exact;no source/audio promotion','research/稳定残差完整声源求解V1.md | research/observer_stable_full_v1_summary.json',
        'baselines/observer_stable_full_v1/validation.json'])
    print(dict(result='observer_stable_full_frozen',**result),flush=True)


if __name__=='__main__':
    main()
