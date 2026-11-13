"""Freeze guided F3 peak observations including the dense-comb classifier limitation."""
import argparse,subprocess,shutil
from pathlib import Path
from research_archive_v1 import sha,load,save,freeze,verify,append_index
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--stage',choices=['freeze','verify'],required=True);a=p.parse_args()
repo=Path(__file__).resolve().parents[1];evidence=a.workspace/'references/analysis/accel_ridges_v1'
root=a.workspace/'baselines/accel_ridges_v1';parent=a.workspace/'baselines/fine_idle_drive_v1'
old=load(parent/'inputs/C_files_sha256.json');voices=load(parent/'inputs/voice_files_sha256.json')
assert len(old)==600 and len(voices)==67
assert all(sha(repo/n)==h for n,h in {**old,**voices}.items())
if a.stage=='verify':verify(root);print('freeze verified');raise SystemExit
first=load(evidence/'observe1/report.json');final=load(evidence/'observe2/report.json');audit=load(evidence/'audit1/report.json')
assert first['result']==final['result']=='native_guided_ridge_observations_complete'
assert audit['result']=='all_native_inventories_assignments_and_classifications_passed'
assert audit['inventory_count']==144 and audit['assignment_count']==288 and audit['class_count']==339
assert audit['dense_comb_limitation']['known_moving_partials']==26
assert audit['dense_comb_limitation']['false_uncertain_despite_moving_support']==18
assert first['observations']==final['observations']
assert audit['observation_report_sha256']==sha(evidence/'observe2/report.json')
for label,report in [('observe1',first),('observe2',final)]:
    for name,h in report['sources'].items():
        assert sha(evidence/label/'exact_sources'/name)==h
        if label=='observe2':assert sha(repo/name)==h
plot=load(evidence/'plot1/report.json');assert plot['observation_sha256']==sha(evidence/'observe2/report.json')
assert sha(repo/'research/accel_ridges_v1_diagnostics.png')==sha(evidence/'plot1/F3_guided_peaks.png')
source=list(final['sources'])+['tools/audit_accel_ridges_v1.py','tools/plot_accel_ridges_v1.py',
    'tools/package_accel_ridges_v1.py','research/加速谱峰对应与误判V1.md','research/accel_ridges_v1_diagnostics.png',
    'AGENTS.md','handoff/研究续接.md','handoff/开发留痕.md']
validation=dict(schema='vsl.accel-ridges-freeze/1',result='guided_peak_observations_verified_classifier_not_sufficient_for_source_identity',
    parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    observations=final['observations'],plot_summary=plot['summary'],native_inventory_count=144,
    assignment_graphs=288,classification_count=339,maximum_frequency_error_hz=audit['maximum_hz_error'],
    maximum_prominence_error_db=audit['maximum_prominence_error'],dense_comb_limitation=audit['dense_comb_limitation'],
    guide_refitted=False,original_classes_relaxed=False,source_or_phase_or_RPM_identity_established=False,
    real_source_audio_read=True,new_audio_or_profile_exported=False,timbre_acceptance=False,
    C_H_unchanged=600,voices_unchanged=67,old61CTest_repeated=False,plot_visually_reviewed=True,
    pending_idle_question_repeated=False,
    next='Joint native varying-frequency fits with dense-comb/missing/neighbour controls and held-out windows; preserve independent phase and source perspective limits.',
    freeze='baselines/accel_ridges_v1')
inputs={'C_files_sha256.json':parent/'inputs/C_files_sha256.json','voice_files_sha256.json':parent/'inputs/voice_files_sha256.json',
        'parent_manifest.json':parent/'manifest.json','data_workspace_AGENTS.md':a.workspace/'AGENTS.md'}
result=freeze(root,repo,source,evidence,inputs,validation);verify(root)
save(repo/'research/accel_ridges_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['accel_ridges_v1','baselines/accel_ridges_v1/manifest.json',result['file_count'],result['manifest_sha256'],
    'F3 all48native tiles;known mixtures;144FFT/288graphs/339classifications independently verified',
    'Dense moving comb gives18false uncertainties;not physical source/phase/RPM or new sound;600C-H/67voices unchanged',
    'research/加速谱峰对应与误判V1.md | research/accel_ridges_v1_summary.json','baselines/accel_ridges_v1/validation.json'])
print(result)
