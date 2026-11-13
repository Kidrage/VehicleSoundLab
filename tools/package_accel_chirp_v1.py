"""Freeze native F3 fits, failures, independent audit and conditional predictions."""
import argparse,subprocess
from pathlib import Path
from research_archive_v1 import sha,load,save,freeze,verify,append_index
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--stage',choices=['freeze','verify'],required=True);a=p.parse_args()
repo=Path(__file__).resolve().parents[1];evidence=a.workspace/'references/analysis/accel_chirp_v1'
root=a.workspace/'baselines/accel_chirp_v1';parent=a.workspace/'baselines/fine_idle_drive_v1'
old=load(parent/'inputs/C_files_sha256.json');voices=load(parent/'inputs/voice_files_sha256.json')
assert len(old)==600 and len(voices)==67 and all(sha(repo/n)==h for n,h in {**old,**voices}.items())
if a.stage=='verify':verify(root);print('freeze verified');raise SystemExit
observed=load(evidence/'observe1/report.json');audit=load(evidence/'audit3/report.json')
assert observed['result']=='native_chirp_fits_and_conditional_parameter_checks_complete'
assert audit['result']=='native_waveforms_support_and_training_only_predictions_verified'
assert audit['windows']==54 and audit['lines']==1105 and audit['predictions']==148
assert audit['observation_report_sha256']==sha(evidence/'observe1/report.json')
assert all(load(evidence/name/'report.json')['result']=='failed' for name in ['audit1','audit2'])
for folder in ['check1','observe1']:
    for name,h in load(evidence/folder/'report.json')['sources'].items():
        assert sha(evidence/folder/'exact_sources'/name)==h
        if folder=='observe1':assert sha(repo/name)==h
plot=load(evidence/'plot1/report.json');assert plot['observation_report_sha256']==sha(evidence/'observe1/report.json')
assert plot['image_sha256']==sha(repo/'research/accel_chirp_v1_diagnostics.png')
sources=list(observed['sources'])+['tools/audit_accel_chirp_v1.py','tools/plot_accel_chirp_v1.py','tools/package_accel_chirp_v1.py',
    'research/加速独立声线参数V1.md','research/accel_chirp_v1_diagnostics.png','AGENTS.md','handoff/研究续接.md','handoff/开发留痕.md']
validation=dict(schema='vsl.accel-chirp-freeze/1',result='native_independent_chirps_checked_fixed_amplitudes_insufficient',
    parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    observations=observed['observations'],summaries=audit['summaries'],audit_windows=54,audit_lines=1105,conditional_predictions=148,
    waveform_error=audit['maximum_waveform_error'],support_error=audit['maximum_support_error'],
    known_nonlinear_FM_eligibility_limitation=True,earlier_null_ratio_and_grouping_audit_failures_preserved=True,
    source_or_common_phase_or_RPM_identity=False,pristine_holdout=False,profile_or_audio_exported=False,
    C_H_unchanged=600,voices_unchanged=67,old61CTest_repeated=False,plot_visually_reviewed=True,
    next='Model observed amplitude/state changes and omitted LF/HF structure before an acceleration recipe; idle quality is current human priority.')
inputs={'C_files_sha256.json':parent/'inputs/C_files_sha256.json','voice_files_sha256.json':parent/'inputs/voice_files_sha256.json',
    'parent_manifest.json':a.workspace/'baselines/accel_ridges_v1/manifest.json','data_workspace_AGENTS.md':a.workspace/'AGENTS.md'}
result=freeze(root,repo,sources,evidence,inputs,validation);verify(root)
save(repo/'research/accel_chirp_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['accel_chirp_v1','baselines/accel_chirp_v1/manifest.json',result['file_count'],result['manifest_sha256'],
    'All48native F3tiles;54known/real models1105lines and148conditional predictions independently checked',
    '15of29reference lines meet both diagnostics;fixed amplitudes insufficient;no source/commonphase/RPM/timbre identity;600C-H67voices exact',
    'research/加速独立声线参数V1.md | research/accel_chirp_v1_summary.json','baselines/accel_chirp_v1/validation.json'])
print(result)
