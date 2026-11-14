"""Verify every assessment/localization metric and freeze all continuous arrays and inputs."""
import argparse,csv,math,os,shutil,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--stage',choices=['freeze','verify'],required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
from research_archive_v1 import load,save,sha,freeze,verify,append_index

root=a.workspace/'baselines/accel_upper_realization_v1'
if a.stage=='verify':print(verify(root)['file_count']);raise SystemExit
evidence=a.workspace/'references/analysis/accel_upper_realization_v1';run=load(evidence/'generate1/report.json');audit=load(evidence/'audit1/report.json')
assessment=load(evidence/'assessment1/report.json');diagnostic=load(evidence/'diagnostic1/report.json')
assert run['result']=='all12_continuous_source_realizations_and576observations_complete' and len(run['observations'])==12 and run['records']==36 and run['blocks_observed']==576
assert audit['result']=='passed' and audit['cases']==12 and audit['records']==36 and audit['blocks']==576 and audit['window_CSDs']==16704
assert audit['all_full_source_streams_replayed'] and audit['all576signed_observations'] and audit['all_full_pooled_CSDs']
assert assessment['result']=='all12_continuous_source_realizations_assessed_NOT_voice' and len(assessment['cases'])==12
assert diagnostic['result']=='all12_existing_discrepancies_localized_no_new_generation' and len(diagnostic['cases'])==12
assert audit['input_sha256']==assessment['input_sha256']==sha(evidence/'generate1/report.json') and assessment['audit_sha256']==sha(evidence/'audit1/report.json')
assert diagnostic['input_sha256']==sha(evidence/'assessment1/report.json') and diagnostic['plan_sha256']==sha(evidence/'diagnostic1/followup.json')==sha(repo/'research/accel_upper_realization_v1_followup.json')
assert sha(evidence/'generate1/known.npz')==run['known_sha256'];sources=set(run['sources'])
for name,digest in run['sources'].items():assert sha(repo/name)==digest==sha(evidence/'generate1/exact_sources'/name)
parent=a.workspace/'baselines/accel_upper_coloured_v1';assert sha(parent/'manifest.json')==run['parent_manifest_sha256']
inputs={'parent_manifest':parent/'manifest.json'};table={v['path']:v['sha256'] for v in load(parent/'manifest.json')['files']}
for name,digest in run['parent_files'].items():
    assert sha(parent/name)==digest==table[name];inputs['parent/'+name]=parent/name
M=np.array([[1.,0.,1.,0.],[0.,1.,0.,1.]]);hz=np.arange(6001)*4;selected=(hz>=4000)&(hz<14000);summary_count=0
def check(x,y):np.testing.assert_allclose(x,y,rtol=1e-11,atol=1e-13)

def independent_summaries(C):
    global summary_count
    S=np.einsum('ai,fij,bj->fab',M,C,M);result=[]
    for lo,hi in [(0,4000),(4000,8000),(8000,14000),(14000,24000)]:
        kk=np.flatnonzero((hz>=lo)&((hz<hi) if hi<24000 else (hz<=hi)));P=S[kk][:,[0,1],[0,1]].real
        coordinate=np.array([math.fsum(C[kk,i,i].real)*4 for i in range(4)]);power=np.array([math.fsum(P[:,i])*4 for i in range(2)])
        cross=complex(math.fsum(S[kk,0,1].real),math.fsum(S[kk,0,1].imag))*4;norm=cross/math.sqrt(np.prod(power)) if min(power)>0 else 0j
        valid=[k for k in range(len(kk)) if min(P[k])>0];weight=math.fsum(P[k].sum() for k in valid)
        msc=math.fsum(abs(S[kk[k],0,1])**2/(P[k,0]*P[k,1])*P[k].sum() for k in valid)/weight if weight>0 else 0.
        result.append(dict(band_hz=[lo,hi],coordinate_power=coordinate,stereo_power=power,integrated_normalized_LR=np.array([norm.real,norm.imag]),
            power_weighted_MSC=msc,defined_stereo_bins=len(valid),total_stereo_bins=len(kk)));summary_count+=1
    return result

