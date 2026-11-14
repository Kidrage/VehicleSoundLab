"""Freeze actual frozen-bus variation evidence and both numerical audit versions."""
import argparse,csv,shutil,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--stage',choices=['freeze','verify'],required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
from research_archive_v1 import load,save,sha,freeze,verify,append_index
root=a.workspace/'baselines/idle_variation_budget_v1'
if a.stage=='verify':print(verify(root)['file_count']);raise SystemExit
evidence=a.workspace/'references/analysis/idle_variation_budget_v1'
run=load(evidence/'observe1/report.json');failed=load(evidence/'audit1/report.json')
audit=load(evidence/'audit2/report.json');assessment=load(evidence/'assessment2/report.json')
assert run['result']=='actual_idle_bus_variation_observed_pending_audit' and len(run['cases'])==153
assert failed['result']=='failed' and 'all_native_measured_phasors' in failed['error']
assert audit['result']=='passed' and audit['QR_factorizations']==17748 and len(audit['cases'])==153
assert audit['input_sha256']==sha(evidence/'observe1/report.json')
assert assessment['result']=='actual_idle_bus_variation_assessed' and assessment['input_sha256']==sha(evidence/'observe1/report.json')
assert assessment['audit_sha256']==sha(evidence/'audit2/report.json')
sources=set()
for path,digest in run['sources'].items():
    assert sha(repo/path)==digest==sha(evidence/'observe1/exact_sources'/path);sources.add(path)
for path,digest in run['inputs'].items():assert sha(path)==digest
for row in run['cases']:assert sha(evidence/'observe1'/row['file'])==row['sha256']
for path,folder,name in [('tools/audit_idle_variation_budget_v1.py','audit2','executed_auditor.py'),
    ('tools/assess_idle_variation_budget_v1.py','assessment2','executed_assessment.py')]:
    assert sha(repo/path)==sha(evidence/folder/name);sources.add(path)
for key,name in [('figure','research/idle_variation_budget_v1.png'),('coordinate_figure','research/idle_variation_budget_v1_coordinates.png')]:
    figure=assessment[key];assert sha(evidence/'assessment2'/figure['file'])==figure['sha256']
    shutil.copy2(evidence/'assessment2'/figure['file'],repo/name);sources.add(name)
plan='research/idle_variation_budget_v1_coordinate_diagnosis.json'
assert sha(repo/plan)==assessment['coordinate_plan_sha256']==sha(evidence/'assessment2'/Path(plan).name);sources.add(plan)
ch=list(csv.reader((repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig')))
assert len(ch)==620 and all(sha(repo/row[0])==row[4] for row in ch[1:])
voices_path=a.workspace/'baselines/idle_microtexture_c_v1/inputs/voice_files_sha256.json';voices=load(voices_path)
assert len(voices)==67 and all(sha(repo/path)==digest for path,digest in voices.items())
sources.update(['tools/package_idle_variation_budget_v1.py','research/怠速起伏分层核查V1.md','AGENTS.md','handoff/研究续接.md','handoff/开发留痕.md'])
shutil.copy2(repo/'AGENTS.md',a.workspace/'AGENTS.md')
inputs={'previous_source_inverse_manifest.json':a.workspace/'baselines/idle_conditional_gain_v1/manifest.json',
    'actual_audio_parent_manifest.json':a.workspace/'baselines/idle_local_partition_v1/manifest.json',
    'known_forward_manifest.json':a.workspace/'baselines/joint_osc_forward_v1/manifest.json',
    'C_H_index.csv':repo/'handoff/C文件索引.csv','original_voice_hashes.json':voices_path}
full=assessment['groups']['1.0_measured_acoustic']
validation=dict(schema='vsl.idle-variation-budget-freeze/1',result='actual_bus_variation_located_not_new_voice',
    parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    previous_goal_turn_progress='6124b37 froze real native conditional mean inverse and rejected3boundarysource; clean verified before this stage',
    source_control_cases=8,actual_generated_blocks=72,phase_bases_per_block=2,known_case=1,total_cases=153,
    actual_main_mix_FLOAT_takes_reused_not_regenerated=True,all51signed6x6covariance_budgets=True,
    signed_cross_and_above100percent_marginals_preserved=True,no_log_variance_additivity=True,
    all153cases_independent_QR_factorizations=17748,
    maximum_QR_coefficient_error_FS=audit['errors']['all_weighted_QR_coefficients_FS'],
    maximum_procedural_phasor_error=audit['errors']['all_native_procedural_phasors'],
    maximum_measured_phasor_error=audit['errors']['all_native_measured_phasors'],
    initial_NumPy_FFT_unit_phase_gate_failure_preserved=True,auditor_uses_manual_Hilbert_with_SciPyFFT_backend_no_gate_change=True,
    old_NumPy_FFT_difference_diagnosis=audit['old_numpy_FFT_comparison'],
    fullAM_measured_pooled_real_std=full['within_block_pooled_std'][:3],
    fullAM_measured_real_rho100ms=full['rho_100_200_500ms'][0][:3],
    fullAM_measured_main_detail_cross_variance_ratios=[row[:3] for row in full['pooled_signed_main_detail_cross_variance_ratios']],
    pooled_within_block_statistics_NOT_confidence_or_native_innovation_parameters=True,
    source_physical_main_detail_separation=False,both_figures_viewed=True,new_audio_or_model=False,
    original_assessment1_kept_coordinate_diagnosis_explicitly_subsequent=True,
    known_vs_measured_quadrature_gap_and_artificial_cancellation_retained=True,
    fullAM_known_imag_std=assessment['groups']['1.0_procedural']['within_block_pooled_std'][3:],
    fullAM_measured_imag_std=full['within_block_pooled_std'][3:],
    old619C_H_and67voices_exact=True,moving35_changed=False,runtime_changed=False,listening_improvement_claimed=False,
    next=assessment['next'])
result=freeze(root,repo,sources,evidence,inputs,validation);verify(root)
save(repo/'research/idle_variation_budget_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['idle_variation_budget_v1','baselines/idle_variation_budget_v1/manifest.json',result['file_count'],result['manifest_sha256'],
    '72actualblocks2phasebases+8source+1known;51signed6x6;17748QR',
    '75mainTOOslow/quiet;187detaildominant;signedcross;619C-H67voicesexact;noaudio/C',
    'research/怠速起伏分层核查V1.md | research/idle_variation_budget_v1_summary.json','baselines/idle_variation_budget_v1/validation.json'])
print(result)
