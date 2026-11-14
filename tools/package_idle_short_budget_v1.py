"""Freeze complete short-window bus budgets and source near75spectra, no voice adoption."""
import argparse,csv,shutil,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--stage',choices=['freeze','verify'],required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
from research_archive_v1 import load,save,sha,freeze,verify,append_index
root=a.workspace/'baselines/idle_short_budget_v1'
if a.stage=='verify':print(verify(root)['file_count']);raise SystemExit
evidence=a.workspace/'references/analysis/idle_short_budget_v1'
run=load(evidence/'observe1/report.json');audit=load(evidence/'audit1/report.json');assessment=load(evidence/'assessment1/report.json');tables=load(evidence/'summary_audit1/report.json')
assert run['result']=='complete_idle_short_bus_and_near75_budget_observed' and len(run['cases'])==168 and len(run['spectra'])==56
assert audit['result']=='all_idle_short_buses_and_native_residual_spectra_independently_checked'
assert audit['window_QR']==17052 and audit['global_QR']==56 and audit['known_global_QR']==2
assert audit['input_sha256']==assessment['input_sha256']==sha(evidence/'observe1/report.json')
assert tables['result']=='all_pooled_short_idle_tables_independently_verified'
assert tables['audit_sha256']==sha(evidence/'audit1/report.json') and tables['assessment_sha256']==sha(evidence/'assessment1/report.json')
assert tables['pooled_groups']==6 and tables['spectral_groups']==4
assert audit['known_AM_projection_surviving_rms']>.003 and 'NOT executed before original' in audit['AM_projection_counterexample_timing']
sources=set()
for path,digest in run['sources'].items():
    assert sha(repo/path)==digest==sha(evidence/'observe1/exact_sources'/path);sources.add(path)
for path,digest in run['inputs'].items():assert sha(path)==digest
for row in run['cases']+run['spectra']:assert sha(evidence/'observe1'/row['file'])==row['sha256']
for path,folder,name in [('tools/audit_idle_short_budget_v1.py','audit1','executed_auditor.py'),
    ('tools/idle_short_budget_v1/independent.py','audit1','executed_independent.py'),
    ('tools/assess_idle_short_budget_v1.py','assessment1','executed_assessment.py'),
    ('tools/verify_idle_short_budget_summary_v1.py','summary_audit1','executed_verifier.py')]:
    assert sha(repo/path)==sha(evidence/folder/name);sources.add(path)
figure=assessment['figure'];assert sha(evidence/'assessment1'/figure['file'])==figure['sha256']
shutil.copy2(evidence/'assessment1'/figure['file'],repo/'research/idle_short_budget_v1.png');sources.add('research/idle_short_budget_v1.png')
ch=list(csv.reader((repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig')))
assert len(ch)==620 and all(sha(repo/row[0])==row[4] for row in ch[1:])
voices_path=a.workspace/'baselines/idle_microtexture_c_v1/inputs/voice_files_sha256.json';voices=load(voices_path)
assert len(voices)==67 and all(sha(repo/path)==digest for path,digest in voices.items())
sources.update(['tools/package_idle_short_budget_v1.py','research/怠速短窗分层预算V1.md',
    'research/idle_listening_priority_20261114.json','AGENTS.md','handoff/研究续接.md','handoff/开发留痕.md'])
shutil.copy2(repo/'AGENTS.md',a.workspace/'AGENTS.md')
inputs={'previous_window_manifest.json':a.workspace/'baselines/idle_window_transfer_v1/manifest.json',
    'variation_manifest.json':a.workspace/'baselines/idle_variation_budget_v1/manifest.json',
    'actual_audio_manifest.json':a.workspace/'baselines/idle_local_partition_v1/manifest.json',
    'C_H_index.csv':repo/'handoff/C文件索引.csv','original_voice_hashes.json':voices_path}
validation=dict(schema='vsl.idle-short-budget-freeze/1',result='actual75main_and_near_carrier_fast_structure_gap_measured',
    parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    previous_goal_turn_progress='e029eb1 actual three-aperture observation/known transfer plus bdf3aea human regular-synth-note feedback; clean verified',
    human_priority='节奏太规整，像持续的合成器音符',all3seeds_full24seconds=True,actual_multibus_cases=144,reused_source_cases=24,
    all51signed6x6_budget_covariances=True,independent_windowQR=17052,independent_globalQR=56,independent_known_globalQR=2,
    all48original200ms_threebus_results_exact=True,all56native_residual_spectra_checked=True,all_pooled_tables_independently_checked=True,
    AM_projection_counterexample_timing=audit['AM_projection_counterexample_timing'],original_observation_data_or_gates_changed=False,
    pooled=assessment['pooled'],spectra=assessment['spectra'],source_physical_split=False,temporal_gap_is_NOT_proven_perceptual_cause=True,
    source_native_AM_PM_recovered=False,new_fit=False,new_audio=False,new_C=False,new_download=False,figure_viewed=True,
    old619C_H_and67voices_exact=True,moving35_changed=False,runtime_changed=False,listening_improvement_claimed=False,next=assessment['next'])
result=freeze(root,repo,sources,evidence,inputs,validation);verify(root)
save(repo/'research/idle_short_budget_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['idle_short_budget_v1','baselines/idle_short_budget_v1/manifest.json',result['file_count'],result['manifest_sha256'],
    'full3x24s;144bus+24source;17052windowQR56global;51signedCov',
    '75fastGapMain;187DetailSeparate;AMcounterLateExplicit;noaudio/C',
    'research/怠速短窗分层预算V1.md | research/idle_short_budget_v1_summary.json','baselines/idle_short_budget_v1/validation.json'])
print(result)
