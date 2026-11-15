"""Freeze complete supported-known evidence and preserve failed full-scale gates."""
import argparse, shutil, subprocess
from pathlib import Path
from research_archive_v1 import load, save, sha, freeze, verify, append_index


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', type=Path, required=True)
    a = p.parse_args()
    repo = Path(__file__).resolve().parents[1]
    e = a.workspace/'references/analysis/observer_supported_v1'
    root = a.workspace/'baselines/observer_supported_v1'
    parent = a.workspace/'baselines/observer_frequency_correction_v1'
    upstream = load(repo/'research/observer_frequency_correction_v1_summary.json')
    assert sha(parent/'manifest.json') == upstream['manifest_sha256']
    manifest = load(parent/'manifest.json')
    old_sources = {row['path'].removeprefix('source/'): row['sha256']
        for row in manifest['files'] if row['path'].startswith('source/')}
    protected = {}
    for name, count in (('C_files_sha256.json', 670), ('voice_files_sha256.json', 82), ('F2_files_sha256.json', 3)):
        values = load(parent/'evidence'/name)
        assert len(values) == count and all(sha(repo/n) == digest for n, digest in values.items())
        save(e/name, values)
        protected[name] = values
    names = set()
    for flags in (['ls-files', '-z'], ['ls-files', '--others', '--exclude-standard', '-z']):
        names.update(subprocess.check_output(['git']+flags, cwd=repo).decode('utf-8').split('\0'))
    names.discard('')
    assert {n for n in names if Path(n).suffix in ('.c', '.h')} == set(protected['C_files_sha256.json'])
    assert sha(repo/'handoff/C文件索引.csv') == old_sources['handoff/C文件索引.csv']
    hearings = upstream['protected_hearings_sha256']
    assert all(sha(repo/n) == d for n, d in hearings.items())
    producers = dict(known1='observer_supported_known_measured', context1='observer_context_known_measured',
        full1='observer_supported_full_known_measured', null1='observer_supported_data_null_diagnosed')
    locations = {}
    for folder, result in producers.items():
        r = load(e/folder/'report.json')
        assert r['result'] == result
        for name, digest in r['sources'].items():
            assert sha(repo/name) == sha(e/folder/'exact_sources'/name) == digest
        for name, digest in r.get('inputs', {}).items():
            path = Path(name)
            assert path.is_relative_to(e) and sha(path) == digest
            locations[name] = 'evidence/'+path.relative_to(e).as_posix()
    audits = (('known_audit3', 'known1', 'tools/audit_observer_supported_known_v1.py'),
        ('context_audit1', 'context1', 'tools/audit_observer_context_known_v1.py'),
        ('full_audit1', 'full1', 'tools/audit_observer_supported_full_known_v1.py'),
        ('null_audit1', 'null1', 'tools/audit_observer_supported_null_v1.py'))
    for folder, producer, script in audits:
        r = load(e/folder/'report.json')
        assert r['result'].startswith('independent_') and r['result'].endswith('_passed')
        assert r['producer_sha256'] == sha(e/producer/'report.json')
        assert r['auditor_sha256'] == sha(e/folder/'executed_audit.py') == sha(repo/script)
        for j, (name, digest) in enumerate(r.get('oracles_sha256', {}).items()):
            assert sha(repo/name) == sha(e/folder/f'executed_oracle_{j}.py') == digest
    for folder in ('known_audit1', 'known_audit2'):
        assert load(e/folder/'report.json')['result'] == 'failed'
    pub = load(e/'review2/report.json')
    metrics = load(e/'review2/metrics_verification.json')
    visual = load(e/'review2/visual_review.json')
    assert metrics['result'] == 'independent_observer_supported_publication_passed'
    assert metrics['producer_sha256'] == sha(e/'review2/report.json')
    assert metrics['auditor_sha256'] == sha(e/'review2/executed_metrics_audit.py') == sha(repo/'tools/audit_observer_supported_publication_v1.py')
    assert visual['scientific_figures_individually_viewed'] == 2 and visual['accepted_for_publication']
    assert pub['images'] == visual['images_sha256']
    assert all(sha(e/'review2'/name) == d for name, d in pub['images'].items())
    assert not list(e.rglob('*.wav'))
    inputs = {'data_AGENTS': a.workspace/'AGENTS.md',
        'upstream/observer_frequency_correction_v1/manifest.json': parent/'manifest.json',
        'upstream/observer_frequency_correction_v1/validation.json': parent/'validation.json'}
    validation = dict(result='observer_supported_frozen', results=pub['summary'],
        original_input_archive_locations=locations, C_H_exact=670, voice_parameters_exact=82, F2_files_exact=3,
        C_index_exact=True, protected_hearings_sha256=hearings, historical_failed_audits=['known_audit1', 'known_audit2'],
        superseded_layout='review1 legend only;review2 final', scientific_figures_individually_viewed=2,
        original_gates_unchanged=True, full288_solver_failed=True, source_models_fitted=0,
        new_stochastic_source=False, native48k_or_C_or_timbre_qualified=False,
        runtime_default_driver_owned_take_room_changed=False, old_68CTest_not_repeated=True,
        downloaded=False, pushed=False, full_goal='active', next='research/observer_representer_v1_plan.json')
    sources = [n for n in old_sources if (repo/n).is_file()]
    sources += [n for n in names if ('observer_supported' in n or 'observer_context' in n or 'observer_representer' in n)
        and Path(n).suffix in ('.py', '.json', '.md')]
    sources += ['research/完整窗与前后文提取V1.md', 'tools/package_observer_supported_v1.py']
    shutil.copy2(__file__, e/'executed_package.py')
    result = freeze(root, repo, sources, e, inputs, validation)
    verify(root)
    save(repo/'research/observer_supported_v1_summary.json', dict(validation, **result))
    append_index(repo/'handoff/阶段索引.csv', ['observer_supported_v1', 'baselines/observer_supported_v1/manifest.json',
        result['file_count'], result['manifest_sha256'], '8known32dense;8genuine-context;full288;data-null;all independent',
        '670C-H82voice3F2/index exact;full288solver FAILED;no source promotion',
        'research/完整窗与前后文提取V1.md | research/observer_supported_v1_summary.json', 'baselines/observer_supported_v1/validation.json'])
    print(dict(result='observer_supported_frozen', **result), flush=True)


if __name__ == '__main__':
    main()
