"""Freeze phase/magnitude source evidence without promoting an instantaneous gain law."""
import argparse,csv,shutil,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--stage',choices=['freeze','verify'],required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
from research_archive_v1 import load,save,sha,freeze,verify,append_index

root=a.workspace/'baselines/idle_amp_phase_link_v1'
if a.stage=='verify':print(verify(root)['file_count']);raise SystemExit
evidence=a.workspace/'references/analysis/idle_amp_phase_link_v1'
names=['observe1','audit1','stream1','stream_audit1','assessment1','assessment2','assessment_audit1']
reports={name:load(evidence/name/'report.json') for name in names}
assert reports['observe1']['result']=='frozen_AM_relative_phase_relationship_observed' and len(reports['observe1']['cases'])==8
assert reports['stream1']['result']=='existing_full_phase_streams_window_law_probed'
for name in ['audit1','stream_audit1','assessment_audit1']:assert reports[name]['result']=='passed'
assert reports['assessment_audit1']['assessment_sha256']==sha(evidence/'assessment2/report.json')
sources=set()
for folder in ['observe1','stream1']:
    for path,digest in reports[folder]['inputs'].items():assert sha(path)==digest
    for path,digest in reports[folder]['sources'].items():
        assert sha(repo/path)==digest==sha(evidence/folder/'exact_sources'/path);sources.add(path)
for row in reports['observe1']['cases']+reports['observe1']['frozen_observer_controls']:
    assert sha(evidence/'observe1'/row['file'])==row['sha256']
for row in reports['observe1']['evaluations']:
    assert sha(evidence/'observe1'/row['prediction_file'])==row['prediction_sha256']
for row in reports['stream1']['streams']:assert sha(evidence/'stream1'/row['file'])==row['sha256']
executed=[('tools/audit_idle_amp_phase_link_v1.py','audit1','executed_auditor.py'),
    ('tools/audit_idle_amp_phase_stream_v1.py','stream_audit1','executed_auditor.py'),
    ('tools/assess_idle_amp_phase_link_v1.py','assessment2','executed_assessment.py'),
    ('tools/audit_idle_amp_phase_assessment_v1.py','assessment_audit1','executed_auditor.py')]
for path,folder,copy in executed:assert sha(repo/path)==sha(evidence/folder/copy);sources.add(path)
for folder in ['assessment1','assessment2']:
    figure=reports[folder]['figure'];assert sha(evidence/folder/figure['file'])==figure['sha256']
shutil.copy2(evidence/'assessment2/evidence.png',repo/'research/idle_amp_phase_link_v1.png')
sources.add('research/idle_amp_phase_link_v1.png')
ch=list(csv.reader((repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig')))
assert len(ch)==620 and all(sha(repo/row[0])==row[4] for row in ch[1:])
voices_path=a.workspace/'baselines/idle_microtexture_c_v1/inputs/voice_files_sha256.json'
voices=load(voices_path);assert len(voices)==67 and all(sha(repo/path)==digest for path,digest in voices.items())
sources.update(['tools/package_idle_amp_phase_link_v1.py','research/怠速力度与相位联动V1.md',
    'AGENTS.md','handoff/研究续接.md','handoff/开发留痕.md'])
shutil.copy2(repo/'AGENTS.md',a.workspace/'AGENTS.md')
inputs={name+'_manifest.json':a.workspace/'baselines'/name/'manifest.json' for name in
    ['idle_local_partition_v1','idle_phase_amplitude_v1','idle_phase_recipe_v1']}
inputs.update(C_H_index=repo/'handoff/C文件索引.csv',original_voice_hashes=voices_path)
assessment=reports['assessment2'];source=reports['observe1']
validation=dict(schema='vsl.idle-amp-phase-link-freeze/1',result='source_relationship_NOT_new_audio_or_C',
    parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    all8frozen_source_control_portions=True,original116windows200ms20ms=True,
    source_CHECK_previously_inspected=True,source_QR_condition=assessment['source_model_condition'],
    source_CHECK_total_MSE_reductions=assessment['source_CHECK_MSE_reductions'],
    source_CHECK_error_variance_reductions=assessment['source_MSE_decomposition'][1]['fractional_error_variance_reduction'],
    source187_fluctuation_error_worse_despite_total_MSE_improvement=True,
    all8x51x7x7covariance_independently_audited=True,all4models_and8predictions_audited=True,
    full_existing_phase_streams=[(row['seed'],row['seconds'],row['windows']) for row in reports['stream1']['streams']],
    all11298native_windows_and_global_bounds_audited=True,
    phase_feature_box_outside_fractions=assessment['full_stream_feature_box_outside'],
    both_six_panel_figure_versions_preserved=True,final_figure_viewed=True,
    window_regression_NOT_instantaneous_gain=True,physical_AM_PM_or_RPM_identified=False,
    source_PCM_or_new_audio_or_gain_trajectory_exported=False,old619C_H_and67voices_exact=True,
    accepted_moving35_changed=False,runtime_changed=False,listening_accepted=False,
    next='Pending idle allocation hearing before C. If continuing source work: known joint-source forward window consistency and power budget before native AM/PM synthesis;75/112 motivate a hypothesis but187 is a counterexample. No blind all-line coupling/AM/pad boost, preserve phase qualifications/full goal.')
result=freeze(root,repo,sources,evidence,inputs,validation);verify(root)
save(repo/'research/idle_amp_phase_link_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['idle_amp_phase_link_v1','baselines/idle_amp_phase_link_v1/manifest.json',result['file_count'],result['manifest_sha256'],
    '8sources4fits/8predictions;8x51x7x7;11298nativewindows;MSEdecomposition',
    '75/112link;187fluctuationworse;windowlawNOTnativegain;619C-H67voicesexact',
    'research/怠速力度与相位联动V1.md | research/idle_amp_phase_link_v1_summary.json','baselines/idle_amp_phase_link_v1/validation.json'])
print(result)
