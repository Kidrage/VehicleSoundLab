"""Archive fixed-map controls with exact sources and unchanged runtime assets."""
import argparse
import csv
from pathlib import Path
import subprocess
from research_archive_v1 import load,save,sha,freeze,verify,append_index
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--verify',action='store_true')
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
e=a.workspace/'references/analysis/F3_warp_noise_v1';root=a.workspace/'baselines/F3_warp_noise_v1'
if a.verify:verify(root);print('F3 frozen-map archive verified');raise SystemExit
parent=a.workspace/'baselines/F3_lift_voice_v1';verify(parent)
producer=load(e/'controls1/report.json');audit=load(e/'audit1/report.json');plot=load(e/'plot1/report.json')
assert producer['result']=='paired_frozen_map_controls_completed'
assert audit['result']=='independent_frozen_map_audit_passed'
assert plot['result']=='all_fixed_controls_plotted'
assert audit['producer_report_sha256']==plot['producer_report_sha256']==sha(e/'controls1/report.json')
assert len(producer['cases'])==len(audit['cases'])==16
assert sha(repo/'tools/audit_F3_warp_noise_v1.py')==sha(e/'audit1/audit_source.py')
assert sha(repo/'tools/plot_F3_warp_noise_v1.py')==sha(e/'plot1/plot_source.py')
for name,want in producer['inputs'].items():assert sha(name)==want,name
for name,want in producer['sources'].items():
    assert sha(repo/name)==want==sha(e/'controls1/exact_sources'/name),name
with (parent/'source/handoff/C文件索引.csv').open(encoding='utf-8-sig',newline='') as f:index=list(csv.DictReader(f))
assert len(index)==647
assert all(sha(repo/row['文件'])==row['SHA-256'] for row in index)
voices=load(parent/'inputs/voice_files_sha256.json')
assert len(voices)==74 and all(sha(repo/name)==want for name,want in voices.items())
f2=['experiments/modal_idle_v1/F2_fixed_idle.msource','experiments/modal_texture_v1/F2_amplitude.mtexture',
    'experiments/spectral_texture_v1/F2_fine_static.sfir']
assert all(sha(repo/name)==sha(parent/'source'/name) for name in f2)
sources=set(producer['sources'])|set(f2)|set([
    'tools/audit_F3_warp_noise_v1.py','tools/plot_F3_warp_noise_v1.py','tools/package_F3_warp_noise_v1.py',
    'research/F3固定变换噪声对照V1.md','README.md','AGENTS.md',
    'handoff/研究续接.md','handoff/开发留痕.md','handoff/C文件索引.csv'])
inputs={'parent_manifest.json':parent/'manifest.json','C_index_before.csv':parent/'source/handoff/C文件索引.csv',
    'voice_files_sha256.json':parent/'inputs/voice_files_sha256.json',
    'frozen_coordinates.npz':parent/'evidence/fit2/F3 Sixth Before Upshift/coordinates.npz',
    'frozen_extraction.json':parent/'evidence/fit2/F3 Sixth Before Upshift/extraction.json',
    'source_prior_dependence.json':a.workspace/'references/analysis/F3_detail_v1/observe1/report.json',
    'data_AGENTS.md':a.workspace/'AGENTS.md'}
validation=dict(result='fixed_map_stationary_noise_controls_completed',
    git_parent=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    previous_goal_turn='progress: revised user-requested ADI cost inventory and documented omitted legacy recipes; not timbre acceptance',
    controls=producer['route_summary'],known_before_map=producer['known_before_map'],
    maximum_independent_errors=audit['maximum_errors'],
    coordinate_plot=plot,analysis_images_viewed=1,C_H_exact=647,voice_files_exact=74,F2_exact=True,
    no_source_waveform_read=True,no_clock_reestimation=True,no_fit_or_runtime_change=True,
    physical_source_separation=False,periodic_modulation_law_qualified=False,
    timbre_accepted=False,new_listening_candidate=False,
    F3_detail_hearing='pending; no repeat question, blind strength or migration',
    F2_idle_hearing='independently pending; unchanged',
    E_stereo_feedback='左右关系有改善，音色仍明显电子',
    unchanged_C_tests_not_repeated=True,downloaded=False,pushed=False,
    all_attempts=['controls1','audit1','plot1'],full_goal='active',
    next='Measure high-band power versus frozen cycle coordinate in native time without waveform resampling; '
         'do not infer physical cause or implement modulation from this conditional four-seed control.')
result=freeze(root,repo,sources,e,inputs,validation);verify(root)
save(repo/'research/F3_warp_noise_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['F3_warp_noise_v1','baselines/F3_warp_noise_v1/manifest.json',
    result['file_count'],result['manifest_sha256'],
    '4paired seeds x4routes;direct FIR/polyphase;all powers/256nulls/p;one diagnostic image',
    '647C-H74voices/F2 exact;conditional map only;no source audio/reestimate/fit/runtime/hearing promotion',
    'research/F3固定变换噪声对照V1.md | research/F3_warp_noise_v1_summary.json',
    'baselines/F3_warp_noise_v1/validation.json'])
print(result)
