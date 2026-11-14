"""Freeze complete aperture observation without promoting source coordinates to a voice."""
import argparse,csv,shutil,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--stage',choices=['freeze','verify'],required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
from research_archive_v1 import load,save,sha,freeze,verify,append_index
root=a.workspace/'baselines/idle_window_transfer_v1'
if a.stage=='verify':print(verify(root)['file_count']);raise SystemExit
evidence=a.workspace/'references/analysis/idle_window_transfer_v1'
run=load(evidence/'observe1/report.json');audit=load(evidence/'audit1/report.json');assessment=load(evidence/'assessment1/report.json')
assert run['result']=='idle_aperture_transfer_and_resolution_observed' and len(run['cases'])==42 and len(run['transfer'])==3
assert audit['result']=='complete_idle_aperture_QR_and_transfer_independently_checked' and audit['QR_factorizations']==5220
assert audit['input_sha256']==sha(evidence/'observe1/report.json') and len(audit['cases'])==42 and len(audit['transfer'])==12
assert assessment['result']=='idle_aperture_transfer_assessed' and assessment['input_sha256']==sha(evidence/'observe1/report.json')
sources=set()
for path,digest in run['sources'].items():
    assert sha(repo/path)==digest==sha(evidence/'observe1/exact_sources'/path);sources.add(path)
for path,digest in run['inputs'].items():assert sha(path)==digest
for row in run['cases']:assert sha(evidence/'observe1'/row['file'])==row['sha256']
for path,folder,name in [('tools/audit_idle_window_transfer_v1.py','audit1','executed_auditor.py'),
    ('tools/assess_idle_window_transfer_v1.py','assessment1','executed_assessment.py')]:
    assert sha(repo/path)==sha(evidence/folder/name);sources.add(path)
figure=assessment['figure'];assert sha(evidence/'assessment1'/figure['file'])==figure['sha256']
shutil.copy2(evidence/'assessment1'/figure['file'],repo/'research/idle_window_transfer_v1.png');sources.add('research/idle_window_transfer_v1.png')
ch=list(csv.reader((repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig')))
assert len(ch)==620 and all(sha(repo/row[0])==row[4] for row in ch[1:])
voices_path=a.workspace/'baselines/idle_microtexture_c_v1/inputs/voice_files_sha256.json';voices=load(voices_path)
assert len(voices)==67 and all(sha(repo/path)==digest for path,digest in voices.items())
sources.update(['tools/package_idle_window_transfer_v1.py','research/怠速分析窗传递V1.md','AGENTS.md','handoff/研究续接.md','handoff/开发留痕.md'])
shutil.copy2(repo/'AGENTS.md',a.workspace/'AGENTS.md')
inputs={'previous_expected_manifest.json':a.workspace/'baselines/idle75_expected_v1/manifest.json',
    'variation_manifest.json':a.workspace/'baselines/idle_variation_budget_v1/manifest.json',
    'actual_audio_manifest.json':a.workspace/'baselines/idle_local_partition_v1/manifest.json',
    'C_H_index.csv':repo/'handoff/C文件索引.csv','original_voice_hashes.json':voices_path}
validation=dict(schema='vsl.idle-aperture-freeze/1',result='source_resolution_and_known_repeated_window_attenuation_measured',
    parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    previous_goal_turn_progress='39955a7 actual expected inverse qualified; source temporal mismatch retained; clean verified',
    known_FM_noAM_3apertures=True,all12_native_perturbations_checked=True,all42observations_5220independentQR=True,
    all14_original200ms_results_exact=True,all51signed_covariance_and_temporal_PSD_checked=True,
    all12two_pass_transfers_checked=True,known_repeated_window_NOT_exact_old_FIR_compiler=True,
    transfer=assessment['transfer'],source_resolution=assessment['resolution'],native_excitation_recovered=False,
    new_source_fit=False,new_audio=False,new_C=False,new_download=False,figure_viewed=True,
    old619C_H_and67voices_exact=True,moving35_changed=False,runtime_changed=False,listening_improvement_claimed=False,
    next='Same-aperture main/detail budgets and source omitted75sidebands/broadband before new AM candidate. '+assessment['next'])
result=freeze(root,repo,sources,evidence,inputs,validation);verify(root)
save(repo/'research/idle_window_transfer_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['idle_window_transfer_v1','baselines/idle_window_transfer_v1/manifest.json',result['file_count'],result['manifest_sha256'],
    '3apertures42cases;5220QR;12twoPassTransfer;14old200msExact',
    'knownSmoothingNOToldCompiler;noNativeAMclaim/audio/C;619C-H67voicesexact',
    'research/怠速分析窗传递V1.md | research/idle_window_transfer_v1_summary.json','baselines/idle_window_transfer_v1/validation.json'])
print(result)
