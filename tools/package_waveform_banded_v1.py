"""Freeze exact-band known progress, failed precision probes and real provenance."""
import argparse
import shutil
import subprocess
from pathlib import Path
from research_archive_v1 import load,save,sha,freeze,verify,append_index


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True);a=p.parse_args()
    repo=Path(__file__).resolve().parents[1];e=a.workspace/'references/analysis/waveform_banded_v1'
    folders=('controls1','controls_audit1','band_controls_audit1','known1','known_audit1','known_audit2',
        'root_diagnosis1','shared1','shared_audit1','native_context1','native_context_audit1',
        'resources_audit1','normal_diagnosis1','equilibration_probe1','diagnosis_audit1')
    reports={name:load(e/name/'report.json') for name in folders}
    ka,sa=reports['known_audit2'],reports['shared_audit1'];resources=reports['resources_audit1']
    assert ka['pass_count']==12 and ka['all_qualified'] and sa['pass_count']==7 and not sa['all_qualified']
    assert reports['known_audit1']['result']=='failed'
    assert reports['diagnosis_audit1']['equilibration_pass_count']==4
    assert reports['native_context_audit1']['pass_count']==6
    assert reports['root_diagnosis1']['all_original_lower_metrics_bitwise_equal']
    assert not reports['equilibration_probe1']['production_backend_selected']
    paths=set()
    for flags in (['ls-files','-z'],['ls-files','--others','--exclude-standard','-z']):
        paths.update(subprocess.check_output(['git']+flags,cwd=repo).decode('utf-8').split('\0'))
    previous=a.workspace/'baselines/waveform_stream_v1';protected={};sources=set();parents={};inputs={};locations={}
    for name,count in (('C_files_sha256.json',670),('voice_files_sha256.json',82),('F2_files_sha256.json',3)):
        values=load(previous/'evidence'/name);assert len(values)==count and all(sha(repo/n)==h for n,h in values.items())
        protected[name]=values;sources.update(values)
    assert {n for n in paths if Path(n).suffix in ('.c','.h')}==set(protected['C_files_sha256.json'])
    assert sha(repo/'handoff/C文件索引.csv')==sha(previous/'source/handoff/C文件索引.csv')
    hearings=load(repo/'research/waveform_stream_v1_summary.json')['protected_hearings_sha256']
    assert all(sha(repo/n)==h for n,h in hearings.items());sources.update(hearings)
    def parent(name):
        if name not in parents:
            root=a.workspace/'baselines'/name;digest=sha(root/'manifest.json')
            assert digest==load(repo/f'research/{name}_summary.json')['manifest_sha256']
            parents[name]=(root,{r['path']:r['sha256'] for r in load(root/'manifest.json')['files']})
            for f in ('manifest.json','validation.json'):inputs[f'upstream/{name}/{f}']=root/f
        return parents[name]
    parent('waveform_stream_v1')
    def bind(name,digest):
        path=Path(name);assert sha(path)==digest
        if path.is_relative_to(e):
            rel=path.relative_to(e);assert rel.parts[0] in folders;target='evidence/'+rel.as_posix()
        elif path.is_relative_to(repo):
            key='current/'+path.relative_to(repo).as_posix();inputs[key]=path;target='inputs/'+key
        elif path.is_relative_to(a.workspace/'baselines'):
            rel=path.relative_to(a.workspace/'baselines');archive=rel.parts[0];root,mapping=parent(archive)
            leaf=path.relative_to(root).as_posix()
            assert (sha(root/'manifest.json') if leaf=='manifest.json' else mapping[leaf])==digest
            key=f'upstream/{archive}/{leaf}';inputs[key]=path;target='inputs/'+key
        else:
            assert path.is_relative_to(a.workspace)
            key='recorded/'+path.relative_to(a.workspace).as_posix();inputs[key]=path;target='inputs/'+key
        locations[str(path)]=target
    for folder,report in reports.items():
        for name,digest in report.get('inputs',report.get('input_sha256',{})).items():bind(name,digest)
        for name,digest in report.get('sources',{}).items():
            assert sha(e/folder/'exact_sources'/name)==digest;sources.add(name)
    sources.update(n for n in paths if any(t in n for t in ('waveform_banded','waveform_native_context')) and Path(n).suffix in ('.py','.md','.json'))
    sources.update(('tools/audit_waveform_structured_known_v1.py','tools/run_waveform_shared_known_v1.py',
        'tools/run_waveform_structured_controls_v1.py','tools/run_waveform_structured_known_v1.py',
        'tools/waveform_stream_v1/metric_root.py','tools/waveform_stream_v1/solver.py',
        'research/带状提取与真实邻域V1.md','AGENTS.md','README.md','CMakeLists.txt','handoff/C文件索引.csv',
        'handoff/当前代码阅读入口.md','tools/research_archive_v1.py','tools/verify_research_archive_independent_v1.py'))
    stage=e/'package1';stage.mkdir(exist_ok=False)
    for folder in folders:shutil.copytree(e/folder,stage/folder)
    for name,values in protected.items():save(stage/name,values)
    shutil.copy2(__file__,stage/'executed_package.py');inputs['data_AGENTS.md']=a.workspace/'AGENTS.md'
    summary=dict(result='waveform_banded_known_progress_frozen',selected_terminal_evidence_directories=list(folders),
        original_input_archive_locations=locations,upstream_manifests_sha256={n:sha(root/'manifest.json') for n,(root,m) in parents.items()},
        original_controls=dict(arbitrary_R=7,finite_DFT=4,temporal=3),band_map_controls=4,
        band_map_maximum_error=max(reports['band_controls_audit1']['maximum_errors'].values()),
        original12_qualified=12,old_root_Gram_2e_11_failures=resources['old_root_strict_Gram_failures'],
        first_strict_audit_failure_retained=True,shared8_qualified=7,
        shared_original_failures=[c for c in sa['cases'] if not c['qualified']],
        equiv_diagonal_probe_qualified=4,equiv_diagonal_probe_count=5,equiv_diagonal_factory_selected=False,
        all8_original_lower_W_bitwise_equal=True,original_known_peak_before=resources['original_known_cumulative_peak_before'],
        original_known_peak_after=resources['original_known_cumulative_peak_after'],
        working_set_reduction_fraction=resources['observed_working_set_peak_reduction_fraction'],
        real6_provenance_verified=6,outer_corrected_phase_qualified=False,
        current_conditional_resource_cases=resources['conditional_cases'],
        full_or_real_or_native48k_or_C_or_hearing_qualified=False,
        C_H_exact=670,voice_parameters_exact=82,F2_files_exact=3,C_index_exact=True,protected_hearings_sha256=hearings,
        runtime_default_driver_owned_take_room_changed=False,old68CTest_not_repeated=True,downloaded=False,pushed=False,full_goal='active')
    root=a.workspace/'baselines/waveform_banded_v1';result=freeze(root,repo,sources,stage,inputs,summary);verify(root)
    save(repo/'research/waveform_banded_v1_summary.json',dict(summary,**result))
    append_index(repo/'handoff/阶段索引.csv',['waveform_banded_v1','baselines/waveform_banded_v1/manifest.json',
        result['file_count'],result['manifest_sha256'],'original12PASS/shared7of8;strictFAIL/equilibration4of5 retained;native6 proven',
        '670C-H82voice3F2/index exact;no full/source/C/audio promotion',
        'research/带状提取与真实邻域V1.md | research/waveform_banded_v1_summary.json','baselines/waveform_banded_v1/validation.json'])
    print(result,flush=True)


if __name__=='__main__':main()
