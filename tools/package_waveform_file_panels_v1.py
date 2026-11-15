"""Freeze all file-panel versions, original known gates, I/O and provenance."""
import argparse
from pathlib import Path
import shutil
import subprocess
from research_archive_v1 import load, save, sha, freeze, verify, append_index


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', type=Path, required=True)
    a = p.parse_args()
    repo = Path(__file__).resolve().parents[1]
    e = a.workspace/'references/analysis/waveform_file_panels_v1'
    folders = ('controls1', 'controls_audit1', 'controls2', 'controls_audit2', 'panels_audit1',
        'controls3', 'controls_audit3', 'panels_audit2', 'known1', 'known_audit1',
        'shared1', 'shared_audit1', 'resources_audit1')
    reports = {name:load(e/name/'report.json') for name in folders}
    for j in (1, 2, 3):
        produced, audited = reports['controls'+str(j)], reports['controls_audit'+str(j)]
        assert audited['all_qualified'] and audited['producer_sha256'] == sha(e/('controls'+str(j))/'report.json')
        assert len(produced['kernel_cases']) == 12 and len(audited['inverse_cases']) == 8 and len(audited['original_cases']) == 7
    for name in ('panels_audit1', 'panels_audit2'):
        assert reports[name]['all_qualified'] and len(reports[name]['guards']) == 12
    for name, count in (('known', 12), ('shared', 8)):
        produced, audited = reports[name+'1'], reports[name+'_audit1']
        assert produced['all_qualified'] and audited['all_qualified'] and audited['pass_count'] == count
        assert produced['file_pipeline'] and audited['producer_sha256'] == sha(e/(name+'1')/'report.json')
    resources = reports['resources_audit1']
    assert resources['all_qualified'] and len(resources['cases']) == 20 and len(resources['comparisons']) == 80
    paths = set()
    for flags in (['ls-files', '-z'], ['ls-files', '--others', '--exclude-standard', '-z']):
        paths.update(subprocess.check_output(['git']+flags, cwd=repo).decode('utf-8').split('\0'))
    previous = a.workspace/'baselines/waveform_early_release_v1'
    protected, sources, versions = {}, set(), {}
    for name, count in (('C_files_sha256.json', 670), ('voice_files_sha256.json', 82), ('F2_files_sha256.json', 3)):
        values = load(previous/'evidence'/name)
        assert len(values) == count and all(sha(repo/n) == h for n, h in values.items())
        protected[name] = values
        sources.update(values)
    assert {n for n in paths if Path(n).suffix in ('.c', '.h')} == set(protected['C_files_sha256.json'])
    assert sha(repo/'handoff/C文件索引.csv') == sha(previous/'source/handoff/C文件索引.csv')
    hearings = load(repo/'research/waveform_early_release_v1_summary.json')['protected_hearings_sha256']
    assert all(sha(repo/n) == h for n, h in hearings.items())
    sources.update(hearings)
    parents, inputs, locations = {}, {}, {}
    def parent(name):
        if name not in parents:
            root = a.workspace/'baselines'/name
            assert sha(root/'manifest.json') == load(repo/f'research/{name}_summary.json')['manifest_sha256']
            mapping = {v['path']:v['sha256'] for v in load(root/'manifest.json')['files']}
            parents[name] = root, mapping
            for leaf in ('manifest.json', 'validation.json'):
                inputs[f'upstream/{name}/{leaf}'] = root/leaf
        return parents[name]
    parent('waveform_early_release_v1')
    def bind(name, digest):
        path = Path(name)
        assert sha(path) == digest, path
        if path.is_relative_to(e):
            rel = path.relative_to(e)
            assert rel.parts[0] in folders
            target = 'evidence/'+rel.as_posix()
        elif path.is_relative_to(repo):
            key = 'current/'+path.relative_to(repo).as_posix()
            inputs[key] = path
            target = 'inputs/'+key
        elif path.is_relative_to(a.workspace/'baselines'):
            archive = path.relative_to(a.workspace/'baselines').parts[0]
            root, mapping = parent(archive)
            leaf = path.relative_to(root).as_posix()
            assert (sha(root/'manifest.json') if leaf == 'manifest.json' else mapping[leaf]) == digest
            key = f'upstream/{archive}/{leaf}'
            inputs[key] = path
            target = 'inputs/'+key
        else:
            raise AssertionError(('Unexpected input', path))
        locations[str(path)] = target
    def factor_files(value):
        if isinstance(value, dict):
            if {'path', 'shape', 'file_bytes', 'sha256'} <= value.keys():
                bind(value['path'], value['sha256'])
            for child in value.values():
                factor_files(child)
        elif isinstance(value, list):
            for child in value:
                factor_files(child)
    for folder, report in reports.items():
        for key in ('inputs', 'input_sha256'):
            for name, digest in report.get(key, {}).items():
                bind(name, digest)
        for name, digest in report.get('sources', {}).items():
            assert sha(e/folder/'exact_sources'/name) == digest
            sources.add(name)
            versions.setdefault(name, {})[folder] = digest
        for key in ('oracle_sha256', 'oracles_sha256'):
            sources.update(report.get(key, {}))
        factor_files(report)
    sources.update(n for n in paths if n and ('waveform_file' in n or '/waveform_file_v1/' in n)
                   and Path(n).suffix in ('.py', '.md', '.json'))
    sources.discard('research/waveform_file_panels_v1_summary.json')
    sources.update(('research/有界文件因子V1.md', 'tools/research_archive_v1.py',
        'tools/verify_research_archive_independent_v1.py', 'tools/audit_waveform_correction_controls_v1.py',
        'tools/audit_waveform_representer_controls_v1.py', 'AGENTS.md', 'README.md', 'CMakeLists.txt',
        'handoff/C文件索引.csv', 'handoff/当前代码阅读入口.md', 'handoff/研究续接.md'))
    sources = {n for n in sources if (repo/n).is_file()}
    stage = e/'package1'
    stage.mkdir(exist_ok=False)
    for folder in folders:
        shutil.copytree(e/folder, stage/folder)
    for name, values in protected.items():
        save(stage/name, values)
    shutil.copy2(__file__, stage/'executed_package.py')
    inputs['data_AGENTS.md'] = a.workspace/'AGENTS.md'
    summary = dict(result='waveform_file_panels_original_known_and_resources_frozen',
        selected_terminal_evidence_directories=list(folders), original_input_archive_locations=locations,
        upstream_manifests_sha256={n:sha(root/'manifest.json') for n, (root, mapping) in parents.items()},
        executed_source_versions=versions, current_source_sha256={n:sha(repo/n) for n in sources},
        kernel_controls=12, inverse_controls=8, arbitrary_controls=7, input_guards=12,
        original12=12, shared8=8, original4DFT_3temporal_native_roots_reused_exact=True,
        complete_known_native_file_resources=resources['cases'], all80_signed_comparisons=resources['comparisons'],
        numerical_regressions=sum(c['regressed'] for c in resources['comparisons']),
        small_known_complete_Q_exports_are_audit_only=True, original_gates_unchanged=True,
        full_or_real_context_resource_qualified=False, no_C_or_timbre_promotion=True,
        C_H_exact=670, voice_parameters_exact=82, F2_files_exact=3, C_index_exact=True,
        protected_hearings_sha256=hearings, runtime_default_driver_owned_take_room_changed=False,
        downloaded=False, pushed=False, old68CTest_not_repeated=True, full_goal='active',
        next='research/waveform_file_panels_next_v1_plan.json')
    root = a.workspace/'baselines/waveform_file_panels_v1'
    result = freeze(root, repo, sources, stage, inputs, summary)
    verify(root)
    save(repo/'research/waveform_file_panels_v1_summary.json', dict(summary, **result))
    append_index(repo/'handoff/阶段索引.csv', ['waveform_file_panels_v1',
        'baselines/waveform_file_panels_v1/manifest.json', result['file_count'], result['manifest_sha256'],
        'bounded fileQR/complete triangular;original8/7/original12/shared8 independentlyPASS',
        '670C-H82voice3F2/index exact;known only/full-context pending;all versions/80 signed retained',
        'research/有界文件因子V1.md | research/waveform_file_panels_v1_summary.json',
        'baselines/waveform_file_panels_v1/validation.json'])
    print(result, flush=True)


if __name__ == '__main__':
    main()
