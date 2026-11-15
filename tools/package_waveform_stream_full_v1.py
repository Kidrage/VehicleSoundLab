"""Freeze actual full known qualification, trace proof and six-source resource inventory."""
import argparse
import shutil
import subprocess
from pathlib import Path
from research_archive_v1 import load, save, sha, freeze, verify, append_index


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True);a=p.parse_args()
    repo=Path(__file__).resolve().parents[1];e=a.workspace/'references/analysis/waveform_stream_full_v1'
    full=load(e/'full1/report.json');audit=load(e/'full_audit1/report.json');trace=load(e/'trace_controls1/report.json')
    inventory=load(e/'real_inventory1/report.json');pub=load(e/'publication1/report.json')
    assert full['solver_qualified'] and audit['solver_qualified'] and audit['fidelity_qualified']
    assert audit['producer_sha256']==sha(e/'full1/report.json') and trace['all_qualified'] and len(trace['cases'])==13
    assert len(inventory['cases'])==6 and not inventory['real6_fit_or_new_context_or_independent_phase_qualified']
    assert len(pub['rows'])==17
    folders=('full1','full_audit1','trace_controls1','real_inventory1','publication1','package_attempt1')
    parents={};inputs={};locations={};sources=set()
    for name in ('observer_representer_v1','observer_stable_full_v1','waveform_stream_v1','observer_frequency_v1'):
        root=a.workspace/'baselines'/name;summary=load(repo/f'research/{name}_summary.json')
        assert sha(root/'manifest.json')==summary['manifest_sha256']
        parents[name]=(root,{r['path']:r['sha256'] for r in load(root/'manifest.json')['files']})
        for f in ('manifest.json','validation.json'):inputs[f'upstream/{name}/{f}']=root/f
    previous,_=parents['waveform_stream_v1'];protected={}
    for name,count in (('C_files_sha256.json',670),('voice_files_sha256.json',82),('F2_files_sha256.json',3)):
        values=load(previous/'evidence'/name);assert len(values)==count
        assert all(sha(repo/n)==h for n,h in values.items());protected[name]=values;sources.update(values)
    paths=set()
    for flags in (['ls-files','-z'],['ls-files','--others','--exclude-standard','-z']):
        paths.update(subprocess.check_output(['git']+flags,cwd=repo).decode('utf-8').split('\0'))
    assert {n for n in paths if Path(n).suffix in ('.c','.h')}==set(protected['C_files_sha256.json'])
    assert sha(repo/'handoff/C文件索引.csv')==sha(previous/'source/handoff/C文件索引.csv')
    hearings=load(repo/'research/waveform_stream_v1_summary.json')['protected_hearings_sha256']
    assert all(sha(repo/n)==h for n,h in hearings.items());sources.update(hearings)
    def bind(name,h):
        path=Path(name);assert sha(path)==h
        if path.is_relative_to(e):
            rel=path.relative_to(e);assert rel.parts[0] in folders;target='evidence/'+rel.as_posix()
        elif path.is_relative_to(repo):
            key='current/'+path.relative_to(repo).as_posix();inputs[key]=path;target='inputs/'+key
        else:
            candidates=[(n,b,m) for n,(b,m) in parents.items() if path.is_relative_to(b)]
            assert len(candidates)==1,str(path);n,b,m=candidates[0];rel=path.relative_to(b).as_posix()
            if rel=='manifest.json':assert sha(b/'manifest.json')==h
            else:assert m[rel]==h
            key=f'upstream/{n}/{rel}';inputs[key]=path;target='inputs/'+key
        locations[str(path)]=target
    for folder in folders:
        report=load(e/folder/'report.json')
        for name,h in report.get('inputs',{}).items():bind(name,h)
        for name,h in report.get('sources',{}).items():
            assert sha(e/folder/'exact_sources'/name)==h;sources.add(name)
    sources.update(n for n in paths if any(s in n for s in ('waveform_stream_full','waveform_trace','waveform_real_context')) and Path(n).suffix in ('.py','.md','.json'))
    sources.update(('research/完整双声道提取验证V1.md','AGENTS.md','README.md','CMakeLists.txt','handoff/C文件索引.csv',
        'handoff/当前代码阅读入口.md','tools/research_archive_v1.py','tools/verify_research_archive_independent_v1.py'))
    stage=e/'package1';stage.mkdir(exist_ok=False)
    for folder in folders:shutil.copytree(e/folder,stage/folder)
    for name,value in protected.items():save(stage/name,value)
    shutil.copy2(__file__,stage/'executed_package.py');inputs['data_AGENTS.md']=a.workspace/'AGENTS.md'
    summary=dict(result='waveform_stream_full_known_v1_frozen',selected_terminal_evidence_directories=list(folders),
        original_input_archive_locations=locations,upstream_manifests_sha256={n:sha(b/'manifest.json') for n,(b,m) in parents.items()},
        full_known_solver_qualified=True,full_known_fidelity_qualified=True,frames=12289,nodes=49,orders=288,independent_RHS=2,
        original_gradient=audit['gradient'],stable_original_complete_normal=audit['stable_original_complete_normal'],
        original_backward=audit['original_backward'],residual_gap=audit['residual_certificate']['gap_upper_bound'],
        representer_gap=audit['representer_certificate']['gap_upper_bound'],metrics=audit['metrics'],
        all17_comparison_rows=pub['rows'],all_regressions=pub['regressions'],independent_full_trace=audit['independent_all_bin_trace'],
        trace_control_count=13,trace_control_max_error=trace['maximum_relative_error'],extra_full_trace2e_11_passed=audit['extra_trace2e_11_passed'],
        solve_host_seconds=full['solve_wall_seconds'],actual_working_set_peak=pub['actual_working_set_peak'],
        actual_private_commit_peak=pub['actual_private_commit_peak'],registered_live_backing_peak=pub['registered_live_backing_peak'],
        actual_four_main_arrays=9173984280,real6_inventory_count=6,real6_fit_or_context_qualified=False,
        real6_original_current_headroom=inventory['original_targets_fit_headroom_now'],real6_extended_current_headroom=inventory['extended_targets_fit_headroom_now'],
        C_H_exact=670,voice_parameters_exact=82,F2_files_exact=3,C_index_exact=True,protected_hearings_sha256=hearings,
        source_or_native48k_or_C_or_hearing_qualified=False,runtime_default_driver_owned_take_room_changed=False,
        old68CTest_not_repeated=True,downloaded=False,pushed=False,full_goal='active')
    root=a.workspace/'baselines/waveform_stream_full_v1';result=freeze(root,repo,sources,stage,inputs,summary);verify(root)
    save(repo/'research/waveform_stream_full_v1_summary.json',dict(summary,**result))
    append_index(repo/'handoff/阶段索引.csv',['waveform_stream_full_v1','baselines/waveform_stream_full_v1/manifest.json',
        result['file_count'],result['manifest_sha256'],'full288 SAMEknown solver+fidelity independentlyPASS;13trace;all17/regressions',
        '670C-H82voice3F2/index exact;real6 context/resources notqualified;no audio/C promotion',
        'research/完整双声道提取验证V1.md | research/waveform_stream_full_v1_summary.json','baselines/waveform_stream_full_v1/validation.json'])
    print(result,flush=True)


if __name__=='__main__':main()
