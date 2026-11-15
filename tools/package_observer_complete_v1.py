"""Freeze complete-frame controls, all source fits and failed publication attempt."""
import argparse, shutil, subprocess
from pathlib import Path
from research_archive_v1 import load, save, sha, freeze, verify, append_index


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', type=Path, required=True)
    a = p.parse_args()
    repo = Path(__file__).resolve().parents[1]
    e = a.workspace/'references/analysis/observer_complete_v1'
    root = a.workspace/'baselines/observer_complete_v1'
    parent = a.workspace/'baselines/observer_inverse_v1'
    assert sha(parent/'manifest.json') == load(repo/'research/observer_inverse_v1_summary.json')['manifest_sha256']
    protected = {}
    for name, count in (('C_files_sha256.json', 670), ('voice_files_sha256.json', 82), ('F2_files_sha256.json', 3)):
        values = load(parent/'evidence'/name)
        assert len(values) == count and all(sha(repo/n) == d for n, d in values.items())
        save(e/name, values); protected[name] = values
    names = set()
    for flags in (['ls-files', '-z'], ['ls-files', '--others', '--exclude-standard', '-z']):
        names.update(subprocess.check_output(['git']+flags, cwd=repo).decode('utf-8').split('\0'))
    names.discard('')
    assert {n for n in names if Path(n).suffix in ('.c', '.h')} == set(protected['C_files_sha256.json'])
    pm = {r['path']: r['sha256'] for r in load(parent/'manifest.json')['files']}
    assert sha(repo/'handoff/C文件索引.csv') == pm['source/handoff/C文件索引.csv']
    hearings = load(parent/'validation.json')['protected_hearings_sha256']
    assert all(sha(repo/n) == d for n, d in hearings.items())
    allinputs = {}
    for folder, terminal in (('known1', 'observer_complete_known_ready'), ('real1', 'observer_complete_all6_measured')):
        record = load(e/folder/'report.json')
        assert record['result'] == terminal
        for name, digest in record['sources'].items():
            assert sha(repo/name) == sha(e/folder/'exact_sources'/name) == digest
        for name, digest in record.get('inputs', {}).items():
            assert sha(name) == digest
            if name in allinputs: assert allinputs[name] == digest
            allinputs[name] = digest
    for folder, producer, terminal in (
        ('known_audit1', 'known1', 'independent_observer_complete_known_passed'),
        ('real_audit1', 'real1', 'independent_observer_complete_real_passed')):
        audit = load(e/folder/'report.json')
        assert audit['result'] == terminal and audit['producer_sha256'] == sha(e/producer/'report.json')
        assert audit['auditor_sha256'] == sha(e/folder/'executed_audit.py')
    pub = load(e/'review2/report.json'); metrics = load(e/'review2/metrics_verification.json')
    visual = load(e/'review2/visual_review.json'); decision = load(e/'review2/decision.json')
    assert pub['result'] == 'observer_complete_review_ready'
    assert metrics['result'] == 'independent_observer_complete_publication_passed'
    assert metrics['all24_rows_verified'] and metrics['all6_solver_records_verified']
    assert metrics['all_aggregates_and_improvement_regression_counts_verified']
    for path, digest in pub['inputs'].items():
        assert sha(path) == digest
        allinputs[path] = digest
    for name, digest in pub['sources'].items():
        assert sha(repo/name) == sha(e/'review2/exact_sources'/name) == digest
    for key in ('figure_inputs', 'solve_inputs', 'summary'):
        assert sha(e/'review2'/(key+'.json')) == pub[key+'_sha256'] == metrics[key+'_sha256']
    assert metrics['auditor_sha256'] == sha(repo/'tools/audit_observer_complete_review_v1.py') == sha(e/'review2/executed_metrics_audit.py')
    assert visual['scientific_figures_individually_viewed'] == 2 and visual['accepted_for_publication']
    for name, digest in pub['images'].items():
        assert sha(e/'review2'/name) == digest == visual['images_sha256'][name]
    assert not decision['native_or_runtime_promoted'] and not list(e.rglob('*.wav'))
    assert load(e/'review1/failure.json')['result'] == 'failed_before_publication'
    locations = {}; inputs = {'data_AGENTS': a.workspace/'AGENTS.md'}
    for path, digest in allinputs.items():
        path = Path(path)
        if path.is_relative_to(e):
            locations[str(path)] = 'evidence/'+path.relative_to(e).as_posix()
        else:
            assert path.is_relative_to(a.workspace/'baselines')
            rel = path.relative_to(a.workspace/'baselines').as_posix()
            inputs['upstream/'+rel] = path
            locations[str(path)] = 'inputs/upstream/'+rel
    for file in ('manifest.json', 'validation.json'):
        inputs['upstream/observer_inverse_v1/'+file] = parent/file
    validation = dict(result='observer_complete_frozen', source_models=6, engines=1, ascents=2,
        known_frame_controls=7, known_synthesis_controls=4, known_dense_controls=3,
        captures=24, band_Gram_matrices=11520, all_solvers_converged=False,
        original_input_archive_locations=locations, results=load(e/'review2/summary.json'),
        decision=decision, scientific_figures_individually_viewed=2,
        failed_publication_attempt_preserved=True, all_source_native_warp_arrays_preserved=True,
        C_H_exact=670, voice_parameters_exact=82, F2_files_exact=3, C_index_exact=True,
        protected_hearings_sha256=hearings, runtime_default_driver_owned_take_room_changed=False,
        new_stochastic_source=False, native48k_or_C_or_timbre_qualified=False,
        old_68CTest_not_repeated=True, downloaded=False, pushed=False,
        full_goal='active', next=decision['next'])
    sources = [n for n in names if Path(n).suffix in ('.c', '.h', '.cmake', '.in') or n.endswith('CMakeLists.txt')]
    sources += list(protected['voice_files_sha256.json'])+list(protected['F2_files_sha256.json'])+list(hearings)
    sources += [n for n in names if ('observer_complete' in n or 'observer_inverse' in n or 'observer_forward' in n)
        and Path(n).suffix in ('.py', '.json', '.md')]
    sources += ['tools/research_archive_v1.py', 'tools/verify_research_archive_independent_v1.py',
        'tools/circular_phase_lift_v1/audit_oracle.py', 'tools/conditional_phase_time_v1/observer.py',
        'tools/carrier_transfer_v1/spectral.py', 'tools/carrier_transfer_v1/groups.py', 'tools/sound_dna/windowed.py',
        'research/完整频谱与弱细节诊断V1.md', 'research/observer_frequency_metric_v1_plan.json',
        'AGENTS.md', 'README.md', 'handoff/C文件索引.csv', 'handoff/开发留痕.md',
        'handoff/研究续接.md', 'handoff/当前代码阅读入口.md']
    shutil.copy2(__file__, e/'executed_package.py')
    result = freeze(root, repo, sources, e, inputs, validation)
    verify(root)
    save(repo/'research/observer_complete_v1_summary.json', dict(validation, **result))
    append_index(repo/'handoff/阶段索引.csv', ['observer_complete_v1', 'baselines/observer_complete_v1/manifest.json',
        result['file_count'], result['manifest_sha256'], '7frame+4OSC+3dense;6source24outcomes11520Gram;all6stop7',
        '670C-H82voice3F2/index exact;fullwave improves but weakHF/LR/CV regress;not promoted',
        'research/完整频谱与弱细节诊断V1.md | research/observer_complete_v1_summary.json',
        'baselines/observer_complete_v1/validation.json'])
    print(dict(result='observer_complete_frozen', **result), flush=True)


if __name__ == '__main__':
    main()
