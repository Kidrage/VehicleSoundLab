"""Archive the audible amplitude-only candidate and its known/source limitations."""
import argparse,subprocess
from pathlib import Path
from research_archive_v1 import load,save,sha,freeze,verify,append_index
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--stage',choices=['freeze','verify'],required=True);a=p.parse_args()
repo=Path(__file__).resolve().parents[1];root=a.workspace/'baselines/modal_texture_v1'
evidence=a.workspace/'references/analysis/modal_texture_v1';old=a.workspace/'baselines/idle_drive_v1'
c=load(old/'C_files_sha256.json');voices=load(old/'voice_files_sha256.json')
assert len(c)==569 and len(voices)==67
assert all(sha(repo/name)==digest for name,digest in {**c,**voices}.items())
subprocess.run(['git','diff','--exit-code','HEAD','--','modules','src','experiments','voices','CMakeLists.txt',
    'tools/fixed_source_v1','tools/idle_modal_v1','tools/idle_material_v1','tools/idle_texture_v2',
    'tools/sustain_osc_v1','tools/low_chirp_v1','tools/line_motion_v1'],cwd=repo,check=True,capture_output=True)
if a.stage=='freeze':
    known=load(evidence/'known1/report.json');trial=load(evidence/'trial1/report.json')
    audit=load(evidence/'audit1/report.json');review=load(evidence/'review1/report.json');check=load(evidence/'check1/report.json')
    assert known['result']=='known_local_model_limits_and_amplitude_proxy_checked' and known['controls_passed']
    fm=next(row for row in known['diagnostics'] if row['id']=='FM')
    assert fm['successful']==fm['eligible']==11 and fm['longest_fitted_track']==fm['longest_exact_tangent_track']==1
    assert trial['result']=='amplitude_only_fixed_idle_candidates_pending_listening' and len(trial['seeds'])==9
    assert trial['baseline_zero_FLOAT_exact'] and trial['modal_parameters_unchanged'] and not trial['holdout_read']
    assert audit['result']=='amplitude_proxy_and_all9_core_mix_renders_independently_rebuilt'
    assert audit['known_diagnosis']['windows']==33 and audit['zero_FLOAT_baseline_exact']
    assert review['result']=='single_player_core_amplitude_review_prepared' and review['common_gain']==1
    assert check['result']=='pass' and check['metadata_combinations']==19 and check['muted_playback']
    assert sha(repo/'tools/audit_modal_texture_v1.py')==sha(evidence/'audit1/executed_audit.py')
    assert sha(repo/'tools/review_modal_texture_v1.py')==sha(evidence/'review1/executed_review.py')
    assert sha(repo/'tools/check_modal_texture_v1.cjs')==sha(evidence/'check1/executed_check.cjs')
    sources={'tools/package_modal_texture_v1.py','tools/audit_modal_texture_v1.py','tools/review_modal_texture_v1.py',
        'tools/check_modal_texture_v1.cjs','tools/research_archive_v1.py','research/怠速主声线幅度纹理V1.md',
        'AGENTS.md','handoff/算法说明.md','handoff/开发留痕.md','handoff/研究续接.md'}
    for folder,report in [('known1',known),('trial1',trial)]:
        for name,digest in report['sources'].items():
            assert sha(evidence/folder/'exact_sources'/name)==digest==sha(repo/name)
            sources.add(name)
    for package in ['fixed_source_v1','idle_modal_v1','idle_material_v1','idle_texture_v2','low_chirp_v1']:
        path=repo/f'tools/{package}/__init__.py'
        if path.is_file():sources.add(path.relative_to(repo).as_posix())
    parent=a.workspace/'references/analysis/fixed_source_profiles_v1/trial1/F2_tailpipe'
    mono=a.workspace/'baselines/low_chirp_v1/evidence/noise1'
    inputs={'F2_training.wav':parent/'training.wav','fixed_source_profile.json':parent/'profile.json',
        'F2_holdout.wav':a.workspace/'baselines/idle_texture_v2/inputs/F2_holdout.wav',
        'mono_noise_report.json':mono/'report.json','mono_noise.npz':mono/'mono_noise.npz',
        'C_files_sha256.json':old/'C_files_sha256.json','voice_files_sha256.json':old/'voice_files_sha256.json',
        'data_workspace_AGENTS.md':a.workspace/'AGENTS.md'}
    assert load(mono/'report.json')['mono_eligible']==1
    validation=dict(schema='vsl.modal-texture-freeze/1',result='isolated_amplitude_candidate_audited_pending_listening',
        git_parent=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
        parent_profile_manifest_sha256=sha(a.workspace/'baselines/fixed_source_profiles_v1/manifest.json'),
        old_fine_manifest_sha256=sha(a.workspace/'baselines/idle_texture_v2/manifest.json'),
        mono_parent_manifest_sha256=sha(a.workspace/'baselines/low_chirp_v1/manifest.json'),
        sources_used=['F2_tailpipe'],training_seconds=[6,9],reference_seconds=[9,12],
        original_modes=13,original_mode_parameters_exact=True,old_fine_zero_FLOAT_exact=True,
        seed_count=3,amounts=[0,.5,1],all_seeds_retained=True,render_groups=9,
        independently_audited_known_windows=33,independently_audited_source_windows=141,
        nonlinear_FM_exact_tangent_link_longest=1,known_FM_amplitude_proxy_log_std=.011302653261574414,
        magnitude_is_proxy_not_physical_AM=True,mono_noise_counterexample_retained=True,
        source_std_cap=.12,source_alpha=trial['evidence']['alpha'],
        expected_squared_gain=1,phase_modulation=False,frequency_modulation=False,recorded_trajectory=False,room=False,
        maximum_FLOAT_sample_error=audit['maximum_FLOAT_sample_error'],source_coefficient_error=audit['source_coefficient_error'],
        common_review_gain=1,clips=19,browser_combinations=19,muted_browser_only=True,screenshots_viewed=True,
        url=review['url'],C_H_unchanged=569,voices_unchanged=67,C_tests_repeated=False,runtime_changed=False,
        timbre_accepted=False,shared_phase_qualified=False,actual_RPM_load=False,
        next='Judge core-AM benefit, pumping and weak-line noise before joint detail-AM or generic realtime adoption. Preserve original pending questions/common-phase qualification and complete state/spatial goal.')
    info=freeze(root,repo,sources,evidence,inputs,validation)
    save(repo/'research/modal_texture_v1_summary.json',dict(validation,freeze='baselines/modal_texture_v1',**info))
    append_index(repo/'handoff/阶段索引.csv',['modal_texture_v1','baselines/modal_texture_v1/manifest.json',
        str(info['file_count']),info['manifest_sha256'],
        'Known nonlinearFM exact tangent-link failure;generic magnitude proxy/PSD amplitude source;all3seeds x3amounts;QR+full replay;19muted browser cases',
        'Listening pending;not physicalAM/newsharedphase/RPM;569C-H/67voices/defaults unchanged;oldF2V2 question not duplicated',
        'research/怠速主声线幅度纹理V1.md | research/modal_texture_v1_summary.json',
        'baselines/modal_texture_v1/validation.json | baselines/modal_texture_v1/evidence/audit1/report.json'])
    print(dict(result='frozen',**info))
else:
    manifest=verify(root);summary=load(repo/'research/modal_texture_v1_summary.json')
    assert summary['manifest_sha256']==sha(root/'manifest.json')
    assert load(root/'inputs/C_files_sha256.json')==c and load(root/'inputs/voice_files_sha256.json')==voices
    assert sha(root/'source/tools/package_modal_texture_v1.py')==sha(Path(__file__))
    print(dict(result='verified',files=manifest['file_count'],C_H_unchanged=569,voices_unchanged=67))
