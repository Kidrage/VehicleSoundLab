"""Freeze known joint forward controls, failed import, inverse and power evidence."""
import argparse,csv,shutil,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--stage',choices=['freeze','verify'],required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
from research_archive_v1 import load,save,sha,freeze,verify,append_index

root=a.workspace/'baselines/joint_osc_forward_v1'
if a.stage=='verify':print(verify(root)['file_count']);raise SystemExit
evidence=a.workspace/'references/analysis/joint_osc_forward_v1'
failed=load(evidence/'run1/report.json');run=load(evidence/'run2/report.json')
audit=load(evidence/'audit1/report.json');assessment=load(evidence/'assessment1/report.json')
assert failed['result']=='failed_before_output_directory_creation' and not failed['algorithm_controls_executed']
assert (evidence/'run1/executed_main.py').is_file() and (evidence/'run1/stderr.txt').is_file()
assert run['result']=='known_joint_forward_inverse_and_moments_pending_audit'
assert audit['result']=='passed' and audit['QR_windows']==3016 and audit['input_sha256']==sha(evidence/'run2/report.json')
assert assessment['result']=='known_joint_forward_evidence_assessed'
assert assessment['input_sha256']==sha(evidence/'run2/report.json') and assessment['audit_sha256']==sha(evidence/'audit1/report.json')
assert run['measured_no_AM_gates_passed'] and run['fit']['known_latent_inputs_supplied']
assert len(run['streams'])==3 and len(run['cases'])==10 and len(run['power'])==19 and len(run['predictions'])==6
sources=set()
for path,digest in run['sources'].items():
    assert sha(repo/path)==digest==sha(evidence/'run2/exact_sources'/path);sources.add(path)
for row in run['streams']+run['cases']:assert sha(evidence/'run2'/row['file'])==row['sha256']
for path,folder,name in [('tools/audit_joint_osc_forward_v1.py','audit1','executed_auditor.py'),
    ('tools/assess_joint_osc_forward_v1.py','assessment1','executed_assessment.py')]:
    assert sha(repo/path)==sha(evidence/folder/name);sources.add(path)
figure=assessment['figure'];assert sha(evidence/'assessment1'/figure['file'])==figure['sha256']
shutil.copy2(evidence/'assessment1'/figure['file'],repo/'research/joint_osc_forward_v1.png');sources.add('research/joint_osc_forward_v1.png')
ch=list(csv.reader((repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig')))
assert len(ch)==620 and all(sha(repo/row[0])==row[4] for row in ch[1:])
voices_path=a.workspace/'baselines/idle_microtexture_c_v1/inputs/voice_files_sha256.json';voices=load(voices_path)
assert len(voices)==67 and all(sha(repo/path)==digest for path,digest in voices.items())
sources.update(['tools/package_joint_osc_forward_v1.py','research/联合OSC前向验证V1.md','AGENTS.md','handoff/研究续接.md','handoff/开发留痕.md'])
shutil.copy2(repo/'AGENTS.md',a.workspace/'AGENTS.md')
inputs={'previous_source_link_manifest.json':a.workspace/'baselines/idle_amp_phase_link_v1/manifest.json',
    'C_H_index.csv':repo/'handoff/C文件索引.csv','original_voice_hashes.json':voices_path}
validation=dict(schema='vsl.joint-osc-forward-freeze/1',result='known_input_forward_inverse_NOT_real_source_or_C_voice',
    parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    missing_threadpoolctl_import_failure_preserved=True,no_math_or_gate_relaxation=True,
    full_covariance_all240fractions_and_stationary_prehistory_checked=True,
    all3six_second_native_streams_and10known_diagnostic_waveforms_audited=True,
    all19known_phase_and19measured_phase_portions_checked=True,independent_QR_factorizations=3016,
    known_input_parameters=run['fit']['parameters'],maximum_parameter_error=run['fit']['maximum_parameter_error'],
    known_input_Jacobian_condition=run['fit']['Jacobian_condition'],known_input_fit_evaluations=run['fit']['nfev'],
    maximum_predicted_CHECK_window_log_error=assessment['maximum_predicted_CHECK_window_log_error'],
    measured_noAM_original_gates_passed=True,Gaussian9power5quadrature_all13x13_and_Hann_power_checked=True,
    maximum_independent_QR_coefficient_error_FS=audit['errors']['all_QR_coefficients'],
    maximum_quadrature_complex_moment_error=audit['errors']['all_quadrature_moments'],
    realized_over_expected_power_range=assessment['realized_power_ratio_range'],
    first_seed_naive_window_errors=assessment['first_seed_joint_TRAIN_naive_relative_errors'],
    gain_E_square_normalization_NOT_exact_per_take_whole_wave_RMS=True,
    figure_viewed=True,known_latent_inputs_supplied=True,real_engine_hidden_excitation_recovered=False,
    new_source_voice_or_audition=False,old619C_H_and67voices_exact=True,moving35_changed=False,runtime_changed=False,
    next='Source-constrained joint statistics with forward observation and latent uncertainty;75/112 first,187counterexample. Pending idle hearing before C voice adoption. No all-line coupling/blind AM, preserve original phase qualifications/full driving/multi-engine/7.1.4 goal.')
result=freeze(root,repo,sources,evidence,inputs,validation);verify(root)
save(repo/'research/joint_osc_forward_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['joint_osc_forward_v1','baselines/joint_osc_forward_v1/manifest.json',result['file_count'],result['manifest_sha256'],
    '3x6s5D/10knownwaves;3016QR;known2paraminverse;13x13MGF/quadrature/Hann',
    'knowninputsNOTrealengine;gainE2NOTtakeRMS;619C-H67voicesexact;noC/listening',
    'research/联合OSC前向验证V1.md | research/joint_osc_forward_v1_summary.json','baselines/joint_osc_forward_v1/validation.json'])
print(result)
