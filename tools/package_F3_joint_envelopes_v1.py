"""Freeze full native band observations and independently audited statistics."""
import argparse
import csv
from pathlib import Path
import shutil
import subprocess
from research_archive_v1 import load, save, sha, freeze, verify, append_index


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace',type=Path,required=True);p.add_argument('--verify',action='store_true')
    a=p.parse_args();repo=Path(__file__).resolve().parents[1]
    e=a.workspace/'references/analysis/F3_joint_envelopes_v1';root=a.workspace/'baselines/F3_joint_envelopes_v1'
    if a.verify:
        r=verify(root);print(dict(result='archive_verified',files=r['file_count'],bytes=r['bytes']));return
    m,audit,review=[load(e/n/'report.json') for n in ['measure1','audit2','review1']]
    assert m['result']=='native_joint_full_band_envelopes_observed'
    assert audit['result']=='independent_joint_envelope_audit_passed'
    assert review['result']=='native_joint_envelope_observations_published'
    assert audit['producer_report_sha256']==review['producer_report_sha256']==sha(e/'measure1/report.json')
    assert review['audit_report_sha256']==sha(e/'audit2/report.json')
    assert len(m['known'])==5 and len(m['real'])==2
    assert audit['windows']==959 and audit['DFT_complex_values']==46032 and len(audit['cases'])==7
    for n,h in m['sources'].items():assert sha(e/'measure1/exact_sources'/n)==sha(repo/n)==h
    for n,h in m['inputs'].items():assert sha(n)==h
    for n,h in m['protected_before'].items():assert sha(repo/n)==h
    for row in m['known']+m['real']:assert sha(e/'measure1'/row['label']/'arrays.npz')==row['arrays_sha256']
    failed=load(e/'audit1/report.json')
    assert failed['result']=='failed' and len(failed['cases'])==1 and failed['error']=='AssertionError()'
    assert (e/'audit1/executed_audit.py').is_file()
    assert sha(repo/'tools/audit_F3_joint_envelopes_v1.py')==sha(e/'audit2/executed_audit.py')==audit['auditor_sha256']
    assert sha(repo/'tools/review_F3_joint_envelopes_v1.py')==sha(e/'review1/executed_review.py')
    assert load(e/'review1/visual_review.json')['two_scientific_figures_individually_viewed']
    for n,h in review['images'].items():assert sha(e/'review1'/n)==h
    assert sha(e/'review1/observations.json')==review['observations_sha256']
    prior=a.workspace/'baselines/catalog_local_F3_v1/evidence'
    c_files,voices=[load(prior/n) for n in ['C_files_sha256.json','voice_files_sha256.json']]
    assert len(c_files)==667 and len(voices)==82
    names=set()
    for flags in [['ls-files','-z'],['ls-files','--others','--exclude-standard','-z']]:
        names.update(subprocess.check_output(['git']+flags,cwd=repo).decode('utf8').split('\0'))
    names.discard('');assert {n for n in names if Path(n).suffix in ('.c','.h')}==set(c_files)
    index=list(csv.reader((repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig',newline='')))
    assert len(index)==668 and all(row[4]==c_files[row[0]] for row in index[1:])
    observations=review['observations']
    validation=dict(result='longer_native_joint_band_observations_verified',
        parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
        previous_goal_turn='ADI recheck gave no synthesis progress; current turn archived native regions then measured longer original-time contexts.',
        runtime_C_H_exact=667,voice_parameters_exact=82,F2_exact=True,
        known_controls=5,real_contexts=2,stereo_inputs=7,windows=959,explicit_DFT_complex_values=46032,
        max_matrix_error_FS2=audit['max_matrix_error_FS2'],max_DFT_error=audit['max_DFT_error'],max_statistic_error=audit['max_statistic_error'],
        HF_covariance_PC1_fractions=[v['HF_covariance_PC1_fraction'] for v in observations],
        original_samples_exact=True,all_scalar_trends_covariances_lags_verified=True,
        deterministic_trend_and_unqualified_residual_preserved=True,
        waveform_failure_and_corrected_roundoff_audit_kept=True,original_plan_gates_unchanged=True,
        runtime_preset=False,stochastic_law_qualified=False,independent_recordings=False,
        images_viewed=2,new_audio_or_C_or_model=False,
        default_driver_owned_take_room_changed=False,unchanged_68CTest_not_repeated=True,
        F2_F3_hearings='independently pending; no repeat, strength sweep or migration',
        E_feedback='左右关系有改善，音色仍明显电子',downloaded=False,pushed=False,
        physical_7_1_4=False,full_goal='active',
        next='Account for existing one-driver DNA/detail joint variations before fitting correlated HF modulation; inspect second-context transient origin; preserve source/event/spatial boundaries and do not force one universal law.')
    sources=[n for n in names if Path(n).suffix in ('.c','.h','.cmake','.in') or n.endswith('CMakeLists.txt')]
    sources+=list(voices)+[n for n in m['protected_before'] if n not in c_files]+list(m['sources'])
    sources+=[
        'tools/joint_envelopes_v1/README.md','tools/audit_F3_joint_envelopes_v1.py','tools/review_F3_joint_envelopes_v1.py','tools/package_F3_joint_envelopes_v1.py',
        'research/F3完整频带联合包络V1.md','README.md','AGENTS.md','handoff/C文件索引.csv','handoff/开发留痕.md','handoff/研究续接.md','handoff/当前代码阅读入口.md']
    inputs=dict(data_AGENTS=a.workspace/'AGENTS.md',segments_catalog=a.workspace/'references/segments_v1.json',
                parent_region_manifest=a.workspace/'baselines/F3_native_regions_v1/manifest.json',
                parent_region_observations=a.workspace/'baselines/F3_native_regions_v1/evidence/review1/full_band_observations.json')
    shutil.copy2(__file__,e/'executed_package.py')
    result=freeze(root,repo,sources,e,inputs,validation);verify(root)
    save(repo/'research/F3_joint_envelopes_v1_summary.json',dict(validation,**result))
    append_index(repo/'handoff/阶段索引.csv',[
        'F3_joint_envelopes_v1','baselines/F3_joint_envelopes_v1/manifest.json',result['file_count'],result['manifest_sha256'],
        '5known+2native3sec;7stereo959windows46032DFT;independentWelch-CSD-scalarOLS-cov-lags;2figures',
        '667C-H82voices/F2 exact;HFjointPC1 .454/.736;trend+transients retained;not stochastic preset;audit1float-order failure kept;no runtime/hearing changes',
        'research/F3完整频带联合包络V1.md | research/F3_joint_envelopes_v1_summary.json','baselines/F3_joint_envelopes_v1/validation.json'])
    print(result)


if __name__=='__main__':main()
