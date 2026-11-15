"""Freeze terminal full-file proof, exact executed versions and recorded shapes."""
import argparse
from pathlib import Path
import shutil
import subprocess
from research_archive_v1 import load, save, sha, freeze, append_index


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','full-audit','resources-audit'): p.add_argument('--'+name,type=Path,required=True)
    a = p.parse_args()
    repo = Path(__file__).resolve().parents[1]
    e = a.workspace/'references/analysis/waveform_file_full_v1'
    folders = tuple(sorted(x.name for x in e.iterdir() if x.is_dir() and (x/'report.json').is_file()))
    reports = {n:load(e/n/'report.json') for n in folders}
    full, audited, resources = reports['full1'], reports[a.full_audit.name], reports[a.resources_audit.name]
    assert full['result'] == 'waveform_file_full_known_measured' and full['only_one_attempt']
    assert audited['result'] == 'independent_waveform_file_full_verified' and audited['all_qualified']
    assert audited['producer_sha256'] == sha(e/'full1/report.json')
    assert resources['result'] == 'independent_waveform_file_real_resources_verified' and resources['all_qualified']
    assert reports['panels_audit1']['all_qualified'] and reports['base_guard1']['all_qualified']
    peak = reports['peak_audit1']
    assert peak['result'] == 'independent_waveform_file_measured_lifetimes_verified' and peak['all_qualified']
    assert load(e/'full1/progress.json')['status'] == 'completed'
    paths = set()
    for flags in (['ls-files','-z'],['ls-files','--others','--exclude-standard','-z']):
        paths.update(subprocess.check_output(['git']+flags,cwd=repo).decode('utf-8').split('\0'))
    prior = a.workspace/'baselines/waveform_file_panels_v1'
    protected, sources, versions = {}, set(), {}
    for name,count in (('C_files_sha256.json',670),('voice_files_sha256.json',82),('F2_files_sha256.json',3)):
        values = load(prior/'evidence'/name)
        assert len(values) == count and all(sha(repo/n) == h for n,h in values.items())
        protected[name] = values
        sources.update(values)
    assert {n for n in paths if Path(n).suffix in ('.c','.h')} == set(protected['C_files_sha256.json'])
    assert sha(repo/'handoff/C文件索引.csv') == sha(prior/'source/handoff/C文件索引.csv')
    hearings = load(repo/'research/waveform_file_panels_v1_summary.json')['protected_hearings_sha256']
    assert all(sha(repo/n) == h for n,h in hearings.items())
    sources.update(hearings)
    parents,inputs,locations = {},{},{}
    def parent(name):
        if name not in parents:
            root = a.workspace/'baselines'/name
            digest = sha(root/'manifest.json')
            assert digest == load(repo/f'research/{name}_summary.json')['manifest_sha256']
            parents[name] = root,{x['path']:x['sha256'] for x in load(root/'manifest.json')['files']}
            for leaf in ('manifest.json','validation.json'): inputs[f'upstream/{name}/{leaf}'] = root/leaf
        return parents[name]
    def bind(name,digest):
        path = Path(name)
        assert sha(path) == digest,path
        if path.is_relative_to(e):
            target = 'evidence/'+path.relative_to(e).as_posix()
        elif path.is_relative_to(repo):
            key = 'current/'+path.relative_to(repo).as_posix()
            inputs[key] = path
            target = 'inputs/'+key
        elif path.is_relative_to(a.workspace/'baselines'):
            archive = path.relative_to(a.workspace/'baselines').parts[0]
            root,mapping = parent(archive)
            leaf = path.relative_to(root).as_posix()
            assert digest == (sha(root/'manifest.json') if leaf=='manifest.json' else mapping[leaf])
            key = f'upstream/{archive}/{leaf}'
            inputs[key] = path
            target = 'inputs/'+key
        else:
            assert path.is_relative_to(a.workspace),path
            key = 'external/'+path.relative_to(a.workspace).as_posix()
            inputs[key] = path
            target = 'inputs/'+key
        locations[str(path)] = target
    def factors(v):
        if isinstance(v,dict):
            if {'path','shape','file_bytes','sha256'} <= v.keys(): bind(v['path'],v['sha256'])
            for child in v.values(): factors(child)
        elif isinstance(v,list):
            for child in v: factors(child)
    for folder,r in reports.items():
        for key in ('inputs','input_sha256'):
            for name,digest in r.get(key,{}).items(): bind(name,digest)
        for name,digest in r.get('sources',{}).items():
            assert sha(e/folder/'exact_sources'/name) == digest
            sources.add(name)
            versions.setdefault(name,{})[folder] = digest
        sources.update(r.get('oracles_sha256',{}))
        factors(r)
    sources.update(n for n in paths if n and 'waveform_file' in n and Path(n).suffix in ('.py','.md','.json'))
    sources.discard('research/waveform_file_full_v1_summary.json')
    sources.update(('research/完整文件声纹提取验证V1.md','tools/research_archive_v1.py',
        'tools/verify_research_archive_independent_v1.py','AGENTS.md','README.md','CMakeLists.txt',
        'handoff/C文件索引.csv','handoff/当前代码阅读入口.md','handoff/研究续接.md','handoff/开发留痕.md'))
    sources = {n for n in sources if (repo/n).is_file()}
    for name,values in protected.items(): save(e/name,values)
    shutil.copy2(__file__,e/'executed_package.py')
    inputs['data_AGENTS.md'] = a.workspace/'AGENTS.md'
    metadata = dict(result='waveform_file_full_known_and_recorded_resources_frozen',
        selected_terminal_evidence_directories=list(folders),selected_full_audit=a.full_audit.name,
        selected_resources_audit=a.resources_audit.name,original_input_archive_locations=locations,
        upstream_manifests_sha256={n:sha(root/'manifest.json') for n,(root,m) in parents.items()},
        executed_source_versions=versions,current_source_sha256={n:sha(repo/n) for n in sources},
        protected_hearings_sha256=hearings,full_known_independently_qualified=True,
        full_metrics=audited['metrics'],full_gradient=audited['gradient'],
        full_stable_complete_normal=audited['stable_original_complete_normal'],
        full_backward=audited['original_backward'],full_comparison_rows=audited['comparison_rows'],
        full_resource_audit=audited['file_resource_audit'],all12_conditional_resources=resources['cases'],
        measured_lifetime_budget_comparison=peak['measured_comparison'],
        all12_conditional_preflights_passed=resources['all12_conditional_preflights_passed'],
        actual_process_memory=full['process_memory'],solve_wall_seconds_PC_only=full['solve_wall_seconds'],
        C_H_exact=670,voice_parameters_exact=82,F2_files_exact=3,C_index_exact=True,
        real_inverse_fit_executed=False,no_C_or_timbre_promotion=True,
        runtime_default_driver_owned_take_room_changed=False,downloaded=False,pushed=False,
        old68CTest_not_repeated=True,full_goal='active',next='research/waveform_file_real_next_v1_plan.json')
    root = a.workspace/'baselines/waveform_file_full_v1'
    result = freeze(root,repo,sources,e,inputs,metadata)
    save(repo/'research/waveform_file_full_v1_summary.json',dict(metadata,**result))
    append_index(repo/'handoff/阶段索引.csv',['waveform_file_full_v1','baselines/waveform_file_full_v1/manifest.json',
        result['file_count'],result['manifest_sha256'],'block1024/full12289/49/288 independentLR all original gates PASS',
        '670C-H82voice3F2/index exact;actual full panels/lifetimes;real resource arithmetic only',
        'research/完整文件声纹提取验证V1.md | research/waveform_file_full_v1_summary.json',
        'baselines/waveform_file_full_v1/validation.json'])
    print(result,flush=True)


if __name__ == '__main__': main()