records=0;native_frames=0
for row,item,diag in zip(run['observations'],assessment['cases'],diagnostic['cases']):
    assert row['segment']==item['segment']==diag['segment'] and row['branch']==item['branch']==diag['branch'] and row['fit_available']==item['fit_available']==diag['fit_available']
    assert sha(evidence/'generate1'/row['file'])==row['sha256'] and sha(evidence/'assessment1'/item['file'])==item['sha256']
    with np.load(evidence/'assessment1'/item['file']) as f,np.load(evidence/'generate1'/row['file']) as model:
        check(f['energy_expected'],model['energy_expected']);check(f['source_target'],model['source_target'])
        for index,record in enumerate(row['records']):
            assert sha(evidence/'generate1'/record['observation_file'])==record['observation_sha256']
            with np.load(evidence/'generate1'/record['observation_file']) as observed:
                for stage in ['raw','refilter']:
                    file=record['files'][stage];path=evidence/'generate1'/file['file'];assert sha(path)==file['sha256']
                    array=np.load(path,mmap_mode='r');assert array.shape==(record['frames'],4) and array.dtype==np.float64
                    for key in ['theoretical_normalized','measured_normalized','power_mean','pooled_spectrum']:check(f[stage+'_'+key][index],observed[stage+'_'+key])
            records+=1;native_frames+=record['frames']
        for stage,metrics in item['stages'].items():
            primary=f[stage+'_theoretical_normalized'];finite=f[stage+'_measured_normalized'];mean=primary.mean(axis=(0,1));finite_mean=finite.mean(axis=(0,1));run_means=primary.mean(axis=1)
            check(metrics['primary_mean'],mean);check(metrics['finite_mean'],finite_mean);check(metrics['run_means'],run_means)
            check(metrics['denominator_effect_max'],abs(finite_mean-mean).max());assert metrics['pre_refilter_energy_expectation_applies']==(stage=='raw')
            P=model['theoretical_power'] if stage=='raw' else model['filtered_theoretical_power'];check(metrics['run_power_db'],10*np.log10(f[stage+'_power_mean'].mean(axis=1)/P))
            if stage=='raw':
                expected=f['energy_expected'];target=f['source_target']
                for key,v in dict(primary_mean_prediction_max_error=abs(mean-expected).max(),primary_mean_prediction_rms_error=np.mean((mean-expected)**2)**.5,
                    finite_mean_prediction_max_difference=abs(finite_mean-expected).max(),primary_mean_source_cost=np.sum((mean-target)**2)/2,
                    finite_mean_source_cost=np.sum((finite_mean-target)**2)/2,theory_source_cost=np.sum((expected-target)**2)/2).items():check(metrics[key],v)
                check(metrics['all3_run_prediction_max_errors'],abs(run_means-expected).max(axis=(1,2,3)))
            C=f[stage+'_pooled_spectrum'].mean(axis=0);E=f[stage+'_expected_spectrum'];check(E,model['Welch_'+stage+'_expected'])
            actual=independent_summaries(C);predicted=independent_summaries(E)
            for b,(aa,ee,budget) in enumerate(zip(actual,predicted,metrics['spectral_budgets'])):
                for table1,table2 in [(metrics['actual_summary'][b],aa),(metrics['expected_summary'][b],ee)]:
                    for key in ee:check(table1[key],table2[key])
                check(budget['stereo_power_db'],10*np.log10(aa['stereo_power']/ee['stereo_power']));check(budget['coordinate_power_db'],10*np.log10(aa['coordinate_power']/ee['coordinate_power']))
                check(budget['integrated_LR_error'],aa['integrated_normalized_LR']-ee['integrated_normalized_LR']);check(budget['pooled_MSC'],aa['power_weighted_MSC']);check(budget['expected_spectrum_MSC'],ee['power_weighted_MSC'])
            A=np.einsum('ai,fij,bj->fab',M,C,M)[:,[0,1],[0,1]].real;EP=np.einsum('ai,fij,bj->fab',M,E,M)[:,[0,1],[0,1]].real
            for d in metrics['detailed_spectral_error']:
                ch=d['channel'];weight=EP[selected,ch];error=abs(10*np.log10(A[selected,ch]/weight));assert d['bins']==2500
                check(d['expected_power_weighted_absolute_db'],np.dot(weight,error)/weight.sum());check(d['maximum_absolute_db'],error.max())
        primary=f['raw_theoretical_normalized'];finite=f['raw_measured_normalized'];expected=f['energy_expected'];delta=primary.mean(axis=(0,1))-expected
        cell=tuple(int(v) for v in np.unravel_index(abs(delta).argmax(),delta.shape));assert diag['worst_cell']==list(cell) and diag['lag_ms']==(cell[0]-5)*10
        values=primary[:,:,cell[0],cell[1],cell[2]];other=finite[:,:,cell[0],cell[1],cell[2]];contributions=(values-expected[cell])/24
        check(diag['full_mean_error'],delta);check(diag['max_over_lag_error'],abs(delta).max(axis=0));check(diag['expected'],expected[cell]);check(diag['source_target'],f['source_target'][cell])
        check(diag['primary_mean'],values.mean());check(diag['finite_mean'],other.mean());check(diag['signed_mean_error'],delta[cell]);check(diag['run_means'],values.mean(axis=1))
        check(diag['all24_primary'],values);check(diag['all24_finite'],other);check(diag['all24_mean_error_contributions'],contributions)
        check(np.sum(contributions),diag['signed_mean_error']);check(diag['largest_absolute_single_block_contribution'],abs(contributions).max());assert diag['no_block_removed']
