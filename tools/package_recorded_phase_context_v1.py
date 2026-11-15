"""Freeze genuine source context, independent audits and every failed version."""
import argparse
import shutil
import subprocess
from pathlib import Path
from research_archive_v1 import load,save,sha,freeze,verify,append_index


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True);a=p.parse_args()
    repo=Path(__file__).resolve().parents[1];e=a.workspace/'references/analysis/recorded_phase_context_v1'
    folders=('known1','known_audit1','known_audit2','real1','real_audit1')
    reports={name:load(e/name/'report.json') for name in folders}
    assert reports['known1']['all_qualified'] and reports['known_audit2']['all_qualified']
    assert reports['known_audit2']['pass_count']==8 and len(reports['known1']['rejections'])==7
    assert reports['real1']['all_qualified'] and reports['real_audit1']['all_qualified']
    assert reports['real_audit1']['pass_count']==6
    assert reports['known_audit1']['result']=='failed' and 'coarse_audio' in reports['known_audit1']['error']
    for producer,auditor in (('known1','known_audit2'),('real1','real_audit1')):
        assert reports[auditor]['producer_sha256']==sha(e/producer/'report.json')
    paths=set()
    for flags in (['ls-files','-z'],['ls-files','--others','--exclude-standard','-z']):
        paths.update(subprocess.check_output(['git']+flags,cwd=repo).decode('utf-8').split('\0'))
    parent_root=a.workspace/'baselines/waveform_correction_storage_v1'
    sources=set();protected={}
    for name,count in (('C_files_sha256.json',670),('voice_files_sha256.json',82),('F2_files_sha256.json',3)):
        values=load(parent_root/'evidence'/name);assert len(values)==count
        assert all(sha(repo/n)==h for n,h in values.items());protected[name]=values;sources.update(values)
    assert {n for n in paths if Path(n).suffix in ('.c','.h')}==set(protected['C_files_sha256.json'])
    assert sha(repo/'handoff/C文件索引.csv')==sha(parent_root/'source/handoff/C文件索引.csv')
    hearings=load(repo/'research/waveform_correction_storage_v1_summary.json')['protected_hearings_sha256']
    assert all(sha(repo/n)==h for n,h in hearings.items());sources.update(hearings)
    parents={};inputs={};locations={}
    def parent(name):
        if name not in parents:
            root=a.workspace/'baselines'/name
            assert sha(root/'manifest.json')==load(repo/f'research/{name}_summary.json')['manifest_sha256']
            parents[name]=(root,{r['path']:r['sha256'] for r in load(root/'manifest.json')['files']})
            for leaf in ('manifest.json','validation.json'):inputs[f'upstream/{name}/{leaf}']=root/leaf
        return parents[name]
    parent('waveform_correction_storage_v1')
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
        elif path.is_relative_to(a.workspace/'references'):
            key='local/'+path.relative_to(a.workspace).as_posix();inputs[key]=path;target='inputs/'+key
        else:raise AssertionError(('Unexpected input',path))
        locations[str(path)]=target
    for folder,report in reports.items():
        for name,digest in report.get('inputs',{}).items():bind(name,digest)
        for name,digest in report.get('sources',{}).items():
            assert sha(e/folder/'exact_sources'/name)==digest;sources.add(name)
    sources.update(n for n in paths if 'recorded_phase_context' in n and Path(n).suffix in ('.py','.md','.json'))
    sources.discard('research/recorded_phase_context_v1_summary.json')
    sources.update(('research/真实前后文相位V1.md','tools/research_archive_v1.py',
        'tools/verify_research_archive_independent_v1.py','tools/verify_recorded_phase_context_bindings_v1.py',
        'AGENTS.md','README.md','CMakeLists.txt','handoff/C文件索引.csv','handoff/当前代码阅读入口.md','handoff/研究续接.md'))
    sources={n for n in sources if n and (repo/n).is_file()}
    stage=e/'package1';stage.mkdir(exist_ok=False)
    for folder in folders:shutil.copytree(e/folder,stage/folder)
    for name,values in protected.items():save(stage/name,values)
    shutil.copy2(__file__,stage/'executed_package.py');inputs['data_AGENTS.md']=a.workspace/'AGENTS.md'
    comparison=[]
    for case in reports['real1']['cases']:
        for order,regions in case['heldout'].items():
            for region,values in regions.items():
                for channel in (0,1):
                    before=case['original_heldout'][order][channel];after=values['coherence'][channel]
                    comparison.append(dict(label=case['label'],heldout_order=int(order),channel=channel,
                        region=region,original_target_coherence=before,context_region_coherence=after,
                        signed_change=after-before,regression=after<before))
    assert len(comparison)==96
    summary=dict(result='recorded_phase_context_known_and_six_real_frozen',
        selected_terminal_evidence_directories=list(folders),original_input_archive_locations=locations,
        upstream_manifests_sha256={n:sha(root/'manifest.json') for n,(root,mapping) in parents.items()},
        known_positive_count=8,known_rejections=7,known_cases=reports['known_audit2']['cases'],
        known_phase_cycle_std_max=max(c['known_cycle_std'] for c in reports['known_audit2']['cases']),
        known_wave_NRMSE_max=max(c['analytic_wave_NRMSE'] for c in reports['known_audit2']['cases']),
        first_auditor_cutoff_failure_retained=True,real_cases=reports['real_audit1']['cases'],
        real_count=6,real_minimum_heldout_coherence=min(c['minimum_heldout_coherence'] for c in reports['real_audit1']['cases']),
        original_heldout_gate=.8,all96_signed_comparison_rows=comparison,
        real_direct_render_max_error_FS=max(c['direct_FIR_and_polyphase_render_max_error_FS'] for c in reports['real_audit1']['cases']),
        original_audio_coordinates_and_scales_bitwise_exact=True,real_two_cycle_each_side_context_qualified=True,
        global_clock_or_physical_RPM_or_load_or_AM_PM_identification=False,
        no_large_real_inverse_or_new_sustained_sound_or_C_or_hearing_qualification=True,
        memory_preflight_still_required=True,C_H_exact=670,voice_parameters_exact=82,F2_files_exact=3,C_index_exact=True,
        protected_hearings_sha256=hearings,runtime_default_driver_owned_take_room_changed=False,
        downloaded=False,pushed=False,unchanged68CTest_not_repeated=True,full_goal='active',
        previous_goal_turn='No synthesis progress: MCPS-only recheck; this stage creates independently qualified actual six source contexts')
    root=a.workspace/'baselines/recorded_phase_context_v1';result=freeze(root,repo,sources,stage,inputs,summary);verify(root)
    save(repo/'research/recorded_phase_context_v1_summary.json',dict(summary,**result))
    append_index(repo/'handoff/阶段索引.csv',['recorded_phase_context_v1','baselines/recorded_phase_context_v1/manifest.json',
        result['file_count'],result['manifest_sha256'],'known8+explicit rejects;SAMEsix genuine contexts independentlyPASS;96signed rows',
        '670C-H82voice3F2/index exact;no inverse/source/C/hearing promotion',
        'research/真实前后文相位V1.md | research/recorded_phase_context_v1_summary.json',
        'baselines/recorded_phase_context_v1/validation.json'])
    print(result,flush=True)


if __name__=='__main__':main()
