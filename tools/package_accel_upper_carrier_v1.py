"""Freeze source-shaped carrier budgets, all attempts and independent compatibility verification."""
import argparse,csv,os,shutil,subprocess,sys
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--stage',choices=['freeze','verify'],required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
from research_archive_v1 import load,save,sha,freeze,verify,append_index

root=a.workspace/'baselines/accel_upper_carrier_v1'
if a.stage=='verify':print(verify(root)['file_count']);raise SystemExit
evidence=a.workspace/'references/analysis/accel_upper_carrier_v1'
run=load(evidence/'observe1/report.json');energy=load(evidence/'energy1/report.json');summary=load(evidence/'summary2/report.json')
failed=load(evidence/'audit1/report.json');audit=load(evidence/'audit2/report.json');assessment=load(evidence/'assessment1/report.json')
assert run['result']=='all12_source_carriers_and_gain_budgets_complete' and run['native_windows']==348 and len(run['observations'])==12
assert energy['result']=='all12_fixed_gain_carrier_compatibility_diagnosed' and len(energy['cases'])==12
assert summary['result']=='all12_coherence_summaries_corrected_spectra_unchanged' and len(summary['observations'])==12
assert failed['result']=='failed' and failed['cases']==0 and 'scalar_native_covariance_lags' in failed['error']
assert audit['result']=='passed' and audit['cases']==12 and audit['native_windows']==348 and audit['band_summaries']==288
assert audit['all6001bins_all16complex_entries'] and audit['all12_fixed_gain_energy_compatibility'] and not audit['near_null_all_bin_coherence_qualified']
assert assessment['result']=='all12_source_carrier_budgets_assessed_not_voice' and len(assessment['cases'])==12
for report in [energy,summary,failed,audit,assessment]:assert report['input_sha256']==sha(evidence/'observe1/report.json')
for report in [failed,audit,assessment]:
    assert report['energy_sha256']==sha(evidence/'energy1/report.json') and report['summary_sha256']==sha(evidence/'summary2/report.json')
assert assessment['audit_sha256']==sha(evidence/'audit2/report.json') and sha(evidence/'observe1/known.npz')==run['known_sha256']
sources=set()
for folder,report in [('observe1',run),('energy1',energy),('summary2',summary)]:
    for name,digest in report['sources'].items():
        assert sha(evidence/folder/'exact_sources'/name)==digest;sources.add(name)
        if folder!='observe1' or name!='tools/accel_upper_carrier_v1/spectral.py':assert sha(repo/name)==digest
old=(evidence/'observe1/exact_sources/tools/accel_upper_carrier_v1/spectral.py').read_text(encoding='utf-8')
fixed=old.replace('valid=den>0;','valid=(P[:,0]>0)&(P[:,1]>0);').replace('weight=P.sum(axis=1);','weight=np.where(valid,P.sum(axis=1),0.);')
assert old!=fixed==(repo/'tools/accel_upper_carrier_v1/spectral.py').read_text(encoding='utf-8')
inputs={}
for key,item in run['parents'].items():
    parent=a.workspace/'baselines'/item['stage'];assert sha(parent/'manifest.json')==item['manifest_sha256']
    inputs['parents/'+key+'/manifest.json']=parent/'manifest.json'
    table={v['path']:v['sha256'] for v in load(parent/'manifest.json')['files']}
    for name,digest in item['files'].items():
        assert sha(parent/name)==digest==table[name];inputs['parents/'+key+'/'+name]=parent/name

def check(x,y):np.testing.assert_allclose(x,y,rtol=1e-12,atol=1e-14)
M=np.array([[1.,0.,1.,0.],[0.,1.,0.,1.]]);selected=(np.arange(6001)*4>=4000)&(np.arange(6001)*4<14000)
count=0
for row,sr,er,item in zip(run['observations'],summary['observations'],energy['cases'],assessment['cases']):
    assert row['segment']==sr['segment']==er['segment']==item['segment'] and row['branch']==sr['branch']==er['branch']==item['branch']
    assert sha(evidence/'observe1'/row['file'])==row['sha256'] and sha(evidence/'energy1'/er['file'])==er['sha256']
    assert item['gain_fit_available']==row['gain_fit_available'] and item['energy_compatibility']==er and item['corrected_summaries']==sr['summaries']
    assert er['model_parameters_changed'] is False
    with np.load(evidence/'observe1'/row['file']) as f:
        P={k:np.einsum('ai,fij,bj->fab',M,f[k],M)[:,[0,1],[0,1]].real for k in ['target','Welch_carrier','Welch_gain']}
        for detail in item['detailed_spectral_error']:
            ch=detail['channel'];target=P['target'][selected,ch];error=abs(10*np.log10(P[detail['configuration']][selected,ch]/target))
            assert detail['all4to14k_bins']==2500
            check(detail['target_power_weighted_absolute_db'],np.dot(target,error)/target.sum());check(detail['maximum_absolute_db'],error.max())
    for b,budget in enumerate(item['budgets']):
        table=sr['summaries'];t=table['target'][b];c=table['Welch_carrier'][b];g=table['Welch_gain'][b]
        fc=table['Welch_refilter_carrier'][b];fg=table['Welch_refilter_gain'][b]
        assert budget['band_hz']==t['band_hz']
        check(budget['repeated_Welch_power_db'],10*np.log10(np.array(c['stereo_power'])/t['stereo_power']))
        check(budget['gain_only_power_db'],10*np.log10(np.array(g['stereo_power'])/c['stereo_power']))
        check(budget['refilter_gain_only_power_db'],10*np.log10(np.array(fg['stereo_power'])/fc['stereo_power']))
        for name,entry in [('carrier',c),('gain',g),('refilter_carrier',fc),('refilter_gain',fg)]:check(budget[name+'_MSC'],entry['power_weighted_MSC'])
        count+=len(table)
    with np.load(evidence/'energy1'/er['file']) as f:
        check(er['previous_cost'],np.sum((f['previous']-f['target'])**2)/2);check(er['new_cost'],np.sum((f['prediction']-f['target'])**2)/2)
        check(er['previous_max_error'],abs(f['previous']-f['target']).max());check(er['new_max_error'],abs(f['prediction']-f['target']).max())
