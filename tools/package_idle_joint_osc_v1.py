"""Freeze a technically checked but unadopted diagnostic, retaining unsuccessful transfer."""
import argparse
import csv
import shutil
import subprocess
import sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--stage',choices=['freeze','verify'],required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
from research_archive_v1 import load,save,sha,freeze,verify,append_index

root=a.workspace/'baselines/idle_joint_osc_v1'
if a.stage=='verify':
    print(verify(root)['file_count']);raise SystemExit
evidence=a.workspace/'references/analysis/idle_joint_osc_v1'
fit=load(evidence/'fit1/report.json');render=load(evidence/'render1/report.json')
audit=load(evidence/'audit2/report.json');review=load(evidence/'review1/report.json')
browser=load(evidence/'browser1/report.json');plot=load(evidence/'plot1/report.json')
assert fit['result']=='joint_osc_moment_fit_retained_pending_generation'
assert render['result']=='diagnostic_joint_osc_audio_pending_audit'
assert audit['result']==browser['result']=='passed'
assert review['result']=='diagnostic_single_player_review' and len(review['clips'])==20
assert len(render['renders'])==len(audit['renders'])==3 and review['common_gain']==1.
assert browser['metadata_combinations']==20 and browser['muted_playback']
assert audit['input_report_sha256']==review['input_report_sha256']==sha(evidence/'render1/report.json')
assert review['audit_sha256']==sha(evidence/'audit2/report.json')
sources=set()
for directory,report in [('fit1',fit),('render1',render)]:
    for name,digest in report['sources'].items():
        assert sha(repo/name)==digest==sha(evidence/directory/'exact_sources'/name)
        sources.add(name)
    for path,digest in report['inputs'].items():assert sha(path)==digest
for row in fit['observations']:
    assert sha(evidence/'fit1'/row['file'])==row['sha256']
    assert row['check']['joint_relative_distance']>row['check']['independent_relative_distance']
for row in render['renders']:
    assert sha(evidence/'render1'/row['traces'])==row['traces_sha256']
    for item in row['files'].values():assert sha(evidence/'render1'/item['file'])==item['sha256']
for row in review['clips']:assert sha(evidence/'review1'/review['files'][row['key']])==row['sha256']
for name,directory,executed in [('tools/audit_idle_joint_osc_v1.py','audit2','executed_auditor.py'),
    ('tools/review_idle_joint_osc_v1.py','review1','executed_review.py'),
    ('tools/idle_joint_osc_v1/review.html','review1','executed_template.html'),
    ('tools/check_idle_joint_osc_v1.cjs','browser1','executed_check.cjs'),
    ('tools/plot_idle_joint_osc_v1.py','plot1','executed_plot.py')]:
    assert sha(repo/name)==sha(evidence/directory/executed);sources.add(name)
assert plot['fit_sha256']==sha(evidence/'fit1/report.json')
assert plot['spectra_sha256']==sha(evidence/'review1/actual_spectra.json')
assert plot['sha256']==sha(evidence/'plot1'/plot['file'])
shutil.copy2(evidence/'plot1'/plot['file'],repo/'research/idle_joint_osc_v1.png')
rows=list(csv.reader((repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig')))
assert len(rows)==620 and all(sha(repo/row[0])==row[4] for row in rows[1:])
voices_path=a.workspace/'baselines/idle_microtexture_c_v1/inputs/voice_files_sha256.json'
voices=load(voices_path)
assert len(voices)==67 and all(sha(repo/name)==digest for name,digest in voices.items())
shutil.copy2(repo/'AGENTS.md',a.workspace/'AGENTS.md')
sources.update(['research/idle_joint_osc_v1.png','research/怠速关联细节对照V1.md',
                'tools/package_idle_joint_osc_v1.py','AGENTS.md','handoff/研究续接.md','handoff/开发留痕.md'])
parents=['idle_conditioned_detail_v1','fixed_source_profiles_v1','idle_phase_recipe_v1','idle_positive_power_v1']
inputs={name+'_manifest.json':a.workspace/'baselines'/name/'manifest.json' for name in parents}
inputs['old_voice_files_sha256.json']=voices_path
validation=dict(schema='vsl.idle-joint-osc-freeze/1',result='diagnostic_complete_joint_transfer_failed_NOT_adopted',
    parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    four_source_control_fits=True, source_check=fit['observations'][0]['check'],
    fixed_seeds=[149921,277139,381611],seconds_each=24,
    source_recorded_trajectory_replayed=False,expected_per_carrier_variances_equal=True,
    actual_PSD_and_RMS_not_matched=True,all_moment_and_factor_checks=True,
    all_coefficient_nodes_checked=True,native_waveform_check='Sampled throughout all seeds, not all native samples',
    sample_counts=[row['native_sample_count'] for row in audit['renders']],
    maximum_sampled_error_FS=max(value for row in audit['renders'] for value in row['sampled_native_waveform_errors'].values()),
    maximum_peak_FS=max(item['peak'] for row in render['renders'] for item in row['files'].values()),
    review_url=review['url'],review_clips=20,common_gain=1.,browser=browser,
    figures_and_screenshots_viewed=True,existing619C_H_and67voices_exact=True,
    runtime_changed=False,listening_accepted=False,accepted_moving_changed=False,
    next='Keep the full covariance failure. Select repeatable small local structure before another source-derived positive-kernel hypothesis; no CHECK-tuned scalar mixture, automatic C promotion or extra HF/LF power fill. Pending original phase qualifications and whole-system goal remain open.')
result=freeze(root,repo,sources,evidence,inputs,validation);verify(root)
save(repo/'research/idle_joint_osc_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['idle_joint_osc_v1','baselines/idle_joint_osc_v1/manifest.json',result['file_count'],result['manifest_sha256'],
    '4fits;3seedsx24s;moments/factors/nodes+samplednative;20PCM24HTTPbrowser',
    'CompletejointCHECKfails;diagnostic_NOTadopted;619C-H67voicesexact',
    'research/怠速关联细节对照V1.md | research/idle_joint_osc_v1_summary.json','baselines/idle_joint_osc_v1/validation.json'])
print(result)
