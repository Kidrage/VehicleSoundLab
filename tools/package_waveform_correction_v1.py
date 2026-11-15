"""Freeze original-operator corrections, independent trajectories and storage."""
import argparse
import shutil
import subprocess
from pathlib import Path
from research_archive_v1 import load, save, sha, freeze, verify, append_index


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', type=Path, required=True); a = p.parse_args()
    repo = Path(__file__).resolve().parents[1]
    e = a.workspace/'references/analysis/waveform_original_correction_v1'
    folders = ('controls1', 'controls_audit1', 'known1', 'known_audit1',
               'shared1', 'shared_audit1', 'resources_audit1')
    reports = {n: load(e/n/'report.json') for n in folders}
    controls, known, shared, resources = (reports[n] for n in
        ('controls_audit1', 'known_audit1', 'shared_audit1', 'resources_audit1'))
    assert controls['all_qualified'] and len(controls['inverse_cases']) == 8 and len(controls['original_cases']) == 7
    assert known['all_qualified'] and known['pass_count'] == 12
    assert shared['all_qualified'] and shared['pass_count'] == 8
    assert len(resources['native_replays']) == 23 and len(resources['native_rejections']) == 5
    assert not resources['native_probe_factory_selected']
    paths = set()
    for flags in (['ls-files', '-z'], ['ls-files', '--others', '--exclude-standard', '-z']):
        paths.update(subprocess.check_output(['git']+flags, cwd=repo).decode('utf-8').split('\0'))
    previous = a.workspace/'baselines/waveform_banded_v1'
    protected, sources, parents, inputs, locations = {}, set(), {}, {}, {}
    for name, count in (('C_files_sha256.json', 670), ('voice_files_sha256.json', 82), ('F2_files_sha256.json', 3)):
        values = load(previous/'evidence'/name)
        assert len(values) == count and all(sha(repo/n) == h for n, h in values.items())
        protected[name] = values; sources.update(values)
    assert {n for n in paths if Path(n).suffix in ('.c', '.h')} == set(protected['C_files_sha256.json'])
    assert sha(repo/'handoff/C文件索引.csv') == sha(previous/'source/handoff/C文件索引.csv')
    hearings = load(repo/'research/waveform_banded_v1_summary.json')['protected_hearings_sha256']
    assert all(sha(repo/n) == h for n, h in hearings.items()); sources.update(hearings)

    def parent(name):
        if name not in parents:
            root = a.workspace/'baselines'/name
            assert sha(root/'manifest.json') == load(repo/f'research/{name}_summary.json')['manifest_sha256']
            parents[name] = (root, {v['path']: v['sha256'] for v in load(root/'manifest.json')['files']})
            for leaf in ('manifest.json', 'validation.json'):
                inputs[f'upstream/{name}/{leaf}'] = root/leaf
        return parents[name]

    parent('waveform_banded_v1')

    def bind(name, digest):
        path = Path(name); assert sha(path) == digest
        if path.is_relative_to(e):
            rel = path.relative_to(e); assert rel.parts[0] in folders
            target = 'evidence/'+rel.as_posix()
        elif path.is_relative_to(repo):
            key = 'current/'+path.relative_to(repo).as_posix(); inputs[key] = path
            target = 'inputs/'+key
        elif path.is_relative_to(a.workspace/'baselines'):
            archive = path.relative_to(a.workspace/'baselines').parts[0]
            root, mapping = parent(archive); leaf = path.relative_to(root).as_posix()
            assert (sha(root/'manifest.json') if leaf == 'manifest.json' else mapping[leaf]) == digest
            key = f'upstream/{archive}/{leaf}'; inputs[key] = path; target = 'inputs/'+key
        else:
            raise AssertionError(('Unexpected unfrozen source input', path))
        locations[str(path)] = target

    for folder, report in reports.items():
        for name, digest in report.get('inputs', {}).items():
            bind(name, digest)
        for name, digest in report.get('sources', {}).items():
            assert sha(e/folder/'exact_sources'/name) == digest
            sources.add(name)
    sources.update(n for n in paths if 'waveform_correction' in n or 'waveform_original_correction' in n)
    sources.update(('research/原始算子修正与存储V1.md', 'research/waveform_correction_storage_v1_plan.json',
        'tools/verify_waveform_correction_bindings_v1.py', 'AGENTS.md', 'README.md', 'CMakeLists.txt',
        'handoff/C文件索引.csv', 'handoff/当前代码阅读入口.md', 'handoff/研究续接.md',
        'tools/research_archive_v1.py', 'tools/verify_research_archive_independent_v1.py'))
    sources = {n for n in sources if n and (repo/n).is_file()}
    stage = e/'package1'; stage.mkdir(exist_ok=False)
    for folder in folders:
        shutil.copytree(e/folder, stage/folder)
    for name, values in protected.items():
        save(stage/name, values)
    shutil.copy2(__file__, stage/'executed_package.py')
    inputs['data_AGENTS.md'] = a.workspace/'AGENTS.md'
    delayed = next(c for c in shared['cases'] if c['kind'] == 'Hann' and c['label'] == 'delayed_right')
    summary = dict(result='waveform_original_correction_known_progress_frozen',
        selected_terminal_evidence_directories=list(folders), original_input_archive_locations=locations,
        upstream_manifests_sha256={n: sha(root/'manifest.json') for n, (root, mapping) in parents.items()},
        inverse_controls_qualified=8, original_arbitrary_controls_qualified=7,
        original12_qualified=12, shared8_qualified=8, fixed_correction_steps=2,
        delayed_right_independent_original_normal=delayed['stable_complete_normal'],
        unchanged_original_normal_gate=1e-11,
        upstream_band_shared_pass_count=7, upstream_delayed_right_failure_retained=True,
        upstream_strict_Gram_failures_retained=True,
        native_triangle_replays=23, native_invalid_cases_rejected=5, native_factory_selected=False,
        original12_cumulative_peak=resources['original12_cumulative_process_peak'],
        shared8_cumulative_peak=resources['shared8_cumulative_process_peak'],
        conditional_resource_cases=resources['conditional_cases'],
        original1_5GiB_native_plus3GiB_headroom_preserved=True,
        full_or_real_or_native48k_or_C_or_hearing_qualified=False,
        outer_corrected_phase_qualified=False, C_H_exact=670, voice_parameters_exact=82, F2_files_exact=3,
        C_index_exact=True, protected_hearings_sha256=hearings,
        runtime_default_driver_owned_take_room_changed=False, old68CTest_not_repeated=True,
        downloaded=False, pushed=False, full_goal='active', previous_goal_turn='MCPS-only; no synthesis progress')
    root = a.workspace/'baselines/waveform_original_correction_v1'
    result = freeze(root, repo, sources, stage, inputs, summary); verify(root)
    save(repo/'research/waveform_original_correction_v1_summary.json', dict(summary, **result))
    append_index(repo/'handoff/阶段索引.csv', ['waveform_original_correction_v1',
        'baselines/waveform_original_correction_v1/manifest.json', result['file_count'], result['manifest_sha256'],
        'original12/shared8 independentPASS;originalFFT2step;8inverse/7original;23native probes',
        '670C-H82voice3F2/index exact;no full/source/C/hearing promotion',
        'research/原始算子修正与存储V1.md | research/waveform_original_correction_v1_summary.json',
        'baselines/waveform_original_correction_v1/validation.json'])
    print(result, flush=True)


if __name__ == '__main__':
    main()
