"""Validate every saved second-chaos contraction, protect runtime files, and freeze evidence."""
import argparse,csv,os,shutil,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--stage',choices=['freeze','verify'],required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
from research_archive_v1 import load,save,sha,freeze,verify,append_index

root=a.workspace/'baselines/accel_observer_second_v1'
if a.stage=='verify':print(verify(root)['file_count']);raise SystemExit
evidence=a.workspace/'references/analysis/accel_observer_second_v1'
run=load(evidence/'observe1/report.json');audit=load(evidence/'audit2/report.json');assessment=load(evidence/'assessment1/report.json')
assert run['result']=='all12_full_native_second_chaos_and_cubic_remainders_complete' and run['coordinates']==48
assert audit['result']=='passed' and audit['coordinates']==48 and audit['cases']==12
assert audit['followup_known']['passed'] and not audit['full_variance_or_CI_qualified']
assert audit['input_sha256']==assessment['input_sha256']==sha(evidence/'observe1/report.json')
assert assessment['audit_sha256']==sha(evidence/'audit2/report.json') and len(assessment['cases'])==12
assert run['known']['maximum_dense_or_four_time_error']<1e-10 and sha(evidence/'observe1/known.npz')==run['known_sha256']
sources=set(run['sources'])
for name,digest in run['sources'].items():assert sha(repo/name)==digest==sha(evidence/'observe1/exact_sources'/name)
for name in ['tools/audit_accel_observer_second_v1.py','tools/accel_observer_second_v1/independent.py','research/accel_observer_second_v1_audit_followup.json']:
    assert sha(repo/name)==sha(evidence/'audit2/exact_sources'/name);sources.add(name)
assert sha(repo/'tools/assess_accel_observer_second_v1.py')==sha(evidence/'assessment1/executed_assessment.py')
sources.add('tools/assess_accel_observer_second_v1.py')
parent=a.workspace/'baselines/accel_observer_projection_v1';assert sha(parent/'manifest.json')==run['parent_manifest_sha256']
table={x['path']:x['sha256'] for x in load(parent/'manifest.json')['files']};inputs={'parent_manifest':parent/'manifest.json'}
for name,digest in run['parent_files'].items():
    assert sha(parent/name)==digest==table[name];inputs['parent/'+name]=parent/name


def check(x,y):np.testing.assert_allclose(x,y,rtol=1e-12,atol=1e-14)


counts=dict(path=0,total=0);improved=0
for row,item in zip(run['observations'],assessment['cases']):
    assert all(row[k]==item[k] for k in ['segment','branch','fit_available'])
    assert sha(evidence/'observe1'/row['file'])==row['sha256']
    for entry in row['local_files']:assert sha(evidence/'observe1'/entry['file'])==entry['sha256']
    with np.load(evidence/'observe1'/row['file']) as f,np.load(parent/row['old_parent_file']) as old:
        assert f['actual'].shape==f['conditional'].shape==(3,8,4)
        for key in ['actual','conditional','source_target','gamma','tau','tile','carrier_R','path_difference','carrier_difference','total_difference']:
            assert np.array_equal(f[key],old[key]);check(item[key],f[key]) if key in item else None
        for key in ['expected','first_variance_pooled']:check(f[key],old[key])
        check(f['first_variance_run'],16*f['gamma']*f['signed_ou_quadratic'])
        check(f['second_variance_run'],32*f['gamma']**2*(f['term_diagonal']+2*f['term_mixed']+f['term_trace']))
        check(f['remainder_upper_run'],f['exponential_remainder_cubic']*f['absolute_ou_quadratic'])
        check(f['variance_lower_run'],f['first_variance_run']+f['second_variance_run'])
        check(f['variance_upper_run'],f['variance_lower_run']+f['remainder_upper_run'])
        for key in ['first_variance','second_variance','remainder_upper','variance_lower','variance_upper']:check(f[key+'_pooled'],f[key+'_run']/3)
        check(f['prior_path_upper'],old['combined_path_upper']);check(f['prior_total_upper'],old['combined_total_upper']);check(f['prior_carrier_upper'],old['prior_carrier_upper'])
        check(f['combined_path_upper'],np.minimum(f['variance_upper_pooled'],f['prior_path_upper']))
        check(f['combined_total_upper'],f['combined_path_upper']+f['prior_carrier_upper'])
        assert np.all(f['second_variance_pooled']>=0) and np.all(f['variance_lower_pooled']<=f['combined_path_upper']+1e-12)
        for key,value in item.items():
            if key in f:check(value,f[key])
        check(item['upper_ratio'],f['combined_path_upper']/f['prior_path_upper'])
        for report_key,key in [('first','first_variance_pooled'),('second','second_variance_pooled'),('lower','variance_lower_pooled'),('upper','combined_path_upper'),('total_upper','combined_total_upper')]:check(row[report_key],f[key])
        improved+=int(np.sum(f['combined_path_upper']<f['prior_path_upper']))
        for name in ['path','total']:
            prob=np.array([1. if d==0 else min(1.,v/d**2) for v,d in zip(f['combined_'+name+'_upper'],f[name+'_difference'])])
            check(prob,f[name+'_tail_upper']);counts[name]+=int(np.sum(prob==1))
