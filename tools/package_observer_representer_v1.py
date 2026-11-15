"""Freeze equivalent-solver qualification, failed attempts and complete regressions."""
import argparse, shutil, subprocess
from pathlib import Path
from research_archive_v1 import load, save, sha, freeze, verify, append_index


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', type=Path, required=True)
    a = p.parse_args()
    repo = Path(__file__).resolve().parents[1]
    e = a.workspace/'references/analysis/observer_representer_v1'
    parent = a.workspace/'baselines/observer_supported_v1'
    root = a.workspace/'baselines/observer_representer_v1'
    old = load(repo/'research/observer_supported_v1_summary.json')
    assert sha(parent/'manifest.json') == old['manifest_sha256']
    entries = {row['path']:row['sha256'] for row in load(parent/'manifest.json')['files']}
    protected = {}
    for name, count in (('C_files_sha256.json', 670), ('voice_files_sha256.json', 82), ('F2_files_sha256.json', 3)):
        values = load(parent/'evidence'/name)
        assert len(values) == count and all(sha(repo/n) == d for n, d in values.items())
        save(e/name, values)
        protected[name] = values
    names = set()
    for flags in (['ls-files', '-z'], ['ls-files', '--others', '--exclude-standard', '-z']):
        names.update(subprocess.check_output(['git']+flags, cwd=repo).decode('utf-8').split('\0'))
    names.discard('')
    assert {n for n in names if Path(n).suffix in ('.c', '.h')} == set(protected['C_files_sha256.json'])
    assert sha(repo/'handoff/C文件索引.csv') == entries['source/handoff/C文件索引.csv']
    hearings = old['protected_hearings_sha256']
    assert all(sha(repo/n) == d for n, d in hearings.items())
    inputs = {'data_AGENTS':a.workspace/'AGENTS.md'}
    locations = {}
    def bind(path, digest):
        path = Path(path)
        assert sha(path) == digest
        if path.is_relative_to(e):
            target = 'evidence/'+path.relative_to(e).as_posix()
        else:
            assert path.is_relative_to(parent), str(path)
            relative = path.relative_to(parent).as_posix()
            assert digest == entries[relative]
            key = 'upstream/observer_supported_v1/'+relative
            inputs[key] = path
            target = 'inputs/'+key
        locations[str(path)] = target
    for folder, result in (('algebra2', 'observer_representer_algebra_measured'),
            ('primal_algebra1', 'observer_representer_primal_algebra_measured'),
            ('context1', 'observer_representer_context_measured'), ('full1', 'observer_representer_full_known_measured')):
        r = load(e/folder/'report.json')
        assert r['result'] == result
        for name, digest in r['sources'].items():
            assert sha(repo/name) == sha(e/folder/'exact_sources'/name) == digest
        for path, digest in r.get('inputs', {}).items():
            bind(path, digest)
    for folder, producer, script in (('algebra_audit1', 'algebra2', 'tools/audit_observer_representer_known_v1.py'),
            ('primal_algebra_audit1', 'primal_algebra1', 'tools/audit_observer_representer_known_v1.py'),
            ('context_audit1', 'context1', 'tools/audit_observer_representer_context_v1.py'),
            ('full_audit1', 'full1', 'tools/audit_observer_representer_full_v1.py')):
        r = load(e/folder/'report.json')
        assert r['result'].startswith('independent_') and r['result'].endswith('_passed')
        assert r['producer_sha256'] == sha(e/producer/'report.json')
        assert r['auditor_sha256'] == sha(e/folder/'executed_audit.py') == sha(repo/script)
        for j, (name, digest) in enumerate(r.get('oracles_sha256', {}).items()):
            assert sha(repo/name) == sha(e/folder/f'executed_oracle_{j}.py') == digest
        for path, digest in r.get('extra_inputs', {}).items():
            bind(path, digest)
    assert load(e/'algebra1/report.json')['result'] == 'failed'
    assert not load(e/'algebra2/report.json')['all_qualified']
    pub = load(e/'review2/report.json')
    audit = load(e/'review2/metrics_verification.json')
    visual = load(e/'review2/visual_review.json')
    assert audit['result'] == 'independent_observer_representer_review_passed'
    assert audit['producer_sha256'] == sha(e/'review2/report.json')
    assert visual['scientific_figures_individually_viewed'] == 2 and visual['accepted_for_publication']
    assert visual['images_sha256'] == pub['images'] and all(sha(e/'review2'/n) == d for n, d in pub['images'].items())
    assert not list(e.rglob('*.wav'))
    inputs['upstream/observer_supported_v1/manifest.json'] = parent/'manifest.json'
    inputs['upstream/observer_supported_v1/validation.json'] = parent/'validation.json'
    validation = dict(result='observer_representer_frozen', results=pub['summary'], original_input_archive_locations=locations,
        C_H_exact=670, voice_parameters_exact=82, F2_files_exact=3, C_index_exact=True, protected_hearings_sha256=hearings,
        construction_failure_retained='algebra1', failed_dual_iteration_retained='algebra2 all4',
        full288_solver_failed=True, scientific_figures_individually_viewed=2, layout_review1_preserved=True,
        original_gates_and_objective_unchanged=True, source_models_fitted=0, native48k_or_C_or_timbre_qualified=False,
        runtime_default_driver_owned_take_room_changed=False, old_68CTest_not_repeated=True, downloaded=False, pushed=False,
        full_goal='active', previous_goal_turn_classification='progress: supported extraction/full-known/null evidence frozen at1b9e375',
        next='research/observer_representer_krylov_v1_plan.json')
    sources = [n.removeprefix('source/') for n in entries if n.startswith('source/') and (repo/n.removeprefix('source/')).is_file()]
    sources += [n for n in names if 'observer_representer' in n and Path(n).suffix in ('.py', '.json', '.md')]
    sources += ['research/等价声源求解与零方向V1.md', 'tools/package_observer_representer_v1.py']
    shutil.copy2(__file__, e/'executed_package.py')
    result = freeze(root, repo, sources, e, inputs, validation)
    verify(root)
    save(repo/'research/observer_representer_v1_summary.json', dict(validation, **result))
    append_index(repo/'handoff/阶段索引.csv', ['observer_representer_v1', 'baselines/observer_representer_v1/manifest.json',
        result['file_count'], result['manifest_sha256'], '4dualFAILED/4primalPASS/8HannPASS/full288FAILED/null-stationarity',
        '670C-H82voice3F2/index exact;no source promotion;all regressions retained',
        'research/等价声源求解与零方向V1.md | research/observer_representer_v1_summary.json', 'baselines/observer_representer_v1/validation.json'])
    print(dict(result='observer_representer_frozen', **result), flush=True)


if __name__ == '__main__':
    main()
