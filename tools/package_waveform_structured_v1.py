"""Freeze exact structured controls, original12, failed audit and resource evidence."""
import argparse
import shutil
import subprocess
from pathlib import Path
from research_archive_v1 import load,save,sha,freeze,verify,append_index


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True);a=p.parse_args()
    repo=Path(__file__).resolve().parents[1];e=a.workspace/'references/analysis/waveform_structured_v1'
    full=load(e/'known1/report.json');independent=load(e/'known_audit2/report.json');resources=load(e/'resources_audit1/report.json')
    assert full['result']=='waveform_structured_original12_measured' and full['all_qualified']
    assert independent['result']=='independent_waveform_structured_original12_verified' and independent['pass_count']==12
    assert independent['producer_sha256']==sha(e/'known1/report.json')
    assert resources['result']=='independent_waveform_structured_resources_verified'
    assert resources['current_cumulative_peak_bytes']==962129920
    assert len(resources['stricter_whitened_diagnostic_failures'])==8
    failed=load(e/'known_audit1/report.json')
    assert failed['result']=='failed' and 'all_original_quadratic_terms' in failed['error']
    folders=('controls1','controls_audit1','known1','known_audit1','known_audit2','resources_audit1')
    parents={};inputs={}
    for n in ('observer_representer_v1','waveform_graph_v1'):
        b=a.workspace/'baselines'/n;summary=load(repo/f'research/{n}_summary.json')
        assert sha(b/'manifest.json')==summary['manifest_sha256']
        parents[n]=(b,{r['path']:r['sha256'] for r in load(b/'manifest.json')['files']})
        for f in ('manifest.json','validation.json'):inputs[f'upstream/{n}/{f}']=b/f
    parent,_=parents['waveform_graph_v1'];protected={};sources=set()
    for n,count in (('C_files_sha256.json',670),('voice_files_sha256.json',82),('F2_files_sha256.json',3)):
        values=load(parent/'evidence'/n);assert len(values)==count
        assert all(sha(repo/k)==h for k,h in values.items());protected[n]=values;sources.update(values)
    paths=set()
    for flags in (['ls-files','-z'],['ls-files','--others','--exclude-standard','-z']):
        paths.update(subprocess.check_output(['git']+flags,cwd=repo).decode('utf-8').split('\0'))
    assert {n for n in paths if Path(n).suffix in ('.c','.h')}==set(protected['C_files_sha256.json'])
    assert sha(repo/'handoff/C文件索引.csv')==sha(parent/'source/handoff/C文件索引.csv')
    hearings=load(repo/'research/waveform_graph_v1_summary.json')['protected_hearings_sha256']
    assert all(sha(repo/n)==h for n,h in hearings.items());sources.update(hearings)
    locations={}
    def bind(n,h):
        p=Path(n);assert sha(p)==h
        if p.is_relative_to(e):
            rel=p.relative_to(e);assert rel.parts[0] in folders
            target='evidence/'+rel.as_posix()
        else:
            candidates=[(n,b,m) for n,(b,m) in parents.items() if p.is_relative_to(b)]
            assert len(candidates)==1,str(p);name,b,m=candidates[0];rel=p.relative_to(b).as_posix()
            assert m[rel]==h;key=f'upstream/{name}/{rel}';inputs[key]=p;target='inputs/'+key
        locations[str(p)]=target
    for folder in folders:
        r=load(e/folder/'report.json')
        for n,h in r.get('inputs',{}).items():bind(n,h)
        for n,h in r.get('sources',{}).items():
            assert sha(e/folder/'exact_sources'/n)==h;sources.add(n)
    sources.update(n for n in paths if 'waveform_structured' in n and Path(n).suffix in ('.py','.json','.md'))
    sources.update(('research/结构化波形求解与内存V1.md','research/waveform_graph_structured_v1_plan.json',
        'AGENTS.md','README.md','CMakeLists.txt','handoff/C文件索引.csv','handoff/当前代码阅读入口.md',
        'tools/research_archive_v1.py','tools/verify_research_archive_independent_v1.py'))
    stage=e/'package1';stage.mkdir(exist_ok=False)
    for f in folders:shutil.copytree(e/f,stage/f)
    for n,values in protected.items():save(stage/n,values)
    shutil.copy2(__file__,stage/'executed_package.py');inputs['data_AGENTS.md']=a.workspace/'AGENTS.md'
    summary=dict(result='waveform_structured_v1_frozen',selected_terminal_evidence_directories=list(folders),
        original_input_archive_locations=locations,upstream_manifests_sha256={n:sha(b/'manifest.json') for n,(b,m) in parents.items()},
        original12_qualified=12,original12_direct_normal_passed=sum(c['original_direct_normal_relative']<=1e-11 for c in independent['cases']),
        controls=dict(original_arbitrary_R=7,finite_DFT=4,temporal_root=3),
        C_H_exact=670,voice_parameters_exact=82,F2_files_exact=3,C_index_exact=True,protected_hearings_sha256=hearings,
        previous_cumulative_process_peak_bytes=resources['previous_cumulative_peak_bytes'],
        current_cumulative_process_peak_bytes=resources['current_cumulative_peak_bytes'],
        cumulative_peak_reduction_fraction=resources['cumulative_peak_reduction_fraction'],
        stricter_whitened_2e_11_diagnostic_failures=resources['stricter_whitened_diagnostic_failures'],
        original_unwhitened_equation_audit_gate=2e-8,all_original_solver_gradient_and_gap_gates_unchanged=True,
        failed_extra_audit_and_executed_versions_preserved=True,full_conditional_arrays=resources['full_conditional_arrays'],
        full_feasibility_proven=False,source_or_full_or_native48k_or_C_or_hearing_qualified=False,
        runtime_default_driver_owned_take_room_changed=False,old_68CTest_not_repeated=True,
        downloaded=False,pushed=False,full_goal='active')
    root=a.workspace/'baselines/waveform_structured_v1';result=freeze(root,repo,sources,stage,inputs,summary);verify(root)
    save(repo/'research/waveform_structured_v1_summary.json',dict(summary,**result))
    append_index(repo/'handoff/阶段索引.csv',['waveform_structured_v1','baselines/waveform_structured_v1/manifest.json',
        result['file_count'],result['manifest_sha256'],'same12PASS;peak1.929->.962GB;extra8white diagnostics retained',
        '670C-H82voice3F2/index exact;no full/source/C/audio promotion',
        'research/结构化波形求解与内存V1.md | research/waveform_structured_v1_summary.json',
        'baselines/waveform_structured_v1/validation.json'])
    print(result,flush=True)


if __name__=='__main__':main()
