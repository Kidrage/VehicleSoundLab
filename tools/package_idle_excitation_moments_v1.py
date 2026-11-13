"""Freeze the source-derived idle excitation study and both independent audits."""
import argparse,shutil,subprocess
from pathlib import Path
from research_archive_v1 import load,save,sha,freeze,verify,append_index
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--stage',choices=['freeze','verify'],required=True);a=p.parse_args()
repo=Path(__file__).resolve().parents[1];root=a.workspace/'baselines/idle_excitation_moments_v1'
if a.stage=='verify':verify(root);print('Idle excitation study archive verified.');raise SystemExit
evidence=a.workspace/'references/analysis/idle_excitation_moments_v1'
observed=load(evidence/'observe1/report.json');trial=load(evidence/'trial1/report.json')
audit=load(evidence/'audit2/report.json');review=load(evidence/'review1/report.json')
assert observed['result']=='moment_candidate_compiled'
assert trial['result']=='sparse_excitation_candidates_pending_listening'
assert audit['result']=='passed' and audit['all9_finite_moment_reports_independently_verified']
assert audit['complete_audio_candidates']==len(trial['renders'])==9
assert load(evidence/'audit1/report.json')['result']=='passed'
assert review['audit_sha256']==sha(evidence/'audit1/report.json')
assert review['common_gain']==1 and not review['listening_accepted']
for row in review['inputs'].values():assert sha(row['path'])==row['sha256']
for row in review['clips']:assert sha(evidence/'review1'/review['files'][row['key']])==row['sha256']
assert load(evidence/'browser1/report.json')['metadata_combinations']==25
assert load(evidence/'browser1/report.json')['result']=='pass'
plot=load(evidence/'plot1/report.json');assert sha(evidence/'plot1/excitation_moments.png')==plot['image_sha256']
shutil.copy2(evidence/'plot1/excitation_moments.png',repo/'research/idle_excitation_moments_v1_diagnostics.png')
sources=set()
for folder,report in [('observe1',observed),('trial1',trial)]:
    for name,digest in report['sources'].items():
        assert sha(repo/name)==digest==sha(evidence/folder/'exact_sources'/name);sources.add(name)
sources.update(['tools/audit_idle_excitation_moments_v1.py','tools/review_idle_excitation_moments_v1.py',
    'tools/idle_excitation_moments_v1/review.html','tools/check_idle_conditioned_detail_v1.cjs',
    'tools/plot_idle_excitation_moments_v1.py','tools/package_idle_excitation_moments_v1.py',
    'research/怠速颗粒激励提取V1.md','research/idle_excitation_moments_v1_diagnostics.png',
    'AGENTS.md','handoff/研究续接.md','handoff/开发留痕.md'])
invariant=a.workspace/'baselines/idle_microtexture_c_v1/inputs';inputs={}
for filename,count in [('C_files_sha256.json',612),('voice_files_sha256.json',67)]:
    data=load(invariant/filename);assert len(data)==count
    for name,digest in data.items():assert sha(repo/name)==digest,name
    inputs[filename]=invariant/filename
inputs.update(F2_profile_json=Path(observed['profile_path']),
    F2_check_wav=a.workspace/'baselines/idle_texture_v2/inputs/F2_holdout.wav',
    previous_conditioned_manifest=a.workspace/'baselines/idle_conditioned_detail_v1/manifest.json',
    data_workspace_AGENTS=a.workspace/'AGENTS.md')
validation=dict(schema='vsl.idle-excitation-moments-freeze/1',
    result='offline_sparse_spectral_excitation_pending_listening',
    parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    all3seeds_all3amounts_retained=True,all9_audio_and_finite_moments_independently_verified=True,
    zero_FLOAT_exact=True,maximum_FLOAT_error=audit['max_wave_error_FS'],
    maximum_finite_band_power_delta_db=plot['max_finite_band_power_delta_db'],
    maximum_peak_FS=max(row['peak'] for row in trial['renders']),
    unchanged_C_H=612,unchanged_old_voices=67,runtime_or_default_changed=False,
    old61_driving_tests_repeated=False,physical_source_or_RPM_load_identified=False,
    original_shared_phase_qualification_still_required=True,same_recording_previously_inspected_check=True,
    timbre_accepted=False,browser_muted_combinations=25,screenshots_and_plot_viewed=True,
    PCM_or_recorded_timeline_or_room_or_PM_FM=False,
    next='Hear grain/sand/pops against static and previous conditional candidate before optional C port; no blind rate/seed/window tuning.')
result=freeze(root,repo,sorted(sources),evidence,inputs,validation);verify(root)
save(repo/'research/idle_excitation_moments_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['idle_excitation_moments_v1','baselines/idle_excitation_moments_v1/manifest.json',
    result['file_count'],result['manifest_sha256'],
    'NativeF2 fourth cumulants;independent FIR/PRNG/fullFFT/all9audio+moments;25muted browser combinations',
    'Statistical excitation not firing/sourceidentity/listening/runtime acceptance;612C-H67voices unchanged',
    'research/怠速颗粒激励提取V1.md | research/idle_excitation_moments_v1_summary.json',
    'baselines/idle_excitation_moments_v1/validation.json'])
print(result)
