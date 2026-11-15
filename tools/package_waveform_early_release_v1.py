"""Freeze native base graph, owned source release, full proof and actual shapes."""
import argparse
import shutil
import subprocess
from pathlib import Path
from research_archive_v1 import load,save,sha,freeze,verify,append_index


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True);a=p.parse_args()
    repo=Path(__file__).resolve().parents[1];e=a.workspace/'references/analysis/waveform_early_release_v1'
    folders=('controls1','controls_audit1','roots1','roots_audit1','roots_native_audit1',
             'known1','known_audit1','shared1','shared_audit1','lifetime_audit1',
             'full1','full_audit1','real_resources1','real_resources_audit1')
    reports={n:load(e/n/'report.json') for n in folders}
    assert reports['controls_audit1']['all_qualified'] and reports['roots_audit1']['all_qualified']
    assert reports['roots_native_audit1']['result']=='independent_waveform_banded_controls_passed'
    for name,count in (('known_audit1',12),('shared_audit1',8)):
        assert reports[name]['all_qualified'] and reports[name]['pass_count']==count
    life=reports['lifetime_audit1'];full=reports['full1'];audit=reports['full_audit1']
    assert life['actual_lifetimes_verified'] and life['all_output_arrays_bitwise_previous']
    assert len(life['cases'])==20 and len(life['ownership_guards'])==8
    assert full['owned_pipeline'] and audit['solver_qualified'] and audit['fidelity_qualified']
    assert audit['base_graph_copy_avoided'] and audit['source_released_before_inner']
    assert audit['producer_sha256']==sha(e/'full1/report.json')
    resources=reports['real_resources1'];resource_audit=reports['real_resources_audit1']
    assert resource_audit['result']=='independent_waveform_early_release_real_resources_verified'
    assert resource_audit['producer_sha256']==sha(e/'real_resources1/report.json')
    paths=set()
    for flags in (['ls-files','-z'],['ls-files','--others','--exclude-standard','-z']):
        paths.update(subprocess.check_output(['git']+flags,cwd=repo).decode('utf-8').split('\0'))
    previous=a.workspace/'baselines/recorded_phase_context_v1'
    protected={};sources=set();parents={};inputs={};locations={}
    for name,count in (('C_files_sha256.json',670),('voice_files_sha256.json',82),('F2_files_sha256.json',3)):
        values=load(previous/'evidence'/name);assert len(values)==count and all(sha(repo/n)==h for n,h in values.items())
        protected[name]=values;sources.update(values)
    assert {n for n in paths if Path(n).suffix in ('.c','.h')}==set(protected['C_files_sha256.json'])
    assert sha(repo/'handoff/C文件索引.csv')==sha(previous/'source/handoff/C文件索引.csv')
    hearings=load(repo/'research/recorded_phase_context_v1_summary.json')['protected_hearings_sha256']
    assert all(sha(repo/n)==h for n,h in hearings.items());sources.update(hearings)
    def parent(name):
        if name not in parents:
            root=a.workspace/'baselines'/name
            assert sha(root/'manifest.json')==load(repo/f'research/{name}_summary.json')['manifest_sha256']
            parents[name]=(root,{r['path']:r['sha256'] for r in load(root/'manifest.json')['files']})
            for leaf in ('manifest.json','validation.json'):inputs[f'upstream/{name}/{leaf}']=root/leaf
        return parents[name]
    parent('recorded_phase_context_v1');parent('waveform_correction_storage_v1')
    def bind(name,digest):
        path=Path(name);assert sha(path)==digest
        if path.is_relative_to(e):
            rel=path.relative_to(e);assert rel.parts[0] in folders;target='evidence/'+rel.as_posix()
        elif path.is_relative_to(repo):
            key='current/'+path.relative_to(repo).as_posix();inputs[key]=path;target='inputs/'+key
        elif path.is_relative_to(a.workspace/'baselines'):
            archive=path.relative_to(a.workspace/'baselines').parts[0]
            root,mapping=parent(archive);leaf=path.relative_to(root).as_posix()
            assert (sha(root/'manifest.json') if leaf=='manifest.json' else mapping[leaf])==digest
            key=f'upstream/{archive}/{leaf}';inputs[key]=path;target='inputs/'+key
        else:raise AssertionError(('Unexpected input',path))
        locations[str(path)]=target
    for folder,report in reports.items():
        for key in ('inputs','input_sha256'):
            for name,digest in report.get(key,{}).items():bind(name,digest)
        for name,digest in report.get('sources',{}).items():
            assert sha(e/folder/'exact_sources'/name)==digest;sources.add(name)
        for key in ('oracle_sha256','oracles_sha256'):
            sources.update(report.get(key,{}))
    sources.update(n for n in paths if 'waveform_early_release' in n and Path(n).suffix in ('.py','.md','.json'))
    sources.discard('research/waveform_early_release_v1_summary.json')
    sources.update(('research/基础三角与提前释放V1.md','tools/verify_waveform_early_release_bindings_v1.py',
        'tools/audit_waveform_correction_native_full_v1.py','tools/audit_waveform_correction_known_v1.py',
        'tools/audit_waveform_correction_controls_v1.py','tools/audit_waveform_structured_controls_v1.py',
        'tools/audit_waveform_banded_controls_v1.py','tools/research_archive_v1.py',
        'tools/verify_research_archive_independent_v1.py','AGENTS.md','README.md','CMakeLists.txt',
        'handoff/C文件索引.csv','handoff/当前代码阅读入口.md','handoff/研究续接.md'))
    sources={n for n in sources if n and (repo/n).is_file()}
    stage=e/'package1';stage.mkdir(exist_ok=False)
    for folder in folders:shutil.copytree(e/folder,stage/folder)
    for name,values in protected.items():save(stage/name,values)
    shutil.copy2(__file__,stage/'executed_package.py');inputs['data_AGENTS.md']=a.workspace/'AGENTS.md'
    summary=dict(result='waveform_early_release_known_full_and_actual_shapes_frozen',
        selected_terminal_evidence_directories=list(folders),original_input_archive_locations=locations,
        upstream_manifests_sha256={n:sha(root/'manifest.json') for n,(root,mapping) in parents.items()},
        inverse_controls=8,original_arbitrary_controls=7,DFT_controls=4,temporal_controls=3,
        original12=12,shared8=8,actual_ownership_guards=8,all20arrays_bitwise_previous=True,
        full_solver_qualified=True,full_fidelity_qualified=True,
        full_gradient=audit['gradient'],full_stable_normal=audit['stable_original_complete_normal'],full_backward=audit['original_backward'],
        full_metrics=audit['metrics'],all17_comparison_rows=audit['comparison_rows'],
        full_all_three_original_histories=audit['original_correction_history'],
        full_base_main_bytes=audit['actual_full_main_array_bytes'],previous_full_base_main_bytes=8368514064,
        full_actual_WS_peak=full['process_memory']['cumulative_peak_working_set_bytes'],
        full_actual_private_commit_peak=full['process_memory']['cumulative_peak_private_commit_bytes'],
        full_registered_backing_peak=full['resources']['max_tracked_live_backing_bytes'],
        full_elapsed_host_seconds=full['solve_wall_seconds'],
        full_base_triangle_and_source_lifetimes_independently_verified=True,
        actual_real_shape_resource_cases=resources['cases'],real_resource_audit_cases=resource_audit['cases'],
        all_six_recorded_contexts_qualified_upstream=True,no_large_real_fit_or_C_or_hearing_promotion=True,
        exact_storage_for_context_still_required=True,default_old_pipeline_and_inverse_unchanged=True,
        C_H_exact=670,voice_parameters_exact=82,F2_files_exact=3,C_index_exact=True,protected_hearings_sha256=hearings,
        runtime_default_driver_owned_take_room_changed=False,downloaded=False,pushed=False,old68CTest_not_repeated=True,
        full_goal='active',previous_goal_turn='MCPS recheck only; no synthesis progress. Current stage independently completes full extraction, actual lifetime and twelve real resource qualifications.')
    root=a.workspace/'baselines/waveform_early_release_v1';result=freeze(root,repo,sources,stage,inputs,summary);verify(root)
    save(repo/'research/waveform_early_release_v1_summary.json',dict(summary,**result))
    append_index(repo/'handoff/阶段索引.csv',['waveform_early_release_v1','baselines/waveform_early_release_v1/manifest.json',
        result['file_count'],result['manifest_sha256'],'native BASEgraphT/earlyX;original12/shared8/full known independentlyPASS',
        '670C-H82voice3F2/index exact;actualsix contexts still resource-gated;no source/C promotion',
        'research/基础三角与提前释放V1.md | research/waveform_early_release_v1_summary.json',
        'baselines/waveform_early_release_v1/validation.json'])
    print(result,flush=True)


if __name__=='__main__':main()
