"""Freeze both terminal waveform-space attempts and exact original inputs."""
import argparse
import shutil
import subprocess
from pathlib import Path
from research_archive_v1 import load, save, sha, freeze, verify, append_index


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    study = args.workspace/'references/analysis/waveform_representer_v1'
    pub = load(study/'review1/report.json')
    audit = load(study/'publication_audit1/report.json')
    assert audit['result'] == 'independent_waveform_representer_publication_verified'
    assert audit['producer_publication_sha256'] == sha(study/'review1/report.json')
    assert audit['summary'] == pub['summary']
    assert audit['auditor_sha256'] == sha(repo/'tools/audit_waveform_representer_publication_v1.py')
    assert audit['images_individually_viewed_by_agent'] == ['known_controls.png', 'resource_scope.png']
    assert (pub['summary']['before_passes'], pub['summary']['after_passes']) == (4, 9)
    folders = tuple(f'{name}{number}' for number in (1,2) for name in
                    ('explicit','explicit_audit','known','known_audit'))+('review1','publication_audit1')
    parent = args.workspace/'baselines/observer_stable_full_v1'
    parent_summary = load(repo/'research/observer_stable_full_v1_summary.json')
    assert sha(parent/'manifest.json') == parent_summary['manifest_sha256']
    protected, sources = {}, set()
    for name, count in (('C_files_sha256.json',670),('voice_files_sha256.json',82),('F2_files_sha256.json',3)):
        values = load(parent/'evidence'/name)
        assert len(values) == count and all(sha(repo/n) == h for n,h in values.items())
        protected[name] = values
        sources.update(values)
    current = set()
    for flags in (['ls-files','-z'],['ls-files','--others','--exclude-standard','-z']):
        current.update(subprocess.check_output(['git']+flags,cwd=repo).decode('utf-8').split('\0'))
    assert {n for n in current if Path(n).suffix in ('.c','.h')} == set(protected['C_files_sha256.json'])
    original_parent = args.workspace/'baselines/observer_representer_v1'
    manifests = {}
    inputs = {'upstream/observer_stable_full_v1/manifest.json':parent/'manifest.json'}
    for name, base in (('observer_representer_v1',original_parent),):
        expected = load(repo/f'research/{name}_summary.json')['manifest_sha256']
        assert sha(base/'manifest.json') == expected
        manifests[name] = {r['path']:r['sha256'] for r in load(base/'manifest.json')['files']}
        inputs[f'upstream/{name}/manifest.json'] = base/'manifest.json'
        inputs[f'upstream/{name}/validation.json'] = base/'validation.json'
    locations = {}
    def bind(name, expected):
        path = Path(name)
        assert sha(path) == expected
        if path.is_relative_to(study):
            rel = path.relative_to(study)
            assert rel.parts[0] in folders
            target = 'evidence/'+rel.as_posix()
        else:
            assert path.is_relative_to(original_parent)
            rel = path.relative_to(original_parent).as_posix()
            assert manifests['observer_representer_v1'][rel] == expected
            key = 'upstream/observer_representer_v1/'+rel
            inputs[key] = path
            target = 'inputs/'+key
        locations[str(path)] = target
    for number in (1,2):
        for name in ('explicit','known'):
            folder = study/f'{name}{number}'
            report = load(folder/'report.json')
            for key, value in report['sources'].items():
                assert sha(folder/'exact_sources'/key) == value
                sources.add(key)
            for key, value in report.get('inputs',{}).items():
                bind(key,value)
    for key, value in pub['inputs'].items():
        bind(key,value)
    for key in audit['original_input_bindings']:
        assert key in locations
    for filename in ('handoff/C文件索引.csv','research/relative_phase_v1_listening.json'):
        assert sha(repo/filename) == sha(parent/'source'/filename)
        sources.add(filename)
    sources.update(parent_summary['protected_hearings_sha256'])
    for n,h in parent_summary['protected_hearings_sha256'].items():
        assert sha(repo/n) == h
    sources.update(n for n in current if 'waveform_representer' in n and Path(n).suffix in ('.py','.json','.md'))
    sources.update(('research/波形空间声源提取V1.md','AGENTS.md','README.md','CMakeLists.txt',
        'handoff/当前代码阅读入口.md','tools/research_archive_v1.py','tools/verify_research_archive_independent_v1.py'))
    stage = study/'package1'
    stage.mkdir(exist_ok=False)
    for name in folders:
        shutil.copytree(study/name,stage/name)
    for name, values in protected.items():
        save(stage/name,values)
    shutil.copy2(__file__,stage/'executed_package.py')
    inputs['data_AGENTS.md'] = args.workspace/'AGENTS.md'
    validation = dict(result='waveform_representer_v1_frozen', results=pub['summary'],
        original_input_archive_locations=locations,
        upstream_manifests_sha256={n:sha(args.workspace/'baselines'/n/'manifest.json') for n in
                                   ('observer_representer_v1','observer_stable_full_v1')},
        selected_terminal_evidence_directories=list(folders),C_H_exact=670,voice_parameters_exact=82,
        F2_files_exact=3,C_index_exact=True,protected_hearings_sha256=parent_summary['protected_hearings_sha256'],
        explicit_controls_per_version=7,finite_DFT_controls_per_version=4,original_controls_per_version=12,
        plotted_rows_independently_verified=24,scientific_figures_individually_viewed=2,
        all_original_gates_unchanged=True,all_versions_and_three_failures_retained=True,
        full_scale_or_source_or_native48k_or_C_or_hearing_qualified=False,
        runtime_default_driver_owned_take_room_changed=False,previous_13GB_basis_not_copied=True,
        old_68CTest_not_repeated=True,downloaded=False,pushed=False,full_goal='active')
    archive = args.workspace/'baselines/waveform_representer_v1'
    result = freeze(archive,repo,sources,stage,inputs,validation)
    verify(archive)
    save(repo/'research/waveform_representer_v1_summary.json',dict(validation,**result))
    append_index(repo/'handoff/阶段索引.csv',['waveform_representer_v1',
        'baselines/waveform_representer_v1/manifest.json',result['file_count'],result['manifest_sha256'],
        'same12 qualification4->9;3failures retained;no full/source run',
        '670C-H82voice3F2/index exact;no C/audio promotion',
        'research/波形空间声源提取V1.md | research/waveform_representer_v1_summary.json',
        'baselines/waveform_representer_v1/validation.json'])
    print(result,flush=True)


if __name__ == '__main__':
    main()
