"""Freeze conditional expected75 qualification, source outcomes and original runtime invariants."""
import argparse,csv,shutil,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--stage',choices=['freeze','verify'],required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
from research_archive_v1 import load,save,sha,freeze,verify,append_index
root=a.workspace/'baselines/idle75_expected_v1'
if a.stage=='verify':print(verify(root)['file_count']);raise SystemExit
evidence=a.workspace/'references/analysis/idle75_expected_v1'
run=load(evidence/'fit1/report.json');audit=load(evidence/'audit1/report.json');assessment=load(evidence/'assessment1/report.json')
assert run['result']=='conditional_expected75_moments_fitted_pending_audit'
assert len(run['models'])==4 and len(run['CHECK'])==4
assert len(run['controls']['finite_white_and_quadrature'])==4 and len(run['controls']['native_coefficients'])==12
assert len(run['controls']['grid_moments'])==4
for label in ['same_grid','independent_fine_grid']:assert run['known'][label]['available'] and run['known'][label]['maximum_parameter_error']<1e-5
assert audit['result']=='conditional_expected75_operator_and_terminal_moments_independently_checked'
assert len(audit['operators'])==6 and audit['input_sha256']==sha(evidence/'fit1/report.json')
assert assessment['result']=='conditional_expected75_fit_assessed'
assert assessment['input_sha256']==sha(evidence/'fit1/report.json') and assessment['audit_sha256']==sha(evidence/'audit1/report.json')
sources=set()
for path,digest in run['sources'].items():
    assert sha(repo/path)==digest==sha(evidence/'fit1/exact_sources'/path);sources.add(path)
for path,digest in run['inputs'].items():assert sha(path)==digest
for path,folder,name in [('tools/audit_idle75_expected_v1.py','audit1','executed_auditor.py'),
    ('tools/assess_idle75_expected_v1.py','assessment1','executed_assessment.py')]:
    assert sha(repo/path)==sha(evidence/folder/name);sources.add(path)
path='research/idle75_expected_v1_audit_plan.json'
assert sha(repo/path)==audit['plan_sha256']==sha(evidence/'audit1'/Path(path).name);sources.add(path)
figure=assessment['figure'];assert sha(evidence/'assessment1'/figure['file'])==figure['sha256']
shutil.copy2(evidence/'assessment1'/figure['file'],repo/'research/idle75_expected_v1.png');sources.add('research/idle75_expected_v1.png')
ch=list(csv.reader((repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig')))
assert len(ch)==620 and all(sha(repo/row[0])==row[4] for row in ch[1:])
voices_path=a.workspace/'baselines/idle_microtexture_c_v1/inputs/voice_files_sha256.json';voices=load(voices_path)
assert len(voices)==67 and all(sha(repo/path)==digest for path,digest in voices.items())
sources.update(['tools/package_idle75_expected_v1.py','research/怠速期望统计拟合V1.md','AGENTS.md','handoff/研究续接.md','handoff/开发留痕.md'])
shutil.copy2(repo/'AGENTS.md',a.workspace/'AGENTS.md')
inputs={'previous_clock_manifest.json':a.workspace/'baselines/idle75_clock_v1/manifest.json',
    'variation_manifest.json':a.workspace/'baselines/idle_variation_budget_v1/manifest.json',
    'actual_audio_manifest.json':a.workspace/'baselines/idle_local_partition_v1/manifest.json',
    'C_H_index.csv':repo/'handoff/C文件索引.csv','original_voice_hashes.json':voices_path}
validation=dict(schema='vsl.idle75-expected-freeze/1',result='known_expected_inverse_passed_real_source_recorded',
    parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    conditional_expected75_only_NOT_full_phase_estimator_ensemble=True,
    full_signed64tap_covariance_all16interpolation_pairs=True,exact_window_sample_mean_centering=True,
    controls=assessment['known_recovery_errors'],native_compression_error=assessment['maximum_native_coefficient_compression_error'],
    grid_comparison_relative_error=assessment['maximum_grid_relative_moment_error'],
    independent_all6operators_all12native_and_terminal_moments=True,
    intermediate_trace_kernels_all_independently_replayed=False,all_trace_costs_independently_checked=True,
    source_optimizer_available=run['source_available'],source_models=assessment['models'],source_adoption=assessment['adoption'],
    new_audio=False,new_C=False,figure_viewed=True,
    old619C_H_and67voices_exact=True,moving35_changed=False,runtime_changed=False,listening_improvement_claimed=False,
    next=assessment['next']+' Existing idle allocation audition pending/no duplicate;187detail separate; original phase qualifications/full driving/multi-engine/stereo7.1.4 goal active.')
result=freeze(root,repo,sources,evidence,inputs,validation);verify(root)
save(repo/'research/idle75_expected_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['idle75_expected_v1','baselines/idle75_expected_v1/manifest.json',result['file_count'],result['manifest_sha256'],
    'knownExpected2inversePASS;4source/controlTRAIN;6operators12native',
    'conditionalNOTphaseEstimatorEnsemble;noaudio/C;619C-H67voicesexact',
    'research/怠速期望统计拟合V1.md | research/idle75_expected_v1_summary.json','baselines/idle75_expected_v1/validation.json'])
print(result)
