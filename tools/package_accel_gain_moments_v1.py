"""Verify every finite gain-moment array/summary and preserve exact consumed evidence."""
import argparse, csv, os, shutil, subprocess, sys
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True);parser.add_argument('--stage',choices=['freeze','verify'],required=True)
args=parser.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(args.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
from research_archive_v1 import load,save,sha,freeze,verify,append_index

root=args.workspace/'baselines/accel_gain_moments_v1'
if args.stage=='verify':print(verify(root)['file_count']);raise SystemExit
evidence=args.workspace/'references/analysis/accel_gain_moments_v1'
run=load(evidence/'observe1/report.json');audit=load(evidence/'audit1/report.json');assessment=load(evidence/'assessment1/report.json')
assert run['result']=='all12_native_gain_power_moments_and_existing_paths_complete' and len(run['observations'])==12
assert run['cases']==12 and run['continuous_runs']==36 and run['blocks']==288 and run['moment_coordinates']==8
assert run['all_block_covariances'] and not run['new_seeds'] and not run['new_audio']
assert run['not_VarS_or_conditional_quadratic_uncertainty'] and run['not_Gaussian_scores_or_confidence_intervals']
assert audit['result']=='passed' and audit['cases']==12 and audit['runs']==36 and audit['blocks']==288
assert audit['all_native_covariance_operators'] and audit['all_full64x64_block_covariances']
assert audit['all_existing_paths_and_moments'] and audit['all_signed_crosscovariances_preserved']
assert audit['not_VarS_or_conditional_quadratic_uncertainty'] and not audit['new_audio']
assert assessment['result']=='all12_finite_gain_power_moments_assessed_NOT_voice_or_VarS' and len(assessment['cases'])==12 and len(assessment['figures'])==2
assert assessment['not_VarS_or_conditional_quadratic_uncertainty'] and assessment['not_normal_scores_or_confidence_intervals'] and not assessment['new_audio']
assert audit['input_sha256']==assessment['input_sha256']==sha(evidence/'observe1/report.json') and assessment['audit_sha256']==sha(evidence/'audit1/report.json')
assert sha(evidence/'observe1/known.npz')==run['known_sha256']
sources=set(run['sources'])
for name,digest in run['sources'].items():assert sha(repo/name)==digest==sha(evidence/'observe1/exact_sources'/name)
parent=args.workspace/'baselines/accel_upper_realization_v1';assert sha(parent/'manifest.json')==run['parent_manifest_sha256']
table={v['path']:v['sha256'] for v in load(parent/'manifest.json')['files']};inputs={'parent_manifest':parent/'manifest.json'}
for name,digest in run['parent_files'].items():
    assert sha(parent/name)==digest==table[name];inputs['parent/'+name]=parent/name
previous=load(parent/'evidence/generate1/report.json')


def check(x,y):np.testing.assert_allclose(x,y,rtol=1e-12,atol=1e-14)


coordinate_blocks=0
for row,item,original in zip(run['observations'],assessment['cases'],previous['observations']):
    for key in ['segment','branch','fit_available']:assert row[key]==item[key]==original[key]
    assert row['records']==original['records'] and len(row['records'])==3
    assert sha(evidence/'observe1'/row['file'])==row['sha256']
    with np.load(evidence/'observe1'/row['file']) as f,np.load(parent/row['model_parent_file']) as model:
        assert f['actual_block'].shape==(3,8,8) and f['full_block_covariance'].shape==(64,64)
        assert f['block_lag_covariance'].shape==(8,8,8) and f['actual_run'].shape==(3,8)
        check(f['gamma'],model['L']@model['L'].T);check(f['tau'],model['parameters'][-1]);check(f['frames_per_block'],len(model['tile'])*480)
        check(f['actual_run'],f['actual_block'].mean(axis=1));check(f['actual_mean'],f['actual_run'].mean(axis=0))
        for seed,record in enumerate(row['records']):check(f['actual_run'][seed,:4],record['gain_squared_mean'])
        for a in range(8):
            for b in range(8):check(f['full_block_covariance'][a*8:(a+1)*8,b*8:(b+1)*8],f['block_lag_covariance'][abs(a-b)])
        A=np.tile(np.eye(8)/8,(1,8));check(A@f['full_block_covariance']@A.T,f['continuous_run_covariance'])
        check(f['continuous_run_covariance']/3,f['independent3_run_mean_covariance'])
        C=f['independent3_run_mean_covariance'];sd=np.sqrt(np.diag(C));check(sd,f['pooled3_sd'])
        defined=sd>0;score=np.zeros(8);score[defined]=(f['actual_mean']-f['mean'])[defined]/sd[defined]
        check(defined,f['standardized_defined']);check(score,f['descriptive_standardized_difference'])
        for reported,key in [('expected','mean'),('actual_mean','actual_mean'),('pooled3_sd','pooled3_sd'),('descriptive_standardized_difference','descriptive_standardized_difference'),('standardized_defined','standardized_defined')]:check(row[reported],f[key]);check(item[reported],f[key])
        check(item['all24_block_means'],f['actual_block']);check(item['actual3_run_means'],f['actual_run'])
        single=f['block_lag_covariance'][0];check(item['block_sd'],np.sqrt(np.diag(single)))
        check(item['continuous_run_sd'],np.sqrt(np.diag(f['continuous_run_covariance'])))
        for prefix,func in [('minimum',np.min),('maximum',np.max)]:
            check(item['actual_'+prefix+'_block'],func(f['actual_block'],axis=(0,1)));check(item['actual_'+prefix+'_run'],func(f['actual_run'],axis=0))
        naive=np.diag(single)/24;ratio=np.zeros(8);valid=naive>0;ratio[valid]=np.diag(C)[valid]/naive[valid]
        check(item['exact_over_independent8blocks_variance_ratio'],ratio);check(item['independence_ratio_defined'],valid)
        D=np.outer(sd,sd);correlation=np.zeros((8,8));valid=D>0;correlation[valid]=C[valid]/D[valid]
        check(item['pooled3_power_crosscorrelation'],correlation)
        check(item['minimum_full64x64_eigenvalue'],np.linalg.eigvalsh(f['full_block_covariance']).min())
        coordinate_blocks+=f['actual_block'].size
assert coordinate_blocks==2304
assert sum(row['branch']=='original' and row['fit_available'] for row in run['observations'])==3
assert all(not row['fit_available'] for row in run['observations'] if row['branch']!='original')
for name,folder,snapshot in [('tools/audit_accel_gain_moments_v1.py','audit1','executed_auditor.py'),('tools/assess_accel_gain_moments_v1.py','assessment1','executed_assessment.py')]:
    assert sha(repo/name)==sha(evidence/folder/snapshot);sources.add(name)
for figure in assessment['figures']:
    path=evidence/'assessment1'/figure['file'];assert sha(path)==figure['sha256']
    name='research/accel_gain_moments_v1_'+figure['file'];shutil.copy2(path,repo/name);sources.add(name)
ch=list(csv.reader((repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig')));assert len(ch)==620 and all(sha(repo/row[0])==row[4] for row in ch[1:])
voice_path=args.workspace/'baselines/idle_microtexture_c_v1/inputs/voice_files_sha256.json';voices=load(voice_path);assert len(voices)==67 and all(sha(repo/name)==digest for name,digest in voices.items())
sources.update(['tools/package_accel_gain_moments_v1.py','research/力度有限波动V1.md','AGENTS.md','handoff/研究续接.md','handoff/开发留痕.md'])
inputs.update(C_H_index=repo/'handoff/C文件索引.csv',voice_hashes=voice_path,
    conditional_parent_manifest=args.workspace/'baselines/accel_upper_conditional_v1/manifest.json',idle_pending_manifest=args.workspace/'baselines/idle_complex75_v1/manifest.json')
shutil.copy2(repo/'AGENTS.md',args.workspace/'AGENTS.md')
validation=dict(schema='vsl.accel-gain-moments-freeze/1',result='exact_native_finite_gain_power_moments_and_all_existing_paths_verified_NOT_VarS_or_voice',
    parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    previous_goal_turn_classification='progress:2f2774d exact conditional localization, independent full audit and111file verified freeze/clean commit',
    independent_audit=audit,cases=12,continuous_runs=36,blocks=288,coordinate_blocks=coordinate_blocks,
    known_Gaussian_quadrature_before_source=True,all_full64x64_native_block_covariances=True,
    all_report_arrays_and_signed_crosscovariances_verified=True,all_existing_seeds_and_full_history_preserved=True,
    adjacent_blocks_not_independent=True,paired_seeds_across_models=True,not_normal_scores_or_confidence_intervals=True,
    gain_power_moments_not_substitute_for_conditional_quadratic_or_output_VarS=True,
    full_VarS_and_conditional_quadratic_uncertainty_still_unqualified=True,
    source_cases=[row for row in assessment['cases'] if row['branch']=='original'],
    figures_viewed=True,no_failed_attempts=True,old619C_H_and67voices_exact=True,
    moving35_changed=False,runtime_changed=False,pending_idle_listening_unchanged=True,
    new_seeds=False,new_audio=False,new_runtime_profile=False,new_C=False,new_download=False,old_CTests_repeated=False,
    original_fullMSC_and_commonphase_qualifications_unwaived=True,next=assessment['next'],full_goal_complete=False)
result=freeze(root,repo,sources,evidence,inputs,validation);verify(root)
save(repo/'research/accel_gain_moments_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['accel_gain_moments_v1','baselines/accel_gain_moments_v1/manifest.json',result['file_count'],result['manifest_sha256'],
    'native48kJointg2g4;12models36runs288blocks;all64x64;independentReplay',
    'NOTVarSOrConditionalQuadraticUncertainty;noCI;619C-H67voices',
    'research/力度有限波动V1.md | research/accel_gain_moments_v1_summary.json','baselines/accel_gain_moments_v1/validation.json'])
print(result)
