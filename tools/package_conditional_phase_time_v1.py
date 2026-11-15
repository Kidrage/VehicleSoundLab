"""Freeze time-domain evidence and unchanged C/model/listening contracts."""
import argparse
import csv
from pathlib import Path
import shutil
import subprocess
from research_archive_v1 import load, save, sha, freeze, verify, append_index


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    evidence = args.workspace/'references/analysis/conditional_phase_time_v1'
    root = args.workspace/'baselines/conditional_phase_time_v1'
    if args.verify:
        manifest = verify(root)
        print(dict(result='archive_verified', files=manifest['file_count'], bytes=manifest['bytes']))
        return
    parent = args.workspace/'baselines/conditional_phase_slope_v1'
    assert sha(parent/'manifest.json') == load(repo/'research/conditional_phase_slope_v1_summary.json')['manifest_sha256']
    parent_entries = {row['path']:row['sha256'] for row in load(parent/'manifest.json')['files']}
    protected = {}
    for name, count in [('C_files_sha256.json', 670), ('voice_files_sha256.json', 82), ('F2_files_sha256.json', 3)]:
        files = load(parent/'evidence'/name)
        assert len(files) == count and all(sha(repo/n) == h for n, h in files.items())
        save(evidence/name, files)
        protected[name] = files
    names = set()
    for command in [['ls-files', '-z'], ['ls-files', '--others', '--exclude-standard', '-z']]:
        names.update(subprocess.check_output(['git']+command, cwd=repo).decode('utf-8').split('\0'))
    names.discard('')
    assert {n for n in names if Path(n).suffix in ('.c', '.h')} == set(protected['C_files_sha256.json'])
    assert sha(repo/'handoff/C文件索引.csv') == parent_entries['source/handoff/C文件索引.csv']
    index = list(csv.reader((repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig', newline='')))
    assert len(index) == 671 and all(row[4] == protected['C_files_sha256.json'][row[0]] for row in index[1:])
    hearings = {}
    for path, digest in parent_entries.items():
        if path.startswith('source/research/') and ('listening' in path or 'acceptance' in path):
            name = path.removeprefix('source/')
            assert sha(repo/name) == digest
            hearings[name] = digest
    known = load(evidence/'known1/report.json')
    known_audit = load(evidence/'known_audit1/report.json')
    assert known['result'] == 'conditional_time_known_controls_ready' and len(known['cases']) == 7
    assert known_audit['result'] == 'independent_conditional_time_known_audit_passed'
    assert known_audit['producer_sha256'] == sha(evidence/'known1/report.json')
    assert known_audit['auditor_sha256'] == sha(evidence/'known_audit1/executed_audit.py') == sha(repo/'tools/audit_conditional_phase_time_known_v1.py')
    source = load(evidence/'real1/report.json')
    assert source['result'] == 'six_source_conditional_time_probes_ready' and len(source['cases']) == 6
    for stage in ('known1', 'real1'):
        producer = load(evidence/stage/'report.json')
        for name, digest in producer['sources'].items():
            assert sha(repo/name) == sha(evidence/stage/'exact_sources'/name) == digest
        for path, digest in producer['inputs'].items():
            assert sha(path) == digest
    audits = {}
    for folder in sorted(evidence.glob('real_audit*')):
        audit = load(folder/'report.json')
        assert sha(folder/'executed_audit.py') == audit.get('auditor_sha256', sha(folder/'executed_audit.py'))
        audits[folder.name] = audit['result']
    passing = [name for name, value in audits.items() if value == 'independent_conditional_time_real_audit_passed']
    assert len(passing) == 1
    audit_name = passing[0]
    audit = load(evidence/audit_name/'report.json')
    assert audit['producer_sha256'] == sha(evidence/'real1/report.json')
    assert audit['auditor_sha256'] == sha(repo/'tools/audit_conditional_phase_time_real_v1.py')
    assert audit['waveforms'] == 90 and audit['all_instantaneous_reobserved_and_JSON_statistics_verified']
    review_folder = evidence/'review1'
    review = load(review_folder/'report.json')
    assert review['result'] == 'conditional_time_figures_ready'
    for path, digest in review['inputs'].items():
        assert sha(path) == digest
    for name, digest in review['sources'].items():
        assert sha(repo/name) == sha(review_folder/'exact_sources'/name) == digest
    for name, digest in review['images'].items():
        assert sha(review_folder/name) == digest
    assert sha(review_folder/'summary.json') == review['summary_sha256']
    assert sha(review_folder/'figure_inputs.json') == review['figure_inputs_sha256']
    visual = load(review_folder/'visual_review.json')
    assert visual['scientific_figures_individually_viewed'] == 2 and visual['accepted_for_publication']
    assert visual['images_sha256'] == review['images']
    metrics_audit = load(review_folder/'metrics_verification.json')
    assert metrics_audit['all_90_rows_and_all_aggregates_verified']
    assert metrics_audit['summary_sha256'] == review['summary_sha256']
    assert not list(evidence.rglob('*.wav'))
    validation = dict(
        result='conditional_phase_time_frozen',
        parent_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip(),
        previous_goal_turn='Progress: ADI V7 cost inventory and local commit; no synthesis advance. This stage resumes existing known-first waveform/observer work.',
        known_controls=7, source_models=6, seeds=3, variants=5, generated_waveforms=90,
        frames_per_waveform=65536, normalized_coordinate_only=True, native48k_aliasing_qualified=False,
        original_periodic_Hann_samples=4096, original_hop=256, full_generated_rows=241,
        source_rows_max_error_FS=max(row['source_rows_maximum_error_FS'] for row in source['cases']),
        saved_map_probe_max_error_radians=max(row['maximum_saved_map_probe_error_radians'] for row in source['cases']),
        first_source_seed_chunk_errors_FS=source['cases'][0]['seeds'][0]['chunk_identity_maximum_errors_FS'],
        known_audit=known_audit, real_audit=audit, retained_real_audits=audits,
        comparisons=load(review_folder/'summary.json'), scientific_figures_individually_viewed=2,
        metrics_independently_verified=True, C_H_exact=670, voice_parameters_exact=82, F2_files_exact=3,
        C_index_exact=True, protected_hearings_sha256=hearings, new_C_H=0,
        runtime_default_driver_owned_take_room_changed=False, new_listening_question=False,
        conditional_mapping_promoted=False,
        old_68CTest_not_repeated=True, downloaded=False, pushed=False,
        new_device_audio=False, physical_7_1_4=False, full_goal='active',
        next='Known-first carrier-group spectral transfer and signed cross terms on the exact same frozen waves, then qualify an observation-aware temporal model before native48k/listening/C. No distribution-only promotion, blind rho/rank/strength changes or replacement of accepted moving35. Preserve V6 buses, one driver and independent future spatial layer; full multi-engine/state/physical7.1.4 remains incomplete.')
    sources = [name for name in names if Path(name).suffix in ('.c', '.h', '.cmake', '.in') or name.endswith('CMakeLists.txt')]
    sources += list(protected['voice_files_sha256.json'])+list(protected['F2_files_sha256.json'])+list(hearings)
    sources += [name for name in names if 'conditional_phase_time' in name and Path(name).suffix in ('.py', '.md', '.json')]
    sources += list(source['sources'])+[
        'tools/research_archive_v1.py', 'research/条件相位时域复测V1.md',
        'AGENTS.md', 'README.md', 'handoff/C文件索引.csv', 'handoff/开发留痕.md',
        'handoff/研究续接.md', 'handoff/当前代码阅读入口.md',
        'handoff/ADI21569算力估算V7.md', 'tools/estimate_adi21569_v7.py',
        'research/adi21569_estimate_v7_summary.json']
    inputs = dict(data_AGENTS=args.workspace/'AGENTS.md', parent_manifest=parent/'manifest.json',
                  parent_validation=parent/'validation.json',
                  frozen_C_build_source_zip=args.workspace/'baselines/F3_local_atlas_v1/source.zip')
    for name in source['inputs']:
        path = Path(name)
        if path.is_relative_to(args.workspace/'baselines'):
            inputs['frozen_inputs/'+path.relative_to(args.workspace/'baselines').as_posix()] = path
    shutil.copy2(__file__, evidence/'executed_package.py')
    result = freeze(root, repo, sources, evidence, inputs, validation)
    verify(root)
    save(repo/'research/conditional_phase_time_v1_summary.json', dict(validation, **result))
    append_index(repo/'handoff/阶段索引.csv', [
        'conditional_phase_time_v1', 'baselines/conditional_phase_time_v1/manifest.json', result['file_count'],
        result['manifest_sha256'], '7known;6source3seed5variants90waves;independentAR-CDF-OSC-STFT;2figures',
        '670C-H82voice3F2/index exact;normalized diagnostic only;all alternatives retained;no runtime or hearing adoption',
        'research/条件相位时域复测V1.md | research/conditional_phase_time_v1_summary.json',
        'Qualify temporal spectral transfer before native audio/C;multi-engine/state/physical7.1.4 active'])
    print(dict(result='conditional_phase_time_frozen', **result))


if __name__ == '__main__':
    main()