assert counts==assessment['vacuous_counts'] and improved==assessment['improved_coordinates']
for figure in assessment['figures']:
    path=evidence/'assessment1'/figure['file'];assert sha(path)==figure['sha256']
    name='research/accel_observer_second_v1_'+figure['file'];shutil.copy2(path,repo/name);sources.add(name)
ch=list(csv.reader((repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig')))
assert len(ch)==620 and all(sha(repo/row[0])==row[4] for row in ch[1:])
voice_path=a.workspace/'baselines/idle_microtexture_c_v1/inputs/voice_files_sha256.json';voices=load(voice_path)
assert len(voices)==67 and all(sha(repo/name)==digest for name,digest in voices.items())
sources.update(['tools/package_accel_observer_second_v1.py','research/能量观察二阶分量V1.md','research/怠速优化当前状态.md','README.md','AGENTS.md','handoff/研究续接.md','handoff/开发留痕.md'])
inputs.update(C_H_index=repo/'handoff/C文件索引.csv',voice_hashes=voice_path,idle_pending_manifest=a.workspace/'baselines/idle_complex75_v1/manifest.json')
shutil.copy2(repo/'AGENTS.md',a.workspace/'AGENTS.md')
validation=dict(schema='vsl.accel-observer-second-freeze/1',result='exact_full_second_chaos_and_positive_cubic_remainder_verified_NOT_timbre_or_full_uncertainty_approval',
    parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),independent_audit=audit,cases=12,coordinates=48,
    all_summary_metrics_and_old_observations_verified=True,all_local_native_vectors_and_contractions_verified=True,
    source_dense_temporary_matrices_not_archived=True,producer_missing_scale_reversal_controls_truthfully_followed_up=True,
    audit1_performance_interruption_preserved=load(evidence/'audit1/interruption.json'),
    first_packager_path_error_preserved=load(evidence/'package1/report.json'),
    improved_coordinates=improved,vacuous_counts=counts,figures_viewed=True,full_variance_or_CI_qualified=False,
    old619C_H_and67voices_exact=True,moving35_changed=False,runtime_changed=False,pending_idle_listening_unchanged=True,
    new_audio=False,new_seeds=False,new_C=False,new_download=False,old_CTests_repeated=False,
    original_fullMSC_and_commonphase_qualifications_unwaived=True,next=assessment['next'],full_goal_complete=False)
result=freeze(root,repo,sources,evidence,inputs,validation);verify(root)
save(repo/'research/accel_observer_second_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['accel_observer_second_v1','baselines/accel_observer_second_v1/manifest.json',result['file_count'],result['manifest_sha256'],
    'fullNativeSecondChaos;explicitPairFFT/AR1/integralAudit',str(counts)+';NOTfullVarOrTimbre;619C-H67voices',
    'research/能量观察二阶分量V1.md | research/accel_observer_second_v1_summary.json','baselines/accel_observer_second_v1/validation.json'])
print(result)
