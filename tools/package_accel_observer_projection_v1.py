"""Verify every signed projection/variance bracket and freeze exact sources and inputs."""
import argparse,csv,os,shutil,subprocess,sys
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True);parser.add_argument('--stage',choices=['freeze','verify'],required=True)
args=parser.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(args.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
from research_archive_v1 import load,save,sha,freeze,verify,append_index

root=args.workspace/'baselines/accel_observer_projection_v1'
if args.stage=='verify':print(verify(root)['file_count']);raise SystemExit
evidence=args.workspace/'references/analysis/accel_observer_projection_v1'
run=load(evidence/'observe1/report.json');audit=load(evidence/'audit1/report.json');assessment=load(evidence/'assessment2/report.json');first_assessment=load(evidence/'assessment1/report.json')
assert run['result']=='all12_signed_native_observer_projections_and_remainders_complete' and run['cases']==12 and run['coordinates']==48 and len(run['observations'])==12
assert run['first_projection_not_full_variance'] and run['variance_brackets_not_CI'] and not run['new_audio'] and not run['new_seeds']
assert audit['result']=='passed' and audit['cases']==12 and audit['coordinates']==48
assert audit['all_signed_native_coefficients'] and audit['all_whole_continuous_OU_quadratics'] and audit['all_integral_remainders_bounds_and_old_values'] and audit['first_projection_not_complete_variance']
assert assessment['result']=='all12_signed_projection_brackets_assessed_NOT_acceptance' and len(assessment['cases'])==12 and len(assessment['figures'])==2
assert assessment['first_projection_not_exact_full_variance'] and assessment['variance_brackets_not_confidence_intervals'] and assessment['full_observer_discrepancy_not_settled']
assert audit['input_sha256']==assessment['input_sha256']==sha(evidence/'observe1/report.json') and assessment['audit_sha256']==sha(evidence/'audit1/report.json')
assert sha(evidence/'observe1/known.npz')==run['known_sha256'] and run['known']['exact_four_time_variance_brackets_before_source']
assert {k:v for k,v in first_assessment.items() if k!='figures'}=={k:v for k,v in assessment.items() if k!='figures'}
assert first_assessment['figures'][0]==assessment['figures'][0]
before=(evidence/'assessment1/executed_assessment.py').read_text(encoding='utf-8');after=(evidence/'assessment2/executed_assessment.py').read_text(encoding='utf-8')
assert before.replace('values[i,j]:.3f','values[i,j]:.3g')==after
sources=set(run['sources'])
for name,digest in run['sources'].items():assert sha(repo/name)==digest==sha(evidence/'observe1/exact_sources'/name)
parent=args.workspace/'baselines/accel_observer_bound_v1';assert sha(parent/'manifest.json')==run['parent_manifest_sha256']
table={v['path']:v['sha256'] for v in load(parent/'manifest.json')['files']};inputs={'parent_manifest':parent/'manifest.json'}
for name,digest in run['parent_files'].items():
    assert sha(parent/name)==digest==table[name];inputs['parent/'+name]=parent/name


def check(x,y):np.testing.assert_allclose(x,y,rtol=1e-12,atol=1e-14)


vacuous=dict(path=0,total=0);coordinates=0;improved=0
for row,item in zip(run['observations'],assessment['cases']):
    for key in ['segment','branch','fit_available']:assert row[key]==item[key]
    assert sha(evidence/'observe1'/row['file'])==row['sha256']
    with np.load(evidence/'observe1'/row['file']) as f,np.load(parent/row['old_parent_file']) as old:
        assert f['actual'].shape==f['conditional'].shape==(3,8,4)
        assert f['signed_coefficient'].shape==f['absolute_coefficient'].shape==(len(f['tile'])*480,4)
        for key in ['actual','conditional','source_target','gamma','tau','tile','carrier_R','path_difference','carrier_difference','total_difference']:check(f[key],old[key])
        check(f['expected'],old['expected']);check(f['signed_coefficient'].sum(axis=0),f['expected'])
        check(f['first_variance_run'],16*f['gamma']*f['signed_ou_quadratic_run'])
        check(f['remainder_variance_upper_run'],f['exponential_remainder']*f['absolute_ou_quadratic_run'])
        check(f['variance_upper_run'],f['first_variance_run']+f['remainder_variance_upper_run'])
        for name in ['first_variance','remainder_variance_upper','variance_upper']:check(f[name+'_pooled'],f[name+'_run']/3)
        check(f['prior_path_upper'],old['path_variance_bound_pooled']);check(f['prior_carrier_upper'],old['carrier_variance_bound_pooled']);check(f['prior_total_upper'],old['total_variance_bound_pooled'])
        combined=np.minimum(f['variance_upper_pooled'],f['prior_path_upper']);check(f['combined_path_upper'],combined)
        check(f['combined_total_upper'],combined+f['prior_carrier_upper']);assert np.all(f['first_variance_pooled']<=combined+1e-12)
        improved+=int(np.sum(combined<f['prior_path_upper']))
        for reported,key in [('expected','expected'),('first_lower','first_variance_pooled'),('remainder_upper','remainder_variance_upper_pooled'),('new_projection_upper','variance_upper_pooled'),
            ('prior_path_upper','prior_path_upper'),('combined_path_upper','combined_path_upper'),('prior_carrier_upper','prior_carrier_upper'),('prior_total_upper','prior_total_upper'),
            ('combined_total_upper','combined_total_upper'),('path_difference','path_difference'),('carrier_difference','carrier_difference'),('total_difference','total_difference'),
            ('all24_actual','actual'),('all24_conditional','conditional')]:check(item[reported],f[key])
        check(item['combined_over_prior_path_ratio'],combined/f['prior_path_upper']);check(item['combined_over_prior_total_ratio'],f['combined_total_upper']/f['prior_total_upper'])
        for name in ['path','total']:
            delta=f[name+'_difference'];bound=f['combined_'+name+'_upper'];prob=np.array([1. if d==0 else min(1.,v/d**2) for v,d in zip(bound,delta)])
            check(f[name+'_marginal_tail_upper'],prob);check(item[name+'_tail_upper'],prob);vacuous[name]+=int(np.sum(prob==1.))
        for reported,key in [('first_variance_pooled','first_variance_pooled'),('projection_upper_pooled','variance_upper_pooled'),('combined_path_upper','combined_path_upper'),
            ('combined_total_upper','combined_total_upper'),('path_tail_upper','path_marginal_tail_upper'),('total_tail_upper','total_marginal_tail_upper')]:check(row[reported],f[key])
        coordinates+=4
assert coordinates==improved==48 and vacuous==assessment['vacuous_counts']==dict(path=48,total=48)
assert sum(row['branch']=='original' and row['fit_available'] for row in run['observations'])==3
assert all(not row['fit_available'] for row in run['observations'] if row['branch']!='original')
for name,folder,snapshot in [('tools/audit_accel_observer_projection_v1.py','audit1','executed_auditor.py'),('tools/assess_accel_observer_projection_v1.py','assessment2','executed_assessment.py')]:
    assert sha(repo/name)==sha(evidence/folder/snapshot);sources.add(name)
for figure in assessment['figures']:
    path=evidence/'assessment2'/figure['file'];assert sha(path)==figure['sha256']
    name='research/accel_observer_projection_v1_'+figure['file'];shutil.copy2(path,repo/name);sources.add(name)
ch=list(csv.reader((repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig')));assert len(ch)==620 and all(sha(repo/row[0])==row[4] for row in ch[1:])
voice_path=args.workspace/'baselines/idle_microtexture_c_v1/inputs/voice_files_sha256.json';voices=load(voice_path);assert len(voices)==67 and all(sha(repo/name)==digest for name,digest in voices.items())
sources.update(['tools/package_accel_observer_projection_v1.py','research/能量观察有符号投影V1.md','research/accel_observer_projection_v1_display_followup.json','AGENTS.md','handoff/研究续接.md','handoff/开发留痕.md'])
inputs.update(C_H_index=repo/'handoff/C文件索引.csv',voice_hashes=voice_path,idle_pending_manifest=args.workspace/'baselines/idle_complex75_v1/manifest.json')
shutil.copy2(repo/'AGENTS.md',args.workspace/'AGENTS.md')
validation=dict(schema='vsl.accel-observer-projection-freeze/1',result='signed_exact_first_projection_and_positive_remainder_bounds_verified_BUT_all_tails_vacuous',
    parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),previous_goal_turn_classification='progress:1595dc0 actual observer conservative bound, complete independent audit and84file verified freeze/clean commit',
    independent_audit=audit,cases=12,coordinates=48,all48path_upper_bounds_tighter=True,
    exact_small_four_time_variance_brackets_before_source=True,all_signed_native_coefficients_and_whole_continuous_OU_contractions=True,
    positive_series_remainder_independently_integrated=True,all_old24block_values_and_all_summary_metrics_verified=True,
    first_projection_not_full_variance=True,variance_brackets_not_confidence_intervals=True,vacuous_counts=vacuous,full_finite_observer_discrepancy_unsettled=True,
    source_cases=[row for row in assessment['cases'] if row['branch']=='original'],
    assessment1_preserved_assessment2_display_only=True,all_assessment_metrics_and_first_figure_identical=True,
    display_followup_sha256=sha(repo/'research/accel_observer_projection_v1_display_followup.json'),figures_viewed=True,no_numerical_failed_attempts=True,
    old619C_H_and67voices_exact=True,moving35_changed=False,runtime_changed=False,pending_idle_listening_unchanged=True,
    new_audio=False,new_seeds=False,new_C=False,new_download=False,old_CTests_repeated=False,
    original_fullMSC_and_commonphase_qualifications_unwaived=True,next=assessment['next'],full_goal_complete=False)
result=freeze(root,repo,sources,evidence,inputs,validation);verify(root)
save(repo/'research/accel_observer_projection_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['accel_observer_projection_v1','baselines/accel_observer_projection_v1/manifest.json',result['file_count'],result['manifest_sha256'],
    'signedNativeFirstChaos;positiveRemainderBound;all48AR1/FFT/integralAudit',
    'all48TighterButAll96TailUpper1;NOTfullVarOrCI;619C-H67voices',
    'research/能量观察有符号投影V1.md | research/accel_observer_projection_v1_summary.json','baselines/accel_observer_projection_v1/validation.json'])
print(result)
