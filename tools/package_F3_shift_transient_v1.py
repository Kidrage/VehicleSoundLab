"""Freeze native transient evidence, boundary limitations and all audit attempts."""
import argparse
import csv
from pathlib import Path
import subprocess
from research_archive_v1 import load,save,sha,freeze,verify,append_index
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True);p.add_argument('--verify',action='store_true');a=p.parse_args()
repo=Path(__file__).resolve().parents[1];e=a.workspace/'references/analysis/F3_shift_transient_v1';root=a.workspace/'baselines/F3_shift_transient_v1'
if a.verify:verify(root);print('F3 transient archive verified');raise SystemExit
parent=a.workspace/'baselines/F3_lift_voice_v1';verify(parent)
producer=load(e/'observe1/report.json');first=load(e/'audit1/report.json');audit=load(e/'audit2/report.json');plot=load(e/'plot1/report.json')
assert producer['result']=='fixed_F3_transient_measured' and audit['result']=='direct_native_transient_audit_passed'
assert first['result']=='failed' and 'not subscriptable' in first['error'] and len(first['cases'])==8
assert len(producer['controls'])==7 and len(audit['cases'])==8
assert audit['producer_report_sha256']==plot['producer_report_sha256']==sha(e/'observe1/report.json')
assert plot['audit_report_sha256']==sha(e/'audit2/report.json')
assert plot['result']=='all_source_transient_and_stereo_diagnostics_plotted'
assert not audit['source']['event_envelope_supported']
assert producer['source']['statistics']['descriptive_broad_dip_recovery']
for name,want in producer['inputs'].items():assert sha(name)==want,name
for name,want in producer['sources'].items():assert sha(repo/name)==want==sha(e/'observe1/exact_sources'/name),name
assert sha(repo/'tools/audit_F3_shift_transient_v1.py')==sha(e/'audit2/audit_source.py')
assert sha(repo/'tools/plot_F3_shift_transient_v1.py')==sha(e/'plot1/plot_source.py')
with (parent/'source/handoff/C文件索引.csv').open(encoding='utf-8-sig',newline='') as f:index=list(csv.DictReader(f))
assert len(index)==647 and all(sha(repo/v['文件'])==v['SHA-256'] for v in index)
voices=load(parent/'inputs/voice_files_sha256.json');assert len(voices)==74 and all(sha(repo/n)==h for n,h in voices.items())
f2=['experiments/modal_idle_v1/F2_fixed_idle.msource','experiments/modal_texture_v1/F2_amplitude.mtexture','experiments/spectral_texture_v1/F2_fine_static.sfir']
assert all(sha(repo/n)==sha(parent/'source'/n) for n in f2)
sources=set(producer['sources'])|set(f2)|set([
    'tools/audit_F3_shift_transient_v1.py','tools/plot_F3_shift_transient_v1.py','tools/package_F3_shift_transient_v1.py',
    'research/F3升挡附近瞬态V1.md','README.md','AGENTS.md','handoff/研究续接.md','handoff/开发留痕.md','handoff/C文件索引.csv'])
inputs={'parent_manifest.json':parent/'manifest.json','C_index_before.csv':parent/'source/handoff/C文件索引.csv',
    'voice_files_sha256.json':parent/'inputs/voice_files_sha256.json','data_AGENTS.md':a.workspace/'AGENTS.md'}
validation=dict(result='native_transient_measured_boundary_limited_no_event_envelope',
    git_parent=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    previous_goal_turn='progress: native-cycle power and independent audit retained incomplete sensitivity; no cyclic model promoted',
    source_seconds=[199.5,201.5],native_frames=96000,windows=393,window_frames=1920,hop_frames=240,
    controls=producer['controls'],known_stereo_normalization=producer['known_stereo_normalization'],
    source=producer['source']['statistics'],endpoint_diagnostics=audit['source']['endpoint_distances_seconds'],
    broad_dip_descriptively_detected=True,event_envelope_qualified=False,physical_shift_timing_calibrated=False,
    cross_convention='conj(L)*R',complex_integrated_correlation_not_MSC=True,
    maximum_independent_errors=audit['maximum_errors'],all_native_FFT_frames=3144,
    reused_prior_viewed_PTS_frames=25,analysis_images_viewed=1,
    C_H_exact=647,voice_files_exact=74,F2_exact=True,runtime_UI_driver_default_takes_unchanged=True,
    all_attempts=['observe1','audit1','audit2','plot1'],first_audit_error_preserved=first['error'],
    no_gate_window_band_rescue=True,endpoint_diagnostics_post_observation_report_only=True,
    no_new_voice_or_event_parameter=True,no_listening_promotion=True,
    F3_detail_hearing='independently pending; optional engineering exposure is not acceptance/default migration',
    F2_idle_hearing='independently pending; no repeat/blind strength/default migration',
    unchanged_66CTest_not_repeated=True,downloaded=False,pushed=False,full_goal='active',
    next='Expose the existing F3 DNA/additive stereo profile as an optional catalog entry in the same driver/layer/record host; '
         'preserve default and hearing status. No instantaneous event gain or full-state calibration derived from this transient.')
result=freeze(root,repo,sources,e,inputs,validation);verify(root)
save(repo/'research/F3_shift_transient_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['F3_shift_transient_v1','baselines/F3_shift_transient_v1/manifest.json',result['file_count'],result['manifest_sha256'],
    'Native2s;7known controls;3144direct DFT frames;stereo/cross/Parseval/regions;boundary diagnostics',
    '647C-H74voices/F2 exact;descriptive dip but endpoints censored;no event/default/physical calibration;both audits retained',
    'research/F3升挡附近瞬态V1.md | research/F3_shift_transient_v1_summary.json','baselines/F3_shift_transient_v1/validation.json'])
print(result)
