"""Freeze source-shaped native joint-gain inverse and all independent numerical evidence."""
import argparse,csv,os,shutil,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--stage',choices=['freeze','verify'],required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
from research_archive_v1 import load,save,sha,freeze,verify,append_index

root=a.workspace/'baselines/accel_upper_coloured_v1'
if a.stage=='verify':print(verify(root)['file_count']);raise SystemExit
evidence=a.workspace/'references/analysis/accel_upper_coloured_v1';run=load(evidence/'fit1/report.json');audit=load(evidence/'audit1/report.json')
before=load(evidence/'assessment1/report.json');assessment=load(evidence/'assessment2/report.json')
assert run['result']=='all12_source_carrier_joint_gain_fits_terminal' and len(run['observations'])==12
assert audit['result']=='passed' and audit['cases']==12 and audit['trace_evaluations']==600 and audit['band_summaries']==96
assert audit['source_available']==3 and audit['control_available']==0 and audit['all_known_native_waveform'] and audit['all_trace_costs'] and audit['all176x11_Jacobians']
assert assessment['result']=='all12_source_shaped_carrier_fits_assessed_NOT_voice' and len(assessment['cases'])==12
assert assessment['cases']==before['cases'] and assessment['source_available']==3 and assessment['control_available']==0
assert before['input_sha256']==assessment['input_sha256']==audit['input_sha256']==sha(evidence/'fit1/report.json')
assert before['audit_sha256']==assessment['audit_sha256']==sha(evidence/'audit1/report.json')
old_source=(evidence/'assessment1/executed_assessment.py').read_text(encoding='utf-8')
assert old_source.replace('All 176 residuals: cost / 2','Half sum of 176 squared residuals')==(repo/'tools/assess_accel_upper_coloured_v1.py').read_text(encoding='utf-8')
for name in ['energy_fit.png','stereo_budget.png']:assert sha(evidence/'assessment1'/name)==sha(evidence/'assessment2'/name)
assert run['known']['known_recovery_error']<1e-6 and run['known']['known_fit']['available'] and sha(evidence/'fit1/known.npz')==run['known_sha256']
sources=set(run['sources'])
for name,digest in run['sources'].items():assert sha(repo/name)==digest==sha(evidence/'fit1/exact_sources'/name)
parent=a.workspace/'baselines/accel_upper_carrier_v1';assert sha(parent/'manifest.json')==run['parent_manifest_sha256']
inputs={'parent_manifest':parent/'manifest.json'};table={v['path']:v['sha256'] for v in load(parent/'manifest.json')['files']}
for name,digest in run['parent_files'].items():
    assert sha(parent/name)==digest==table[name];inputs['parent/'+name]=parent/name
parent_summary=load(parent/'evidence/summary2/report.json');inputs['parent/evidence/summary2/report.json']=parent/'evidence/summary2/report.json'
trace=len(run['known']['known_fit']['trace']);count=0;M=np.array([[1.,0.,1.,0.],[0.,1.,0.,1.]])
mask=(np.arange(6001)*4>=4000)&(np.arange(6001)*4<14000)
def check(x,y):np.testing.assert_allclose(x,y,rtol=1e-12,atol=1e-14)
for row,item,sr in zip(run['observations'],assessment['cases'],parent_summary['observations']):
    assert row['segment']==item['segment']==sr['segment'] and row['branch']==item['branch']==sr['branch']
    assert sha(evidence/'fit1'/row['file'])==row['sha256'];fit=row['fit'];trace+=len(fit['trace'])
    for key in ['available','success','nfev','bound_mask']:assert item[key]==fit[key]
    for key in ['old_white_cost','fixed_coloured_cost','maximum_error','Gamma']:assert item[key]==row[key]
    check(item['tau_ms'],row['tau_seconds']*1000);check(item['fitted_coloured_cost'],fit['cost'])
    check(item['improvement_from_fixed'],1-fit['cost']/row['fixed_coloured_cost']);check(item['improvement_from_white'],1-fit['cost']/row['old_white_cost'])
    with np.load(evidence/'fit1'/row['file']) as f,np.load(parent/row['carrier_parent_file']) as carrier:
        target=np.einsum('ai,fij,bj->fab',M,carrier['target'],M)[:,[0,1],[0,1]].real
        for d in item['detailed_spectral_error']:
            P=np.einsum('ai,fij,bj->fab',M,f[d['configuration']],M)[:,[0,1],[0,1]].real;ch=d['channel'];weight=target[mask,ch]
            error=abs(10*np.log10(P[mask,ch]/weight));assert d['bins']==2500
            check(d['weighted_absolute_db'],np.dot(weight,error)/weight.sum());check(d['maximum_absolute_db'],error.max())
    for b,budget in enumerate(item['budgets']):
        c=sr['summaries']['Welch_carrier'][b];fc=sr['summaries']['Welch_refilter_carrier'][b]
        g=row['summaries']['Welch_gain'][b];fg=row['summaries']['Welch_refilter_gain'][b]
        assert budget['band_hz']==g['band_hz']
        check(budget['gain_only_power_db'],10*np.log10(np.array(g['stereo_power'])/c['stereo_power']))
        check(budget['refilter_gain_only_power_db'],10*np.log10(np.array(fg['stereo_power'])/fc['stereo_power']))
        for key,entry in [('carrier',c),('gain',g),('refilter_carrier',fc),('refilter_gain',fg)]:check(budget[key+'_MSC'],entry['power_weighted_MSC'])
        count+=2
