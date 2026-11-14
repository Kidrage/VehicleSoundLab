"""Verify every observer bound/old realization and archive the uninformative result."""
import argparse,csv,os,shutil,subprocess,sys
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True);parser.add_argument('--stage',choices=['freeze','verify'],required=True)
args=parser.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(args.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
from research_archive_v1 import load,save,sha,freeze,verify,append_index

root=args.workspace/'baselines/accel_observer_bound_v1'
if args.stage=='verify':print(verify(root)['file_count']);raise SystemExit
evidence=args.workspace/'references/analysis/accel_observer_bound_v1'
run=load(evidence/'observe1/report.json');audit=load(evidence/'audit1/report.json');assessment=load(evidence/'assessment1/report.json')
assert run['result']=='all12_actual_energy_observer_variance_upper_bounds_complete' and run['cases']==12 and run['coordinates']==48 and len(run['observations'])==12
assert run['not_exact_variances_or_confidence_intervals'] and run['zero_lag_diagonal_pre_refilter_only'] and not run['new_audio'] and not run['new_seeds']
assert audit['result']=='passed' and audit['cases']==12 and audit['coordinates']==48
assert audit['all_native_gradient_and_operator_bounds'] and audit['all_old24block_values_unchanged'] and audit['all_expected_means_and_fixed_coordinate_tail_arithmetic']
assert audit['upper_bounds_not_exact_variances'] and not audit['new_audio']
assert assessment['result']=='all12_energy_observer_upper_bounds_assessed_NOT_acceptance' and len(assessment['cases'])==12 and len(assessment['figures'])==2
assert assessment['not_exact_variance_or_normal_CI'] and assessment['full_finite_observer_discrepancy_not_settled'] and not assessment['new_audio']
assert audit['input_sha256']==assessment['input_sha256']==sha(evidence/'observe1/report.json') and assessment['audit_sha256']==sha(evidence/'audit1/report.json')
assert sha(evidence/'observe1/known.npz')==run['known_sha256']
assert run['known']['exact_Wick8_and_lognormal4_before_source'] and run['known']['all_variance_and_gradient_bounds_hold']
sources=set(run['sources'])
for name,digest in run['sources'].items():assert sha(repo/name)==digest==sha(evidence/'observe1/exact_sources'/name)
parent=args.workspace/'baselines/accel_upper_conditional_v1';assert sha(parent/'manifest.json')==run['parent_manifest_sha256']
table={v['path']:v['sha256'] for v in load(parent/'manifest.json')['files']};inputs={'parent_manifest':parent/'manifest.json'}
for name,digest in run['parent_files'].items():
    assert sha(parent/name)==digest==table[name];inputs['parent/'+name]=parent/name


def check(x,y):np.testing.assert_allclose(x,y,rtol=1e-12,atol=1e-14)


vacuous=dict(path=0,carrier=0,total=0);coordinates=0
for row,item in zip(run['observations'],assessment['cases']):
    for key in ['segment','branch','fit_available']:assert row[key]==item[key]
    assert sha(evidence/'observe1'/row['file'])==row['sha256']
    with np.load(evidence/'observe1'/row['file']) as f,np.load(parent/row['old_parent_file']) as old,np.load(parent/row['model_parent_file']) as model:
        assert f['actual'].shape==f['conditional'].shape==(3,8,4)
        for key in ['actual','conditional','source_target']:check(f[key],old[key])
        check(f['expected'],model['prediction'][5].diagonal());check(f['gamma'],np.diag(model['L']@model['L'].T));check(f['tile'],model['tile'])
        check(item['expected'],f['expected']);check(item['source_target'],f['source_target'])
        check(item['actual_mean'],f['actual'].mean(axis=(0,1)));check(item['conditional_mean'],f['conditional'].mean(axis=(0,1)))
        for name,values in [('path',f['conditional']-f['expected']),('carrier',f['actual']-f['conditional']),('total',f['actual']-f['expected'])]:
            difference=values.mean(axis=(0,1));check(f[name+'_difference'],difference)
            check(item['bounds'][name]['all24_effects'],values);check(item['bounds'][name]['difference'],difference)
            bound=f[name+'_variance_bound_pooled'];check(item['bounds'][name]['variance_upper'],bound);check(item['bounds'][name]['sqrt_variance_upper'],np.sqrt(bound))
            check(bound,f[name+'_variance_bound_run']/3)
            probability=np.array([1. if d==0 else min(1.,b/d**2) for b,d in zip(bound,difference)])
            check(f[name+'_marginal_Chebyshev_upper'],probability);check(item['bounds'][name]['marginal_Chebyshev_upper'],probability)
            vacuous[name]+=int(np.sum(probability==1.))
        check(f['total_variance_bound_run'],f['path_variance_bound_run']+f['carrier_variance_bound_run'])
        check(f['total_variance_bound_pooled'],f['path_variance_bound_pooled']+f['carrier_variance_bound_pooled'])
        check(f['path_variance_bound_run'],f['latent_covariance_norm_bound']*f['conditional_gradient_bound_oneblock']/8)
        check(f['carrier_variance_bound_run'],f['normalized_carrier_covariance_norm_bound']*f['carrier_normalized_gradient_bound_oneblock']/8)
        for i,cell in enumerate(row['bounds']):
            for key,value in cell.items():check(value,f[key][i])
        coordinates+=4
assert coordinates==48 and vacuous==assessment['vacuous_counts']==dict(path=48,carrier=48,total=48)
assert sum(row['branch']=='original' and row['fit_available'] for row in run['observations'])==3
assert all(not row['fit_available'] for row in run['observations'] if row['branch']!='original')
for name,folder,snapshot in [('tools/audit_accel_observer_bound_v1.py','audit1','executed_auditor.py'),('tools/assess_accel_observer_bound_v1.py','assessment1','executed_assessment.py')]:
    assert sha(repo/name)==sha(evidence/folder/snapshot);sources.add(name)
for figure in assessment['figures']:
    path=evidence/'assessment1'/figure['file'];assert sha(path)==figure['sha256']
    name='research/accel_observer_bound_v1_'+figure['file'];shutil.copy2(path,repo/name);sources.add(name)
ch=list(csv.reader((repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig')));assert len(ch)==620 and all(sha(repo/row[0])==row[4] for row in ch[1:])
voice_path=args.workspace/'baselines/idle_microtexture_c_v1/inputs/voice_files_sha256.json';voices=load(voice_path);assert len(voices)==67 and all(sha(repo/name)==digest for name,digest in voices.items())
sources.update(['tools/package_accel_observer_bound_v1.py','research/能量观察方差上界V1.md','AGENTS.md','handoff/研究续接.md','handoff/开发留痕.md'])
inputs.update(C_H_index=repo/'handoff/C文件索引.csv',voice_hashes=voice_path,
    power_moments_parent_manifest=args.workspace/'baselines/accel_gain_moments_v1/manifest.json',idle_pending_manifest=args.workspace/'baselines/idle_complex75_v1/manifest.json')
shutil.copy2(repo/'AGENTS.md',args.workspace/'AGENTS.md')
validation=dict(schema='vsl.accel-observer-bound-freeze/1',result='actual_observer_analytic_upper_bounds_numeric_verified_BUT_all_tails_vacuous_NOT_acceptance',
    parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    previous_goal_turn_classification='progress:786b195 native finite joint gain-power covariance/full36path audit/64file freeze and clean commit',
    independent_audit=audit,cases=12,coordinates=48,known_exact_Wick8_and_lognormal4_before_source=True,
    all_full_native_gradient_bounds_finite_operator_norms_and_means_verified=True,
    all_original24block_values_and48bound_sets_preserved=True,all_summary_metrics_and_tail_arithmetic_verified=True,
    vacuous_counts=vacuous,upper_variance_bounds_not_exact_variances=True,
    all_vacuous_probability_upper_bounds_not_acceptance=True,full_observer_discrepancy_unsettled=True,
    zero_lag_diagonal_pre_refilter_only=True,no_normal_CI_or_postselected_familywise_claim=True,
    source_cases=[row for row in assessment['cases'] if row['branch']=='original'],
    figures_viewed=True,no_failed_attempts=True,numeric_formula_audit_not_formal_interval_proof=True,
    old619C_H_and67voices_exact=True,moving35_changed=False,runtime_changed=False,pending_idle_listening_unchanged=True,
    new_audio=False,new_seeds=False,new_C=False,new_download=False,old_CTests_repeated=False,
    original_fullMSC_and_commonphase_qualifications_unwaived=True,next=assessment['next'],full_goal_complete=False)
result=freeze(root,repo,sources,evidence,inputs,validation);verify(root)
save(repo/'research/accel_observer_bound_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['accel_observer_bound_v1','baselines/accel_observer_bound_v1/manifest.json',result['file_count'],result['manifest_sha256'],
    'actualObserverPoincare;nativeSignedGroups;exactKnownWick8;all48IndependentAudit',
    'all48x3ChebyshevUpper1Vacuous;NOTexactVarOrAcceptance;619C-H67voices',
    'research/能量观察方差上界V1.md | research/accel_observer_bound_v1_summary.json','baselines/accel_observer_bound_v1/validation.json'])
print(result)