assert count==288
for name,folder,executed in [('tools/audit_accel_upper_carrier_v1.py','audit2','executed_auditor.py'),('tools/assess_accel_upper_carrier_v1.py','assessment1','executed_assessment.py')]:
    assert sha(repo/name)==sha(evidence/folder/executed);sources.add(name)
for fig in assessment['figures']:
    path=evidence/'assessment1'/fig['file'];assert sha(path)==fig['sha256']
    name='research/accel_upper_carrier_v1_'+fig['file'];shutil.copy2(path,repo/name);sources.add(name)
ch=list(csv.reader((repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig')))
assert len(ch)==620 and all(sha(repo/row[0])==row[4] for row in ch[1:])
voice_path=a.workspace/'baselines/idle_microtexture_c_v1/inputs/voice_files_sha256.json';voices=load(voice_path)
assert len(voices)==67 and all(sha(repo/path)==digest for path,digest in voices.items())
sources.update(['tools/package_accel_upper_carrier_v1.py','research/高频载体与立体声预算V1.md','AGENTS.md','handoff/研究续接.md','handoff/开发留痕.md'])
shutil.copy2(repo/'AGENTS.md',a.workspace/'AGENTS.md')
inputs.update(C_H_index=repo/'handoff/C文件索引.csv',voice_hashes=voice_path,idle_pending_manifest=a.workspace/'baselines/idle_complex75_v1/manifest.json')
validation=dict(schema='vsl.accel-upper-carrier-freeze/1',result='all12_source_matrix_carriers_and_gain_refilter_stereo_budgets_verified_NOT_voice',
    parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    previous_goal_turn_progress='617216b actual qualified joint persistent-gain model, native inverse/source fits and all independent audits/archive; not a wait-only turn',
    independent_audit=audit,all12cases348windows288summaries=True,all_assessment_metrics_verified=True,figures_viewed=True,
    full12000tap_four_by_four_carrier=True,common_shift_samples=6000,offline_representation_not_realtime_C=True,
    original_summary_and_sources_preserved=True,two_line_positive_power_mask_only=True,failed_known_auditor_attempt_preserved=True,
    subsequent_energy_diagnostic_declared_after_observation=True,unchanged_Gamma_tau=True,source_carrier_joint_refit_pending=True,
    no_PCM_or_source_trajectory_loop=True,no_independent_holdout=True,numeric_fit_not_timbre_acceptance=True,
    new_listening_audio=False,new_runtime_profile=False,new_C=False,new_download=False,old_CTests_repeated=False,
    old619C_H_and67voices_exact=True,moving35_changed=False,runtime_changed=False,pending_idle_listening_unchanged=True,
    full_MSC_original_gate_still_unpassed=True,original_common_phase_qualification_unwaived=True,
    next=assessment['next'],full_goal_complete=False)
result=freeze(root,repo,sources,evidence,inputs,validation);verify(root)
save(repo/'research/accel_upper_carrier_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['accel_upper_carrier_v1','baselines/accel_upper_carrier_v1/manifest.json',result['file_count'],result['manifest_sha256'],
    '12nativeMatrixFIR;6001bins16entries;gain-refilter-Welch-stereo;348windows288bands',
    'noVoice;fixedGainEnergyChanged;summaryMaskOnly;failedAuditorKept;619C-H67voices',
    'research/高频载体与立体声预算V1.md | research/accel_upper_carrier_v1_summary.json','baselines/accel_upper_carrier_v1/validation.json'])
print(result)