assert trace==600 and count==96
assert sum(x['fit']['available'] for x in run['observations'] if x['branch']=='original')==3
controls=[x['fit'] for x in run['observations'] if x['branch']!='original'];assert len(controls)==9 and not any(x['available'] for x in controls)
assert sum(x['nfev']==60 for x in controls)==8
for name,folder,executed in [('tools/audit_accel_upper_coloured_v1.py','audit1','executed_auditor.py'),('tools/assess_accel_upper_coloured_v1.py','assessment2','executed_assessment.py')]:
    assert sha(repo/name)==sha(evidence/folder/executed);sources.add(name)
for fig in assessment['figures']:
    path=evidence/'assessment2'/fig['file'];assert sha(path)==fig['sha256'];name='research/accel_upper_coloured_v1_'+fig['file'];shutil.copy2(path,repo/name);sources.add(name)
ch=list(csv.reader((repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig')));assert len(ch)==620 and all(sha(repo/row[0])==row[4] for row in ch[1:])
voice_path=a.workspace/'baselines/idle_microtexture_c_v1/inputs/voice_files_sha256.json';voices=load(voice_path)
assert len(voices)==67 and all(sha(repo/name)==digest for name,digest in voices.items())
sources.update(['tools/package_accel_upper_coloured_v1.py','research/素材载体联合起伏V1.md','AGENTS.md','handoff/研究续接.md','handoff/开发留痕.md'])
inputs.update(C_H_index=repo/'handoff/C文件索引.csv',voice_hashes=voice_path,idle_pending_manifest=a.workspace/'baselines/idle_complex75_v1/manifest.json')
shutil.copy2(repo/'AGENTS.md',a.workspace/'AGENTS.md')
validation=dict(schema='vsl.accel-upper-coloured-freeze/1',result='source_shaped_carrier_inside_native_joint_gain_fit_verified_NOT_voice',
    parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    previous_goal_turn_progress='15de952 source matrix FIR compilation/all budgets/compatibility audits and archive; actual progress, not wait-only',
    independent_audit=audit,known_full11inverse_before_source=True,all12fits600trace96summaries=True,all_assessment_metrics_verified=True,
    assessment1_preserved_assessment2_caption_only=True,figures_viewed=True,old_initial_bounds_budget_and_availability_unchanged=True,
    three_real_numeric_available=True,nine_controls_unavailable_eight_max60=True,carrier_PSD_frozen_not_refitted=True,
    actual_source_synthesis_or_finite_realization_not_yet_qualified=True,post_gain_before_refilter_observer=True,
    native_three_second_known_generation_verified=True,not_realtime_or_physical_state_evidence=True,
    no_independent_holdout=True,numeric_fit_not_timbre_acceptance=True,new_listening_audio=False,new_runtime_profile=False,new_C=False,
    new_download=False,old_CTests_repeated=False,old619C_H_and67voices_exact=True,moving35_changed=False,runtime_changed=False,pending_idle_listening_unchanged=True,
    full_MSC_original_gate_still_unpassed=True,original_common_phase_qualification_unwaived=True,next=assessment['next'],full_goal_complete=False)
result=freeze(root,repo,sources,evidence,inputs,validation);verify(root)
save(repo/'research/accel_upper_coloured_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['accel_upper_coloured_v1','baselines/accel_upper_coloured_v1/manifest.json',result['file_count'],result['manifest_sha256'],
    'matrixCarrierInsideNativeOU;known11inverse;12fits600traceAllJ;96bands',
    '3realNumeric9controlsUnavailable;slowColour/actualSourceGenPending;619C-H67voices',
    'research/素材载体联合起伏V1.md | research/accel_upper_coloured_v1_summary.json','baselines/accel_upper_coloured_v1/validation.json'])
print(result)
