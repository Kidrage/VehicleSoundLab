"""Freeze all source-only amplitude models, negative transfers and scalar audit."""
import argparse,subprocess,shutil
from pathlib import Path
from research_archive_v1 import load,save,sha,freeze,verify,append_index
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--stage',choices=['freeze','verify'],required=True);a=p.parse_args()
repo=Path(__file__).resolve().parents[1];root=a.workspace/'baselines/accel_amplitude_v1'
if a.stage=='verify':verify(root);print('freeze verified');raise SystemExit
evidence=a.workspace/'references/analysis/accel_amplitude_v1';input=evidence/'observe1'
observed=load(input/'report.json');audit=load(evidence/'audit1/report.json');plot=load(evidence/'plot1/report.json')
assert observed['result']=='all6_cross_passage_amplitude_checks_complete'
assert audit['result']=='all_source_models_native_matches_and6_transfer_reports_verified'
assert audit['models']==55 and audit['predicted_rows']==532 and audit['totals']['compared']==74
assert audit['totals']['linear_better']==32 and len(observed['pairs'])==len(audit['pairs'])==6
assert audit['input_report_sha256']==plot['input_report_sha256']==sha(input/'report.json')
assert audit['maximum_model_error']<1e-10 and audit['maximum_prediction_error']<1e-10 and audit['maximum_score_error']<1e-11
for name,h in observed['sources'].items():assert sha(input/'exact_sources'/name)==h==sha(repo/name)
known=load(input/'known_controls.json')
assert known['powerlaw_slope_error']<1e-12 and known['powerlaw_amplitude_error']<1e-14
assert known['identical_noise_self_match']['supported']
invariants=a.workspace/'baselines/idle_microtexture_c_v1/inputs'
for filename,count in [('C_files_sha256.json',612),('voice_files_sha256.json',67)]:
    table=load(invariants/filename);assert len(table)==count
    for name,h in table.items():assert sha(repo/name)==h,name
for image,target in [('transfer_errors.png','accel_amplitude_v1_diagnostics.png'),('primary_laws.png','accel_amplitude_v1_primary.png')]:
    assert sha(evidence/'plot1'/image)==plot['images'][image];shutil.copy2(evidence/'plot1'/image,repo/'research'/target)
sources=list(observed['sources'])+['tools/audit_accel_amplitude_v1.py','tools/plot_accel_amplitude_v1.py','tools/package_accel_amplitude_v1.py',
    'research/加速幅度跨片段验证V1.md','research/accel_amplitude_v1_diagnostics.png','research/accel_amplitude_v1_primary.png',
    'AGENTS.md','handoff/研究续接.md','handoff/开发留痕.md']
inputs={'C_files_sha256.json':invariants/'C_files_sha256.json','voice_files_sha256.json':invariants/'voice_files_sha256.json',
    'chirp_manifest.json':a.workspace/'baselines/accel_chirp_v1/manifest.json',
    'ridge_manifest.json':a.workspace/'baselines/accel_ridges_v1/manifest.json','data_workspace_AGENTS.md':a.workspace/'AGENTS.md'}
for name in observed['plan']['segments']:
    fits=a.workspace/'baselines/accel_chirp_v1/evidence/observe1'/name/'fits.json'
    assert sha(fits)==observed['parent_fits_sha256'][str(fits)]
    inputs[name+'_fits.json']=fits
    inputs[name+'_ridge.json']=a.workspace/'baselines/accel_ridges_v1/evidence/observe2'/(name+'.json')
validation=dict(schema='vsl.accel-amplitude-freeze/1',result='scale_only_amplitude_not_consistently_better',
    parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    models=55,ordered_pairs=6,predictions=532,totals=audit['totals'],pair_summaries=observed['pairs'],
    maximum_model_error=audit['maximum_model_error'],maximum_prediction_error=audit['maximum_prediction_error'],maximum_score_error=audit['maximum_score_error'],
    all_excluded_missing_ambiguous_and_out_of_range_retained=True,models_source_only=True,
    allpassages_previously_inspected=True,observed_target_eligibility_and_whole_source_guide=True,
    physical_load_or_RPM_or_source_identified=False,phase_or_waveform_prediction=False,
    original_common_phase_qualification_still_required=True,profile_or_audio_exported=False,
    C_H_unchanged=612,old_voices_unchanged=67,old61_driving_tests_repeated=False,
    both_plots_viewed=True,idle_listening_question_repeated=False,
    next='Omitted LF/HF structure and correspondence/model mismatch before acceleration recipe; no higher-degree or range sweep, invented LF/HF or actual RPM/load mapping.')
result=freeze(root,repo,sources,evidence,inputs,validation);verify(root)
save(repo/'research/accel_amplitude_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['accel_amplitude_v1','baselines/accel_amplitude_v1/manifest.json',result['file_count'],result['manifest_sha256'],
    '55source models/all6native matches/532conditionals/74reference comparisons independently checked',
    'Loglinear better than geometric32of74;NOT complete acceleration/RPM/load/phase/timbre;612C-H67voices exact',
    'research/加速幅度跨片段验证V1.md | research/accel_amplitude_v1_summary.json','baselines/accel_amplitude_v1/validation.json'])
print(result)
