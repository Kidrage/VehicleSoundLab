"""Freeze known-only direct QR, independent L/R proofs and all failed diagnostics."""
import argparse
import shutil
import subprocess
from pathlib import Path
from research_archive_v1 import load, save, sha, freeze, verify, append_index


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True);a=p.parse_args()
    repo=Path(__file__).resolve().parents[1];e=a.workspace/'references/analysis/waveform_stream_v1'
    known=load(e/'known_audit1/report.json');shared=load(e/'shared_audit2/report.json');resources=load(e/'resources_audit2/report.json')
    assert known['all_qualified'] and known['pass_count']==12 and shared['all_qualified'] and shared['pass_count']==8
    assert resources['result']=='independent_waveform_stream_resources_verified'
    assert load(e/'shared_audit1/report.json')['result']=='failed'
    folders=('controls1','controls_audit1','controls_shared1','controls_shared_audit1','known1',
             'known_audit1','shared1','shared_audit1','shared_audit2','resources_audit1','resources_audit2')
    parents={};inputs={};locations={};sources=set()
    for name in ('observer_representer_v1','waveform_graph_v1','waveform_structured_v1'):
        root=a.workspace/'baselines'/name;summary=load(repo/f'research/{name}_summary.json')
        assert sha(root/'manifest.json')==summary['manifest_sha256']
        parents[name]=(root,{r['path']:r['sha256'] for r in load(root/'manifest.json')['files']})
        for f in ('manifest.json','validation.json'):inputs[f'upstream/{name}/{f}']=root/f
    previous,_=parents['waveform_structured_v1'];protected={}
    for name,count in (('C_files_sha256.json',670),('voice_files_sha256.json',82),('F2_files_sha256.json',3)):
        values=load(previous/'evidence'/name);assert len(values)==count
        assert all(sha(repo/n)==h for n,h in values.items());protected[name]=values;sources.update(values)
    paths=set()
    for flags in (['ls-files','-z'],['ls-files','--others','--exclude-standard','-z']):
        paths.update(subprocess.check_output(['git']+flags,cwd=repo).decode('utf-8').split('\0'))
    assert {n for n in paths if Path(n).suffix in ('.c','.h')}==set(protected['C_files_sha256.json'])
    assert sha(repo/'handoff/C文件索引.csv')==sha(previous/'source/handoff/C文件索引.csv')
    hearings=load(repo/'research/waveform_structured_v1_summary.json')['protected_hearings_sha256']
    assert all(sha(repo/n)==h for n,h in hearings.items());sources.update(hearings)
    def bind(name,h):
        path=Path(name);assert sha(path)==h
        if path.is_relative_to(e):
            rel=path.relative_to(e);assert rel.parts[0] in folders
            target='evidence/'+rel.as_posix()
        else:
            candidates=[(n,b,m) for n,(b,m) in parents.items() if path.is_relative_to(b)]
            assert len(candidates)==1,str(path);n,b,m=candidates[0];rel=path.relative_to(b).as_posix()
            assert m[rel]==h;key=f'upstream/{n}/{rel}';inputs[key]=path;target='inputs/'+key
        locations[str(path)]=target
    for folder in folders:
        report=load(e/folder/'report.json')
        for name,h in report.get('inputs',{}).items():bind(name,h)
        for name,h in report.get('sources',{}).items():
            assert sha(e/folder/'exact_sources'/name)==h;sources.add(name)
    sources.update(n for n in paths if ('waveform_stream' in n or 'waveform_shared' in n) and Path(n).suffix in ('.py','.md','.json'))
    sources.update(('research/共享算子与原生QRV1.md','research/waveform_structured_stream_v1_plan.json',
        'AGENTS.md','README.md','CMakeLists.txt','handoff/C文件索引.csv','handoff/当前代码阅读入口.md',
        'tools/research_archive_v1.py','tools/verify_research_archive_independent_v1.py'))
    stage=e/'package1';stage.mkdir(exist_ok=False)
    for folder in folders:shutil.copytree(e/folder,stage/folder)
    for name,value in protected.items():save(stage/name,value)
    shutil.copy2(__file__,stage/'executed_package.py');inputs['data_AGENTS.md']=a.workspace/'AGENTS.md'
    diag=[c for c in shared['cases'] if not c['supplemental_original_oracle_Frobenius_2e_11_passed']]
    summary=dict(result='waveform_stream_known_v1_frozen',selected_terminal_evidence_directories=list(folders),
        original_input_archive_locations=locations,upstream_manifests_sha256={n:sha(b/'manifest.json') for n,(b,m) in parents.items()},
        original12_qualified=12,original12_direct_normal_passed=sum(c['original_direct_normal_relative']<=1e-11 for c in known['cases']),
        shared_interleaved_known_qualified=8,mismatched_operator_rejections=7,
        original_and_shared_RHS_controls=dict(arbitrary_R=7,finite_DFT=4,temporal=3),
        strict_white_failures_retained=resources['strict_white_diagnostic_failures_retained'],
        failed_extra_shared_Frobenius_audit_retained=True,extra_Frobenius_diagnostic_failures=[c['label'] for c in diag],
        current_original12_cumulative_peak_bytes=resources['original12_cumulative_process_peak_bytes'],
        previous_original12_cumulative_peak_bytes=resources['previous_original12_cumulative_peak_bytes'],
        shared8_separate_process_peak_bytes=resources['shared8_separate_process_peak_bytes'],
        full_shared_two_RHS_conditional_arrays=resources['full_shared_two_RHS_conditional_arrays'],
        C_H_exact=670,voice_parameters_exact=82,F2_files_exact=3,C_index_exact=True,protected_hearings_sha256=hearings,
        full_or_real_or_native48k_or_C_or_hearing_qualified=False,full_feasibility_proven=False,
        runtime_default_driver_owned_take_room_changed=False,old68CTest_not_repeated=True,downloaded=False,pushed=False,full_goal='active')
    root=a.workspace/'baselines/waveform_stream_v1';result=freeze(root,repo,sources,stage,inputs,summary);verify(root)
    save(repo/'research/waveform_stream_v1_summary.json',dict(summary,**result))
    append_index(repo/'handoff/阶段索引.csv',['waveform_stream_v1','baselines/waveform_stream_v1/manifest.json',
        result['file_count'],result['manifest_sha256'],'original12+shared8PASS;directGEQRF;strict diagnostics retained',
        '670C-H82voice3F2/index exact;no full/source/C/audio promotion',
        'research/共享算子与原生QRV1.md | research/waveform_stream_v1_summary.json','baselines/waveform_stream_v1/validation.json'])
    print(result,flush=True)


if __name__=='__main__':main()