assert records==36 and summary_count==192
for name,folder,executed in [('tools/audit_accel_upper_realization_v1.py','audit1','executed_auditor.py'),('tools/assess_accel_upper_realization_v1.py','assessment1','executed_assessment.py'),('tools/diagnose_accel_upper_realization_v1.py','diagnostic1','executed_diagnostic.py')]:
    assert sha(repo/name)==sha(evidence/folder/executed);sources.add(name)
for report,folder in [(assessment,'assessment1'),(diagnostic,'diagnostic1')]:
    for fig in report['figures']:
        path=evidence/folder/fig['file'];assert sha(path)==fig['sha256'];name='research/accel_upper_realization_v1_'+fig['file'];shutil.copy2(path,repo/name);sources.add(name)
ch=list(csv.reader((repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig')));assert len(ch)==620 and all(sha(repo/row[0])==row[4] for row in ch[1:])
voice_path=a.workspace/'baselines/idle_microtexture_c_v1/inputs/voice_files_sha256.json';voices=load(voice_path);assert len(voices)==67 and all(sha(repo/name)==digest for name,digest in voices.items())
sources.update(['tools/package_accel_upper_realization_v1.py','research/素材持续生成与实测V1.md','research/accel_upper_realization_v1_followup.json','AGENTS.md','handoff/研究续接.md','handoff/开发留痕.md'])
inputs.update(C_H_index=repo/'handoff/C文件索引.csv',voice_hashes=voice_path,idle_pending_manifest=a.workspace/'baselines/idle_complex75_v1/manifest.json')
shutil.copy2(repo/'AGENTS.md',a.workspace/'AGENTS.md')
validation=dict(schema='vsl.accel-upper-realization-freeze/1',result='all_continuous_native_generation_and_observations_numeric_verified_NOT_statistical_or_voice_acceptance',
    parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    previous_goal_turn_classification='progress:25ba234 actual source-shaped joint inverse/all source fits, complete independent audits and archive, clean verified',
    independent_audit=audit,all12cases36runs576blocks=True,all_full_float64_outputs_preserved=True,native_frames_per_stage=native_frames,
    all192summary_rows_and_all_assessment_metrics_verified=True,all12diagnostic_cells_and24block_arithmetic_verified=True,
    diagnostic_declared_after_assessment=True,no_extra_seeds_or_block_deletion=True,figures_viewed=True,
    pre_refilter_theoretical_and_finite_power_denominators_distinct=True,post_refilter_fourth_moment_still_not_qualified=True,
    finite_realization_statistical_mean_agreement_not_qualified=True,material_fifth2_high_order_variability_preserved=True,
    only3independent_runs_per_case_not_confidence_intervals=True,unavailable_controls_diagnostic_only=True,
    old619C_H_and67voices_exact=True,moving35_changed=False,runtime_changed=False,pending_idle_listening_unchanged=True,
    new_listening_audio=False,new_runtime_profile=False,new_C=False,new_download=False,old_CTests_repeated=False,
    full_MSC_original_gate_still_unpassed=True,original_common_phase_qualification_unwaived=True,next=diagnostic['next'],full_goal_complete=False)
result=freeze(root,repo,sources,evidence,inputs,validation);verify(root)
save(repo/'research/accel_upper_realization_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['accel_upper_realization_v1','baselines/accel_upper_realization_v1/manifest.json',result['file_count'],result['manifest_sha256'],
    '12cases36continuousRuns576nativeObs16704WelchWindows;fullFloat64Replay',
    'fifth2HighOrderVariancePending;twoDenominators;refilter4thNotGaussian;619C-H67voices',
    'research/素材持续生成与实测V1.md | research/accel_upper_realization_v1_summary.json','baselines/accel_upper_realization_v1/validation.json'])
print(result)
