"""Freeze known objective controls and all six source fits without voice promotion."""
import argparse, shutil, subprocess
from pathlib import Path
from research_archive_v1 import load, save, sha, freeze, verify, append_index


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', type=Path, required=True)
    a = p.parse_args()
    repo = Path(__file__).resolve().parents[1]
    e = a.workspace/'references/analysis/observer_frequency_v1'
    root = a.workspace/'baselines/observer_frequency_v1'
    parent = a.workspace/'baselines/observer_complete_v1'
    assert sha(parent/'manifest.json') == load(repo/'research/observer_complete_v1_summary.json')['manifest_sha256']
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
    pm = {v['path']: v['sha256'] for v in load(parent/'manifest.json')['files']}
    assert sha(repo/'handoff/C文件索引.csv') == pm['source/handoff/C文件索引.csv']
    hearings = load(parent/'validation.json')['protected_hearings_sha256']
    assert all(sha(repo/n) == d for n, d in hearings.items())
    allinputs, historical = {}, []
    for folder, terminal in (('known1', 'observer_frequency_known_ready'), ('real1', 'observer_frequency_all6_measured')):
        record = load(e/folder/'report.json')
        assert record['result'] == terminal
        for name, digest in record['sources'].items():
            assert sha(repo/name) == sha(e/folder/'exact_sources'/name) == digest
        for name, digest in record.get('inputs', {}).items():
            assert sha(name) == digest
            if name in allinputs: assert allinputs[name] == digest
            allinputs[name] = digest
    for folder, producer, terminal in (
        ('known_audit1', 'known1', 'independent_observer_frequency_known_passed'),
        ('real_audit1', 'real1', 'independent_observer_frequency_real_passed')):
        audit = load(e/folder/'report.json')
        assert audit['result'] == terminal and audit['producer_sha256'] == sha(e/producer/'report.json')
        assert audit['auditor_sha256'] == sha(e/folder/'executed_audit.py')
        for j, (name, digest) in enumerate(audit['oracles_sha256'].items()):
            assert sha(e/folder/f'executed_oracle_{j}.py') == digest
            if sha(repo/name) != digest:
                historical.append(dict(audit=folder, file=name, executed_sha256=digest,
                    current_sha256=sha(repo/name), reason='Real-source gradient oracle added after known audit; original executed oracle retained'))
    for folder in ('block_known1', 'block_known2'):
        block = load(e/folder/'report.json')
        assert block['result'] == 'observer_frequency_block_known_ready'
        for name, digest in block['sources'].items():
            assert sha(e/folder/'exact_sources'/name) == digest
            if sha(repo/name) != digest:
                assert folder == 'block_known1' and name == 'tools/run_observer_frequency_block_known_v1.py'
                historical.append(dict(producer=folder, file=name, executed_sha256=digest,
                    current_sha256=sha(repo/name), reason='Stereo mapping control added after first mono controls; original executed producer retained'))
        for case in block['cases']:
            assert sha(e/folder/case['file']) == case['sha256']
            assert case['stop'] in (1, 2, 4, 5) and case['relative_stationarity'] < 2e-7
            assert case['dense_relative_error'] < 2e-7
            assert sha(e/'block_known1'/case['file']) == sha(e/'block_known2'/case['file'])
    ba = load(e/'block_known_audit1/report.json')
    assert ba['result'] == 'independent_observer_frequency_block_known_passed' and ba['stereo_verified']
    assert ba['producer_sha256'] == sha(e/'block_known2/report.json')
    assert ba['auditor_sha256'] == sha(repo/'tools/audit_observer_frequency_block_known_v1.py') == sha(e/'block_known_audit1/executed_audit.py')
    for j, (name, digest) in enumerate(ba['oracles_sha256'].items()):
        assert sha(repo/name) == sha(e/'block_known_audit1'/f'executed_oracle_{j}.py') == digest
    assert sha(e/'block_known2/stereo_map.npz') == load(e/'block_known2/report.json')['stereo_map_sha256']
    pub = load(e/'review1/report.json'); metrics = load(e/'review1/metrics_verification.json')
    visual = load(e/'review1/visual_review.json'); decision = load(e/'review1/decision.json')
    assert pub['result'] == 'observer_frequency_review_ready'
    assert metrics['result'] == 'independent_observer_frequency_publication_passed'
    assert metrics['all30_rows_verified'] and metrics['all6_solver_records_verified'] and metrics['all6_known_records_exact']
    assert metrics['all_aggregates_and_improvement_regression_counts_verified']
    for path, digest in pub['inputs'].items():
        assert sha(path) == digest; allinputs[path] = digest
    for name, digest in pub['sources'].items():
        assert sha(repo/name) == sha(e/'review1/exact_sources'/name) == digest
    for key in ('figure_inputs', 'solve_inputs', 'known_inputs', 'summary'):
        assert sha(e/'review1'/(key+'.json')) == pub[key+'_sha256'] == metrics[key+'_sha256']
    assert metrics['auditor_sha256'] == sha(repo/'tools/audit_observer_frequency_review_v1.py') == sha(e/'review1/executed_metrics_audit.py')
    assert visual['scientific_figures_individually_viewed'] == 2 and visual['accepted_for_publication']
    for name, digest in pub['images'].items():
        assert sha(e/'review1'/name) == digest == visual['images_sha256'][name]
    assert not decision['native_or_runtime_promoted'] and not list(e.rglob('*.wav'))
    inputs = {'data_AGENTS': a.workspace/'AGENTS.md'}; locations = {}
    for path, digest in allinputs.items():
        path = Path(path)
        if path.is_relative_to(e): locations[str(path)] = 'evidence/'+path.relative_to(e).as_posix()
        else:
            assert path.is_relative_to(a.workspace/'baselines')
            rel = path.relative_to(a.workspace/'baselines').as_posix()
            inputs['upstream/'+rel] = path; locations[str(path)] = 'inputs/upstream/'+rel
    for file in ('manifest.json', 'validation.json'):
        inputs['upstream/observer_complete_v1/'+file] = parent/file
    summary = load(e/'review1/summary.json')
    validation = dict(result='observer_frequency_frozen', source_models=6, engines=1, ascents=2,
        known_dense_cases=6, captures=30, band_Gram_matrices=14400,
        within_order_block_preconditioner_known_and_stereo_independently_passed=True,
        block_preconditioner_real_sources_not_part_of_this_frozen_stage=True,
        solver_converged=summary['solver_converged'], historical_audit_helpers=historical,
        original_input_archive_locations=locations, results=summary, decision=decision,
        mathematical_power_floor_not_measured_noise=True, scientific_figures_individually_viewed=2,
        all_source_native_warp_arrays_preserved=True, C_H_exact=670, voice_parameters_exact=82,
        F2_files_exact=3, C_index_exact=True, protected_hearings_sha256=hearings,
        runtime_default_driver_owned_take_room_changed=False, new_stochastic_source=False,
        native48k_or_C_or_timbre_qualified=False, old_68CTest_not_repeated=True,
        downloaded=False, pushed=False, full_goal='active', next=decision['next'])
    sources = [n for n in names if Path(n).suffix in ('.c', '.h', '.cmake', '.in') or n.endswith('CMakeLists.txt')]
    sources += list(protected['voice_files_sha256.json'])+list(protected['F2_files_sha256.json'])+list(hearings)
    sources += [n for n in names if ('observer_frequency' in n or 'observer_complete' in n or
        'observer_inverse' in n or 'observer_forward' in n) and Path(n).suffix in ('.py', '.json', '.md')]
    sources += ['tools/research_archive_v1.py', 'tools/verify_research_archive_independent_v1.py',
        'tools/circular_phase_lift_v1/audit_oracle.py', 'tools/conditional_phase_time_v1/observer.py',
        'tools/carrier_transfer_v1/spectral.py', 'tools/carrier_transfer_v1/groups.py', 'tools/sound_dna/windowed.py',
        'research/共享频率度量与弱高频V1.md', 'AGENTS.md', 'README.md', 'handoff/C文件索引.csv',
        'handoff/开发留痕.md', 'handoff/研究续接.md', 'handoff/当前代码阅读入口.md']
    shutil.copy2(__file__, e/'executed_package.py')
    result = freeze(root, repo, sources, e, inputs, validation); verify(root)
    save(repo/'research/observer_frequency_v1_summary.json', dict(validation, **result))
    append_index(repo/'handoff/阶段索引.csv', ['observer_frequency_v1', 'baselines/observer_frequency_v1/manifest.json',
        result['file_count'], result['manifest_sha256'], '6dense-known;shared-LR/all-bin-endcap;6source30outcomes14400Gram',
        '670C-H82voice3F2/index exact;in-sample inference,not a sustained voice',
        'research/共享频率度量与弱高频V1.md | research/observer_frequency_v1_summary.json',
        'baselines/observer_frequency_v1/validation.json'])
    print(dict(result='observer_frequency_frozen', **result), flush=True)


if __name__ == '__main__':
    main()
