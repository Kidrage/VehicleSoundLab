"""Preserve native negative evidence, the missed known control and first failure."""
import argparse
import csv
from pathlib import Path
import subprocess
from research_archive_v1 import load,save,sha,freeze,verify,append_index
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True);p.add_argument('--verify',action='store_true');a=p.parse_args()
repo=Path(__file__).resolve().parents[1];e=a.workspace/'references/analysis/F3_native_power_v1';root=a.workspace/'baselines/F3_native_power_v1'
if a.verify:verify(root);print('F3 native-cycle archive verified');raise SystemExit
parent=a.workspace/'baselines/F3_lift_voice_v1';noise=a.workspace/'baselines/F3_warp_noise_v1';verify(parent);verify(noise)
first=load(e/'observe1/report.json');producer=load(e/'observe2/report.json');audit=load(e/'audit1/report.json');plot=load(e/'plot1/report.json')
assert first['result']=='failed' and 'TypeError' in first['error']
assert not any(n.endswith('native.wav') for n in first['inputs'])
assert producer['result']=='native_time_relationship_measured' and audit['result']=='native_time_independent_audit_passed'
assert audit['producer_report_sha256']==plot['producer_report_sha256']==sha(e/'observe2/report.json')
assert plot['result']=='all_native_results_plotted' and plot['cases']==11 and plot['routes']==2
assert audit['known_AM_actual_primary_detected']==3 and audit['primary_source_supported']==[]
for name,want in producer['inputs'].items():assert sha(name)==want,name
for name,want in producer['sources'].items():assert sha(repo/name)==want==sha(e/'observe2/exact_sources'/name),name
for attempt,script,copy in [('audit1','tools/audit_F3_native_power_v1.py','audit_source.py'),('plot1','tools/plot_F3_native_power_v1.py','plot_source.py')]:
    assert sha(repo/script)==sha(e/attempt/copy)
with (parent/'source/handoff/C文件索引.csv').open(encoding='utf-8-sig',newline='') as f:index=list(csv.DictReader(f))
assert len(index)==647 and all(sha(repo/v['文件'])==v['SHA-256'] for v in index)
voices=load(parent/'inputs/voice_files_sha256.json');assert len(voices)==74 and all(sha(repo/n)==h for n,h in voices.items())
f2=['experiments/modal_idle_v1/F2_fixed_idle.msource','experiments/modal_texture_v1/F2_amplitude.mtexture','experiments/spectral_texture_v1/F2_fine_static.sfir']
assert all(sha(repo/n)==sha(parent/'source'/n) for n in f2)
sources=set(producer['sources'])|set(f2)|set([
    'tools/audit_F3_native_power_v1.py','tools/plot_F3_native_power_v1.py','tools/package_F3_native_power_v1.py',
    'research/F3原生周期功率V1.md','AGENTS.md','README.md','handoff/研究续接.md','handoff/开发留痕.md','handoff/C文件索引.csv'])
folder=parent/'evidence/fit2/F3 Sixth Before Upshift'
inputs={'parent_manifest.json':parent/'manifest.json','noise_manifest.json':noise/'manifest.json',
    'native.wav':folder/'native.wav','coordinates.npz':folder/'coordinates.npz',
    'C_index_before.csv':parent/'source/handoff/C文件索引.csv','voice_files_sha256.json':parent/'inputs/voice_files_sha256.json',
    'data_AGENTS.md':a.workspace/'AGENTS.md'}
for seed in [1907,23117,61927,8121907]:inputs[f'noise_seed{seed}.npz']=noise/f'evidence/controls1/seed{seed}/native.npz'
validation=dict(result='native_time_clue_not_reproduced_primary_sensitivity_incomplete',
    git_parent=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    previous_goal_turn='progress: executed frozen-map controls and direct resampling/null audit; archived all outcomes',
    native_source_frames=9338,complete_cycles=13,interior_cycles=9,train_cycles=5,heldout_cycles=4,
    source=producer['source']['result'],known_before_frozen_map=producer['known_before_frozen_map'],
    four_fixed_controls=[dict(name=v['name'],supported=v['supported']) for v in producer['controls']],
    actual_AM_primary_detected=3,actual_AM_trials=4,missed_AM_seed=61927,
    primary_method_qualified=False,physical_source_separation=False,cyclic_law_qualified=False,
    source_waveform_resampled=False,phase_reestimated=False,new_runtime_voice=False,
    maximum_independent_errors=audit['maximum_errors'],analysis_images_viewed=1,
    C_H_exact=647,voice_files_exact=74,F2_exact=True,runtime_UI_driver_default_takes_unchanged=True,
    all_attempts=['observe1','observe2','audit1','plot1'],first_failure_preserved=first['error'],
    fixed_plan_unchanged=True,unchanged_66CTest_not_repeated=True,downloaded=False,pushed=False,
    F3_detail_hearing='pending; no repeat/blind strength/migration',F2_idle_hearing='independently pending',
    E_stereo_feedback='左右关系有改善，音色仍明显电子',full_goal='active',
    next='End this-window periodic-envelope parameterization; examine approved F3 visible-upshift native spectral '
         'decay/recovery and LR changes without rescuing a failed clock or inferring calibrated pedal/fuel/RPM from the display.')
result=freeze(root,repo,sources,e,inputs,validation);verify(root)
save(repo/'research/F3_native_power_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['F3_native_power_v1','baselines/F3_native_power_v1/manifest.json',result['file_count'],result['manifest_sha256'],
    'Native13cycles5/4;all11inputs2routes;normal-equation/filter/256null audit;knownAM miss retained',
    '647C-H74voices/F2 exact;primary clue not reproduced;not qualified;no runtime/hearing promotion;first TypeError retained',
    'research/F3原生周期功率V1.md | research/F3_native_power_v1_summary.json','baselines/F3_native_power_v1/validation.json'])
print(result)
