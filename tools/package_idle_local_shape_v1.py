"""Freeze source extraction, finite audio and next-core clue, without C promotion."""
import argparse,csv,shutil,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--stage',choices=['freeze','verify'],required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from research_archive_v1 import load,save,sha,freeze,verify,append_index

root=a.workspace/'baselines/idle_local_shape_v1'
if a.stage=='verify':print(verify(root)['file_count']);raise SystemExit
evidence=a.workspace/'references/analysis/idle_local_shape_v1'
fit=load(evidence/'fit1/report.json');render=load(evidence/'render1/report.json')
audit=load(evidence/'audit2/report.json');initial_audit=load(evidence/'audit1/report.json')
review=load(evidence/'review1/report.json');browser=load(evidence/'browser1/report.json')
assessment=load(evidence/'assessment1/report.json');core=load(evidence/'core_inspect1/report.json')
assert fit['result']=='local_positive_shape_extraction_complete' and len(fit['observations'])==4
assert render['result']=='finite_local_shape_audio_pending_audit' and len(render['renders'])==3
assert audit['result']==initial_audit['result']==browser['result']=='passed'
assert audit['every_compiled_branch_response_independently_checked']
assert audit['input_sha256']==initial_audit['input_sha256']==review['input_report_sha256']==assessment['input_sha256']==sha(evidence/'render1/report.json')
assert review['audit_sha256']==assessment['audit_sha256']==sha(evidence/'audit1/report.json')
assert review['result']=='same_gain_local_shape_review' and len(review['clips'])==20 and review['common_gain']==1.
assert browser['metadata_combinations']==20 and browser['muted_playback']
assert assessment['result']=='all_declared_local_shape_contrasts_observed' and len(assessment['contrasts'])==6
sources=set()
for directory,report in [('fit1',fit),('render1',render)]:
    for name,digest in report['sources'].items():
        assert sha(repo/name)==digest==sha(evidence/directory/'exact_sources'/name);sources.add(name)
    for path,digest in report['inputs'].items():assert sha(path)==digest
for b in range(2):assert sha(evidence/f'render1/bank_{b}.npz')==audit['bank_sha256'][b]
for row in render['renders']:
    assert sha(evidence/'render1'/row['trace'])==row['trace_sha256']
    for item in row['files'].values():assert sha(evidence/'render1'/item['file'])==item['sha256']
for row in review['clips']:assert sha(evidence/'review1'/review['files'][row['key']])==row['sha256']
for name,directory,executed in [('tools/audit_idle_local_shape_v1.py','audit2','executed_auditor.py'),
    ('tools/review_idle_local_shape_v1.py','review1','executed_review.py'),
    ('tools/idle_local_shape_v1/review.html','review1','executed_template.html'),
    ('tools/check_idle_shape_v1.cjs','browser1','executed_check.cjs'),
    ('tools/assess_idle_local_shape_v1.py','assessment1','executed_assessment.py'),
    ('tools/inspect_idle_core_amplitude_v1.py','core_inspect1','executed_inspector.py')]:
    assert sha(repo/name)==sha(evidence/directory/executed);sources.add(name)
assert sha(core['input'])==core['input_sha256'] and core['raw_uncapped_trace_correlation']<0
figure=assessment['figure'];assert sha(evidence/'assessment1'/figure['file'])==figure['sha256']
shutil.copy2(evidence/'assessment1'/figure['file'],repo/'research/idle_local_shape_v1.png')
save(repo/'research/idle_local_shape_v1_profile.json',dict(schema='vsl.idle-local-shape-study/1',
    selected_bands=[0,1],models=render['models'],fit_report_sha256=sha(evidence/'fit1/report.json'),
    branch_fft_frames=32768,procedural_innovation_lookahead_frames=16384,mask='Complementary cosine amplitude masks',
    normalization='Full shared-input response Gram, conditional stationary innovation variance',
    original_sparse_innovations_retained=True,recorded_trajectory=False,
    selection_used_previously_inspected_CHECK=True,runtime_adopted=False,listening_accepted=False))
rows=list(csv.reader((repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig')))
assert len(rows)==620 and all(sha(repo/row[0])==row[4] for row in rows[1:])
voices_path=a.workspace/'baselines/idle_microtexture_c_v1/inputs/voice_files_sha256.json';voices=load(voices_path)
assert len(voices)==67 and all(sha(repo/name)==value for name,value in voices.items())
shutil.copy2(repo/'AGENTS.md',a.workspace/'AGENTS.md')
sources.update(['AGENTS.md','handoff/研究续接.md','handoff/开发留痕.md',
    'research/怠速局部共振V1.md','research/idle_local_shape_v1_profile.json','research/idle_local_shape_v1.png',
    'tools/package_idle_local_shape_v1.py'])
parents=['idle_conditioned_detail_v1','fixed_source_profiles_v1','idle_phase_recipe_v1',
         'idle_positive_power_v1','idle_post_budget_v1','modal_texture_v1']
inputs={name+'_manifest.json':a.workspace/'baselines'/name/'manifest.json' for name in parents}
inputs['old_voice_files_sha256.json']=voices_path
validation=dict(schema='vsl.idle-local-shape-freeze/1',result='small_source_local_shape_audio_NOT_adopted',
    parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    four_source_control_fits=True,all16models_converged=all(b['model']['optimizer_success'] for r in fit['observations'] for b in r['bands']),
    source_CHECK_improvements=assessment['source_check_descriptor_improvements'],
    selected_bands=[0,1],selection_uses_previously_inspected_CHECK=True,
    seeds=[149921,277139,381611],amounts=[0.,.5,1.],seconds_each=24,
    source_recorded_trajectory_replayed=False,all_native_audio_independently_checked=True,
    maximum_waveform_error_FS=max(v for row in audit['renders'] for v in row['full_native_waveform_errors_FS'].values()),
    maximum_branch_error_FS=max(row['full_branch_convolution_error_FS'] for row in audit['renders']),
    maximum_Gram_variance_error=max(row['full_Gram_variance_error'] for row in audit['renders']),
    zero_frozen_errors_FS=[row['zero_frozen_error_FS'] for row in render['renders']],
    maximum_peak_FS=max(v['peak'] for row in render['renders'] for v in row['files'].values()),
    contrasts=assessment['contrasts'],whole_mix_change_is_small=True,
    core_followup_clue=core,core_clue_is_NOT_new_AM_recipe=True,
    review_url=review['url'],review_clips=20,common_gain=1.,browser=browser,figures_and_screenshots_viewed=True,
    existing619C_H_and67voices_exact=True,runtime_changed=False,listening_accepted=False,accepted_moving_changed=False,
    next='Do not amplify this weak shape result. Phase-aware core magnitude observation with known no-AM nonlinear-FM/known-AM controls before source TRAIN/CHECK and any fresh amplitude generator; old fixed-frequency magnitude mixes AM/FM. Preserve original common-phase qualifications, pending auditions and full-system goal.')
result=freeze(root,repo,sources,evidence,inputs,validation);verify(root)
save(repo/'research/idle_local_shape_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['idle_local_shape_v1','baselines/idle_local_shape_v1/manifest.json',result['file_count'],result['manifest_sha256'],
    '16fits;3seedsx3amountsx24s;allsourceDFT/grad/branchFFT/fullnative;20HTTPbrowser',
    'Weak~minus43dBmix;NOTadopted;posthoccoreAMconfounded;619C-H67voicesexact',
    'research/怠速局部共振V1.md | research/idle_local_shape_v1_summary.json','baselines/idle_local_shape_v1/validation.json'])
print(result)
