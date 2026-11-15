"""Freeze native correction, true phase lifetimes and full-known validation."""
import argparse
import shutil
import subprocess
from pathlib import Path
from research_archive_v1 import load,save,sha,freeze,verify,append_index


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True);a=p.parse_args()
    repo=Path(__file__).resolve().parents[1];e=a.workspace/'references/analysis/waveform_correction_storage_v1'
    folders=('controls1','controls_audit1','known1','known_audit1','shared1','shared_audit1',
        'pipeline_known1','pipeline_known_audit1','pipeline_shared1','pipeline_shared_audit1',
        'storage_audit1','storage_audit2','full1','full_audit1','real_resources1')
    reports={n:load(e/n/'report.json') for n in folders}
    assert reports['controls_audit1']['all_qualified']
    for n,count in (('known_audit1',12),('shared_audit1',8),('pipeline_known_audit1',12),('pipeline_shared_audit1',8)):
        assert reports[n]['all_qualified'] and reports[n]['pass_count']==count
    assert reports['storage_audit1']['result']=='failed' and 'pipeline' in reports['storage_audit1']['error']
    resource=reports['storage_audit2'];full=reports['full1'];audit=reports['full_audit1']
    assert resource['result']=='independent_waveform_correction_storage_verified' and len(resource['cases'])==40
    assert audit['result']=='independent_waveform_correction_native_full_verified'
    assert audit['solver_qualified'] and audit['fidelity_qualified'] and audit['all_phase_releases_verified']
    assert audit['producer_sha256']==sha(e/'full1/report.json')
    paths=set()
    for flags in (['ls-files','-z'],['ls-files','--others','--exclude-standard','-z']):
        paths.update(subprocess.check_output(['git']+flags,cwd=repo).decode('utf-8').split('\0'))
    previous=a.workspace/'baselines/waveform_original_correction_v1'
    protected={};sources=set();parents={};inputs={};locations={}
    for name,count in (('C_files_sha256.json',670),('voice_files_sha256.json',82),('F2_files_sha256.json',3)):
        values=load(previous/'evidence'/name);assert len(values)==count and all(sha(repo/n)==h for n,h in values.items())
        protected[name]=values;sources.update(values)
    assert {n for n in paths if Path(n).suffix in ('.c','.h')}==set(protected['C_files_sha256.json'])
    assert sha(repo/'handoff/C文件索引.csv')==sha(previous/'source/handoff/C文件索引.csv')
    hearings=load(repo/'research/waveform_original_correction_v1_summary.json')['protected_hearings_sha256']
    assert all(sha(repo/n)==h for n,h in hearings.items());sources.update(hearings)
    def parent(name):
        if name not in parents:
            root=a.workspace/'baselines'/name
            assert sha(root/'manifest.json')==load(repo/f'research/{name}_summary.json')['manifest_sha256']
            parents[name]=(root,{r['path']:r['sha256'] for r in load(root/'manifest.json')['files']})
            for leaf in ('manifest.json','validation.json'):inputs[f'upstream/{name}/{leaf}']=root/leaf
        return parents[name]
    parent('waveform_original_correction_v1');parent('waveform_stream_full_v1')
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
        for name,digest in report.get('inputs',{}).items():bind(name,digest)
        for name,digest in report.get('sources',{}).items():
            assert sha(e/folder/'exact_sources'/name)==digest;sources.add(name)
    sources.update(n for n in paths if 'waveform_correction' in n and Path(n).suffix in ('.py','.md','.json'))
    sources.update(('research/原生修正与完整存活验证V1.md','research/waveform_correction_real_next_v1_plan.json',
        'tools/verify_waveform_correction_storage_bindings_v1.py','AGENTS.md','README.md','CMakeLists.txt',
        'handoff/C文件索引.csv','handoff/当前代码阅读入口.md','handoff/研究续接.md',
        'tools/research_archive_v1.py','tools/verify_research_archive_independent_v1.py'))
    sources={n for n in sources if n and (repo/n).is_file()}
    stage=e/'package1';stage.mkdir(exist_ok=False)
    for folder in folders:shutil.copytree(e/folder,stage/folder)
    for name,values in protected.items():save(stage/name,values)
    shutil.copy2(__file__,stage/'executed_package.py');inputs['data_AGENTS.md']=a.workspace/'AGENTS.md'
    summary=dict(result='waveform_correction_storage_and_full_known_frozen',
        selected_terminal_evidence_directories=list(folders),original_input_archive_locations=locations,
        upstream_manifests_sha256={n:sha(root/'manifest.json') for n,(root,mapping) in parents.items()},
        inverse_controls=8,arbitrary_controls=7,native_original12=12,native_shared8=8,
        rebuilt_pipeline_original12=12,rebuilt_pipeline_shared8=8,known_exact_array_case_count=40,
        production_trace_known_controls=13,metadata_failed_first_audit_retained=True,
        full_solver_qualified=True,full_fidelity_qualified=True,full_corrected_normal=audit['stable_original_complete_normal'],
        full_gradient=audit['gradient'],full_backward=audit['original_backward'],
        full_metrics=audit['metrics'],full_comparison_rows=audit['comparison_rows'],
        full_correction_history=audit['original_correction_history'],
        full_actual_phase_releases_verified=True,full_production_trace_relative_error=audit['production_original_trace_relative_error'],
        full_actual_working_set_peak=full['process_memory']['cumulative_peak_working_set_bytes'],
        full_actual_private_commit_peak=full['process_memory']['cumulative_peak_private_commit_bytes'],
        full_registered_backing_peak=full['resources']['max_tracked_live_backing_bytes'],
        full_base_four_array_bytes=8368514064,full_correction_no_T_array_bytes=7965828112,
        full_elapsed_host_seconds=full['solve_wall_seconds'],native_target_default_selected=False,
        real_conditional_resource_cases=reports['real_resources1']['cases'],
        no_real6_or_native48k_or_C_or_hearing_qualification=True,outer_corrected_phase_qualified=False,
        C_H_exact=670,voice_parameters_exact=82,F2_files_exact=3,C_index_exact=True,
        protected_hearings_sha256=hearings,runtime_default_driver_owned_take_room_changed=False,
        old68CTest_not_repeated=True,downloaded=False,pushed=False,full_goal='active',
        previous_goal_turn='Progress: original FFT correction independently qualified12+8 and native triangular probes, archive59a3bd4')
    root=a.workspace/'baselines/waveform_correction_storage_v1';result=freeze(root,repo,sources,stage,inputs,summary);verify(root)
    save(repo/'research/waveform_correction_storage_v1_summary.json',dict(summary,**result))
    append_index(repo/'handoff/阶段索引.csv',['waveform_correction_storage_v1','baselines/waveform_correction_storage_v1/manifest.json',
        result['file_count'],result['manifest_sha256'],'native12+8/pipeline12+8/full known original solver+fidelity independentlyPASS',
        '670C-H82voice3F2/index exact;no real-source/C/audio promotion',
        'research/原生修正与完整存活验证V1.md | research/waveform_correction_storage_v1_summary.json',
        'baselines/waveform_correction_storage_v1/validation.json'])
    print(result,flush=True)


if __name__=='__main__':main()
