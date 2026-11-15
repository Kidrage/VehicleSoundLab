"""Archive exact carrier partitions, full signed matrices and protected runtime."""
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
    evidence = args.workspace/'references/analysis/carrier_transfer_v1'
    root = args.workspace/'baselines/carrier_transfer_v1'
    if args.verify:
        manifest = verify(root)
        print(dict(result='archive_verified', files=manifest['file_count'], bytes=manifest['bytes']))
        return
    parent = args.workspace/'baselines/conditional_phase_time_v1'
    assert sha(parent/'manifest.json') == load(repo/'research/conditional_phase_time_v1_summary.json')['manifest_sha256']
    parent_entries = {row['path']:row['sha256'] for row in load(parent/'manifest.json')['files']}
    protected = {}
    for name, count in [('C_files_sha256.json',670), ('voice_files_sha256.json',82), ('F2_files_sha256.json',3)]:
        values = load(parent/'evidence'/name)
        assert len(values)==count and all(sha(repo/n)==digest for n,digest in values.items())
        save(evidence/name, values)
        protected[name] = values
    names = set()
    for command in [['ls-files','-z'],['ls-files','--others','--exclude-standard','-z']]:
        names.update(subprocess.check_output(['git']+command,cwd=repo).decode('utf-8').split('\0'))
    names.discard('')
    assert {n for n in names if Path(n).suffix in ('.c','.h')}==set(protected['C_files_sha256.json'])
    assert sha(repo/'handoff/C文件索引.csv')==parent_entries['source/handoff/C文件索引.csv']
    index=list(csv.reader((repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig',newline='')))
    assert len(index)==671 and all(row[4]==protected['C_files_sha256.json'][row[0]] for row in index[1:])
    hearings=load(parent/'validation.json')['protected_hearings_sha256']
    assert all(sha(repo/name)==digest for name,digest in hearings.items())
    known=load(evidence/'known1/report.json')
    assert known['result']=='carrier_transfer_known_ready' and len(known['cases'])==8
    for number in (1,2):
        audit=load(evidence/f'known_audit{number}/report.json')
        assert audit['result']=='independent_carrier_transfer_known_passed'
        assert audit['producer_sha256']==sha(evidence/'known1/report.json')
        assert audit['auditor_sha256']==sha(evidence/f'known_audit{number}/executed_audit.py')
    assert load(evidence/'known_audit2/report.json')['auditor_sha256']==sha(repo/'tools/audit_carrier_transfer_v1.py')
    source=load(evidence/'real1/report.json')
    assert source['result']=='all90_carrier_partitions_ready' and len(source['cases'])==6
    for stage in ('known1','real1'):
        run=load(evidence/stage/'report.json')
        for name,digest in run['sources'].items():
            assert sha(repo/name)==sha(evidence/stage/'exact_sources'/name)==digest
        for path,digest in run['inputs'].items():
            assert sha(path)==digest
    audit=load(evidence/'real_audit1/report.json')
    assert audit['result']=='independent_carrier_transfer_real_passed'
    assert audit['producer_sha256']==sha(evidence/'real1/report.json')
    assert audit['auditor_sha256']==sha(repo/'tools/audit_carrier_transfer_v1.py')==sha(evidence/'real_audit1/executed_audit.py')
    assert sum(case['waveforms'] for case in audit['cases'])==90 and audit['matrices']==173520
    review=load(evidence/'review1/report.json')
    assert review['result']=='carrier_transfer_figures_ready'
    for name,digest in review['sources'].items():
        assert sha(repo/name)==sha(evidence/'review1/exact_sources'/name)==digest
    for path,digest in review['inputs'].items():
        assert sha(path)==digest
    for name,digest in review['images'].items():
        assert sha(evidence/'review1'/name)==digest
    for name in ('figure_inputs','paired_inputs','summary'):
        assert sha(evidence/f'review1/{name}.json')==review[name+'_sha256']
    visual=load(evidence/'review1/visual_review.json')
    assert visual['accepted_for_publication'] and visual['scientific_figures_individually_viewed']==2
    assert visual['images_sha256']==review['images']
    metrics=load(evidence/'review1/metrics_verification.json')
    assert metrics['all90_rows_54_pairs_and_aggregates_verified']
    assert metrics['summary_sha256']==review['summary_sha256']
    assert metrics['auditor_sha256']==sha(repo/'tools/audit_carrier_transfer_review_v1.py')
    assert not list(evidence.rglob('*.wav'))
    # Separate known-only preparation for the next temporal hypothesis. These
    # controls have not read recordings and do not qualify a source candidate.
    followup=args.workspace/'references/analysis/circular_phase_lift_v1'
    follow_known=load(followup/'known1/report.json')
    follow_audit=load(followup/'known_audit1/report.json')
    assert follow_known['result']=='circular_phase_lift_known_ready'
    assert len(follow_known['cases'])==8 and not follow_known['recordings_or_models_read']
    assert follow_audit['result']=='independent_circular_phase_lift_known_passed'
    assert follow_audit['producer_sha256']==sha(followup/'known1/report.json')
    assert follow_audit['auditor_sha256']==sha(repo/'tools/audit_circular_phase_lift_known_v1.py')==sha(followup/'known_audit1/executed_audit.py')
    assert follow_audit['semantic_change_at_held_common_verified']
    for name,digest in follow_known['sources'].items():
        assert sha(repo/name)==sha(followup/'known1/exact_sources'/name)==digest
    for name,digest in follow_known['files'].items():
        assert sha(followup/'known1'/name)==digest
    assert not (evidence/'followup_known').exists()
    for name in ('known1','known_audit1'):
        shutil.copytree(followup/name,evidence/'followup_known/circular_phase_lift_v1'/name)
    validation=dict(
        result='carrier_transfer_frozen', parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
        previous_goal_turn='Progress:90 normalized time waves/independent original-observer audit archived and committed e1c33b6; conditional model not promoted.',
        known_controls=8, source_models=6, seeds=3, alternatives=5, exact_partitioned_waves=90,
        carrier_groups=6, stereo_groups_per_wave=6, frames=65536, normalized_coordinate_only=True,
        original_Hann_samples=4096, original_hop=256, full_complex_Gram_matrices=173520,
        known_audits=[load(evidence/f'known_audit{n}/report.json') for n in (1,2)], real_audit=audit,
        real_per_band_audit_strengthened_without_changing_original_tolerance=True,
        results=load(evidence/'review1/summary.json'), all90_rows_54_pairs_and_aggregates_verified=True,
        scientific_figures_individually_viewed=2, signed_complex_LR_and_group_interference_preserved=True,
        no_physical_source_percentage_or_noise_separation_claim=True,
        C_H_exact=670, voice_parameters_exact=82, F2_files_exact=3, C_index_exact=True,
        protected_hearings_sha256=hearings, new_C_H=0, runtime_default_driver_owned_take_room_changed=False,
        new_sound_candidate=False, native48k_aliasing_qualified=False, new_listening_question=False,
        followup_half_angle_known_controls=8, followup_independent_known_audit=follow_audit,
        followup_frozen_source_paths_tested=False, followup_lift_is_equivalent_waveform_fix=False,
        old_68CTest_not_repeated=True, downloaded=False, pushed=False, physical_7_1_4=False, full_goal='active',
        next='Eight circular half-angle/continuous-lift controls and independent scalar audit now pass. Next replay a no-sweep lift candidate on all frozen phase paths through original observer; instantaneous circular equivalence is not waveform/time-law equivalence and fast motion remains ambiguous. No new high-order boost or deletion of accepted low DNA. Preserve V6 buses/one driver/separate future spatial; full engines/states/physical7.1.4 remain incomplete.')
    sources=[name for name in names if Path(name).suffix in ('.c','.h','.cmake','.in') or name.endswith('CMakeLists.txt')]
    sources+=list(protected['voice_files_sha256.json'])+list(protected['F2_files_sha256.json'])+list(hearings)
    sources+=[name for name in names if ('carrier_transfer' in name or 'circular_phase_lift' in name) and Path(name).suffix in ('.py','.md','.json')]
    sources+=list(source['sources'])+['tools/research_archive_v1.py','tools/verify_research_archive_independent_v1.py',
        'research/载频来源与高频扩散V1.md','research/相位半角与连续提升控制V1.md','AGENTS.md','README.md','handoff/C文件索引.csv',
        'handoff/开发留痕.md','handoff/研究续接.md','handoff/当前代码阅读入口.md']
    inputs=dict(data_AGENTS=args.workspace/'AGENTS.md',parent_manifest=parent/'manifest.json',parent_validation=parent/'validation.json',
                frozen_C_build_source_zip=args.workspace/'baselines/F3_local_atlas_v1/source.zip')
    for path in source['inputs']:
        path=Path(path)
        if path.is_relative_to(parent):
            inputs['frozen_parent_inputs/'+path.relative_to(parent).as_posix()]=path
    for case in source['cases']:
        relative=f'evidence/real1/{case["label"]}/source.npz'
        assert sha(parent/relative)==parent_entries[relative]
        inputs['source_targets/'+case['label']+'/source.npz']=parent/relative
    shutil.copy2(__file__,evidence/'executed_package.py')
    result=freeze(root,repo,sources,evidence,inputs,validation)
    verify(root)
    save(repo/'research/carrier_transfer_v1_summary.json',dict(validation,**result))
    append_index(repo/'handoff/阶段索引.csv',[
        'carrier_transfer_v1','baselines/carrier_transfer_v1/manifest.json',result['file_count'],result['manifest_sha256'],
        '8known;90exactwaves;173520complex12x12Gram;independentSTFT/probes/perband;2figures',
        '670C-H82voice3F2/index exact;carrier-origin attribution not physical separation;no sound adoption',
        'research/载频来源与高频扩散V1.md | research/carrier_transfer_v1_summary.json',
        'baselines/carrier_transfer_v1/validation.json'])
    print(dict(result='carrier_transfer_frozen',**result))


if __name__=='__main__':
    main()
