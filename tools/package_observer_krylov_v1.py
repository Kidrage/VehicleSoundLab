"""Freeze orthogonality evidence and all eight unresolved reorth stopping failures."""
import argparse, shutil, subprocess
from pathlib import Path
from research_archive_v1 import load, save, sha, freeze, verify, append_index


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', type=Path, required=True)
    a = p.parse_args()
    repo = Path(__file__).resolve().parents[1]
    e = a.workspace/'references/analysis/observer_krylov_v1'
    parent = a.workspace/'baselines/observer_representer_v1'
    root = a.workspace/'baselines/observer_krylov_v1'
    old = load(repo/'research/observer_representer_v1_summary.json')
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
            key = 'upstream/observer_representer_v1/'+relative
            inputs[key] = path
            target = 'inputs/'+key
        locations[str(path)] = target
    for folder, result in (('known1', 'observer_krylov_known_measured'),
            ('full1', 'observer_krylov_full_diagnostic_measured'), ('reorth_known1', 'observer_reorth_known_measured')):
        r = load(e/folder/'report.json')
        assert r['result'] == result
        for name, digest in r['sources'].items():
            assert sha(repo/name) == sha(e/folder/'exact_sources'/name) == digest
        for path, digest in r.get('inputs', {}).items():
            bind(path, digest)
    for folder, producer, script in (('known_audit1', 'known1', 'tools/audit_observer_krylov_v1.py'),
            ('full_audit1', 'full1', 'tools/audit_observer_krylov_v1.py'),
            ('reorth_known_audit1', 'reorth_known1', 'tools/audit_observer_reorth_known_v1.py')):
        r = load(e/folder/'report.json')
        assert r['result'].startswith('independent_') and r['result'].endswith('_passed')
        assert r['producer_sha256'] == sha(e/producer/'report.json')
        assert r['auditor_sha256'] == sha(e/folder/'executed_audit.py') == sha(repo/script)
        for j, (name, digest) in enumerate(r.get('oracles_sha256', {}).items()):
            assert sha(repo/name) == sha(e/folder/f'executed_oracle_{j}.py') == digest
    full = load(e/'full1/report.json')
    assert full['info']['forward_steps'] == 128 and full['only_one_fixed128_probe']
    assert not load(e/'reorth_known1/report.json')['all_qualified']
    assert load(e/'reorth_known_audit1/report.json')['pass_count'] == 4
    pub = load(e/'review2/report.json')
    audit = load(e/'review2/metrics_verification.json')
    visual = load(e/'review2/visual_review.json')
    assert audit['result'] == 'independent_observer_krylov_review_passed'
    assert audit['producer_sha256'] == sha(e/'review2/report.json')
    assert visual['scientific_figures_individually_viewed'] == 2 and visual['accepted_for_publication']
    assert visual['images_sha256'] == pub['images'] and all(sha(e/'review2'/n) == d for n, d in pub['images'].items())
    for review in ('review1', 'review2'):
        for path, digest in load(e/review/'report.json')['inputs'].items():
            bind(path, digest)
        assert load(e/review/'failed_metrics_audit_1.json')['result'] == 'failed'
    assert not list(e.rglob('*.wav'))
    for name in ('manifest.json', 'validation.json'):
        inputs['upstream/observer_representer_v1/'+name] = parent/name
    validation = dict(result='observer_krylov_frozen', results=pub['summary'], original_input_archive_locations=locations,
        C_H_exact=670, voice_parameters_exact=82, F2_files_exact=3, C_index_exact=True, protected_hearings_sha256=hearings,
        full128_forward_and_adjoint_independently_verified=True, reorth_Hann_failures_retained=8,
        failed_publication_metric_versions_retained=2, layout_review1_retained=True,
        scientific_figures_individually_viewed=2, original_gates_and_objective_unchanged=True,
        new_full_fit_attempts=0, source_models_fitted=0, native48k_or_C_or_timbre_qualified=False,
        runtime_default_driver_owned_take_room_changed=False, old_68CTest_not_repeated=True, downloaded=False, pushed=False,
        full_goal='active', previous_goal_turn_classification='MCPS evidence only, no synthesis improvement',
        next='research/observer_reorth_stopping_v1_plan.json')
    sources = [n.removeprefix('source/') for n in entries if n.startswith('source/') and (repo/n.removeprefix('source/')).is_file()]
    sources += [n for n in names if any(s in n for s in ('observer_krylov', 'observer_reorth', 'krylov_diagnostic')) and Path(n).suffix in ('.py', '.json', '.md')]
    sources += ['research/求解正交性与终止诊断V1.md']
    shutil.copy2(__file__, e/'executed_package.py')
    result = freeze(root, repo, sources, e, inputs, validation)
    verify(root)
    save(repo/'research/observer_krylov_v1_summary.json', dict(validation, **result))
    append_index(repo/'handoff/阶段索引.csv', ['observer_krylov_v1', 'baselines/observer_krylov_v1/manifest.json',
        result['file_count'], result['manifest_sha256'], '11controls/128full-recurrencesPASS;reorth4PASS8HannFAIL',
        '670C-H82voice3F2/index exact;no full fit/source/audio promotion',
        'research/求解正交性与终止诊断V1.md | research/observer_krylov_v1_summary.json', 'baselines/observer_krylov_v1/validation.json'])
    print(dict(result='observer_krylov_frozen', **result), flush=True)


if __name__ == '__main__':
    main()
