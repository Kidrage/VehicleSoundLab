"""Freeze low-line rejection diagnosis and the known layered-scale counterexample."""
import argparse,subprocess
from pathlib import Path
from research_archive_v1 import sha,load,save,freeze,verify,append_index
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--stage',choices=['freeze','verify'],required=True);a=p.parse_args()
repo=Path(__file__).resolve().parents[1];root=a.workspace/'baselines/low_peak_selection_v1'
evidence=a.workspace/'references/analysis/low_peak_selection_v1'
old=a.workspace/'baselines/idle_drive_v1'
c=load(old/'C_files_sha256.json');voices=load(old/'voice_files_sha256.json')
assert len(c)==569 and len(voices)==67
assert all(sha(repo/name)==digest for name,digest in {**c,**voices}.items())
subprocess.run(['git','diff','--exit-code','HEAD','--','modules','src','experiments','voices','CMakeLists.txt'],cwd=repo,check=True,capture_output=True)
if a.stage=='freeze':
    observation=load(evidence/'observe1/report.json');scales=load(evidence/'scale1/report.json')
    mixed=load(evidence/'mixture1/report.json');audit=load(evidence/'audit4/report.json');docs=load(evidence/'docs1/report.json')
    assert observation['result']=='all7_training_windows_and8_low_anchor_selection_paths_traced'
    assert scales['result']=='all7_training_cross_band_spectral_scales_observed'
    assert mixed['result']=='known_moving_layer_with_fixed_layer_rejects_whole_scale_rule'
    assert audit['result']=='selection_stages_and_all69156_real_and_mixture_scores_rebuilt' and audit['score_count']==69156
    assert audit['nonreference_qualified_windows']==0 and not audit['reference_self_match_is_validation']
    assert audit['absent_anchor_window_counts']=={'no_raw_maximum_in_anchor_radius':8,'raw_maxima_rejected':18}
    assert load(evidence/'audit1/report.json')['result']=='failed'
    assert docs['before_lines']==151 and docs['after_lines']==63
    assert sha(repo/'handoff/算法说明.md')==docs['after_sha256']
    assert sha(repo/'tools/audit_low_peak_selection_v1.py')==sha(evidence/'audit4/executed_audit.py')
    sources={'tools/audit_low_peak_selection_v1.py','tools/package_low_peak_selection_v1.py',
        'tools/research_archive_v1.py','research/低频漏提与分层缩放诊断V1.md',
        'AGENTS.md','handoff/算法说明.md','handoff/开发留痕.md','handoff/研究续接.md'}
    for folder,report in [('observe1',observation),('scale1',scales),('mixture1',mixed)]:
        for name,digest in report['sources'].items():
            assert sha(evidence/folder/'exact_sources'/name)==digest==sha(repo/name)
            sources.add(name)
    parent=a.workspace/'references/analysis/fixed_source_profiles_v1/trial1/A_exterior_low_rev'
    inputs={name:parent/name for name in ['training.wav','fit_evidence.json','profile.json']}
    inputs.update({'data_workspace_AGENTS.md':a.workspace/'AGENTS.md','C_files_sha256.json':old/'C_files_sha256.json',
        'voice_files_sha256.json':old/'voice_files_sha256.json'})
    validation=dict(schema='vsl.low-peak-selection-freeze/1',result='source_selection_and_layered_scale_limits_verified_no_new_voice',
        git_parent=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
        parent_manifest_sha256=sha(a.workspace/'baselines/fixed_source_profiles_v1/manifest.json'),
        training_seconds=[208,210],holdout_read=False,anchor_observations=56,supported=30,absent=26,
        absent_window_counts=audit['absent_anchor_window_counts'],rejected_raw_peak_counts=audit['rejected_raw_maximum_counts'],
        known_continuous_chirp_fixed_anchor_support=3/7,
        nonreference_whole_scale_supported=0,real_whole_scale_NOT_engine_phase=True,
        known_tonal_shift=128,known_mixed_global_shift=0,known_mixed_band_shifts=[128,0,0],
        independently_rebuilt_scores=69156,maximum_score_error=audit['maximum_score_error'],
        audit1_parse_failure_retained=True,intermediate_audits_retained=['audit2','audit3'],final_audit='audit4',
        algorithm_document=docs,new_WAV=False,new_profile=False,C_H_unchanged=569,voices_unchanged=67,
        runtime_changed=False,C_tests_repeated=False,shared_phase_qualified=False,measured_RPM_load=False,
        next='Validate observed moving-tonal vs fixed-structure selection on known mixtures before real A; keep F2V2 listening pending.')
    info=freeze(root,repo,sources,evidence,inputs,validation)
    save(repo/'research/low_peak_selection_v1_summary.json',dict(validation,freeze='baselines/low_peak_selection_v1',**info))
    append_index(repo/'handoff/阶段索引.csv',['low_peak_selection_v1','baselines/low_peak_selection_v1/manifest.json',
        str(info['file_count']),info['manifest_sha256'],
        'All7A windows/8low anchors exact selection trace; dense scale controls; known moving+fixed mixture counterexample;69156scores independently rebuilt;parse failure retained',
        'No new voice;6nonreference whole scales rejected;569C-H/67voices unchanged; old shared-phase and listening pending',
        'research/低频漏提与分层缩放诊断V1.md | research/low_peak_selection_v1_summary.json',
        'baselines/low_peak_selection_v1/validation.json | baselines/low_peak_selection_v1/evidence/audit4/report.json'])
    print(dict(result='frozen',**info))
else:
    m=verify(root);s=load(repo/'research/low_peak_selection_v1_summary.json')
    assert s['manifest_sha256']==sha(root/'manifest.json')
    assert load(root/'inputs/C_files_sha256.json')==c and load(root/'inputs/voice_files_sha256.json')==voices
    assert sha(root/'source/tools/package_low_peak_selection_v1.py')==sha(Path(__file__))
    print(dict(result='verified',files=m['file_count'],C_H_unchanged=569,voices_unchanged=67))
