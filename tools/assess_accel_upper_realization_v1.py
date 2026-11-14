"""Describe all continuous-realization energy/spectral budgets, without turning Monte Carlo into a timbre gate."""
import argparse,os,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','audit','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from research_archive_v1 import load,save,sha
from accel_upper_carrier_v1.spectral import summaries

a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_assessment.py')
run=load(a.input/'report.json');audit=load(a.audit/'report.json');assert audit['result']=='passed'
r=dict(result='all12_continuous_source_realizations_assessed_NOT_voice',input_sha256=sha(a.input/'report.json'),audit_sha256=sha(a.audit/'report.json'),cases=[],figures=[])
M=np.array([[1.,0.,1.,0.],[0.,1.,0.,1.]]);hz=np.arange(6001)*4;selected=(hz>=4000)&(hz<14000)
fig,axes=plt.subplots(2,3,figsize=(14,8),layout='constrained');fig2,ax2=plt.subplots(2,3,figsize=(14,8),layout='constrained')
fig3,ax3=plt.subplots(1,3,figsize=(15,6),layout='constrained');labels=[];errors=[];denominators=[];powers=[]
for row in run['observations']:
    all_values={stage:{key:[] for key in ['theoretical_normalized','measured_normalized','power_mean','pooled_spectrum']} for stage in ['raw','refilter']}
    for record in row['records']:
        path=a.input/record['observation_file'];assert sha(path)==record['observation_sha256']
        with np.load(path) as f:
            for stage,table in all_values.items():
                for key in table:table[key].append(f[stage+'_'+key])
    with np.load(a.input/row['file']) as m:
        expected=m['energy_expected'];target=m['source_target'];arrays=dict(energy_expected=expected,source_target=target);stages={}
        for stage,table in all_values.items():
            values={key:np.stack(value) for key,value in table.items()};primary=values['theoretical_normalized'];finite=values['measured_normalized']
            primary_mean=primary.mean(axis=(0,1));finite_mean=finite.mean(axis=(0,1));run_means=primary.mean(axis=1)
            observed_C=values['pooled_spectrum'].mean(axis=0);expected_C=m['Welch_'+stage+'_expected']
            actual_summary=summaries(observed_C,12000);expected_summary=summaries(expected_C,12000);budgets=[]
            for actual,pred in zip(actual_summary,expected_summary):
                budgets.append(dict(band_hz=actual['band_hz'],stereo_power_db=(10*np.log10(np.array(actual['stereo_power'])/pred['stereo_power'])).tolist(),
                    coordinate_power_db=(10*np.log10(np.array(actual['coordinate_power'])/pred['coordinate_power'])).tolist(),
                    integrated_LR_error=(np.array(actual['integrated_normalized_LR'])-pred['integrated_normalized_LR']).tolist(),
                    pooled_MSC=actual['power_weighted_MSC'],expected_spectrum_MSC=pred['power_weighted_MSC']))
            detailed=[]
            A=np.einsum('ai,fij,bj->fab',M,observed_C,M)[:,[0,1],[0,1]].real;E=np.einsum('ai,fij,bj->fab',M,expected_C,M)[:,[0,1],[0,1]].real
            for ch in range(2):
                assert np.all(E[selected,ch]>0) and np.all(A[selected,ch]>0)
                weight=E[selected,ch];db=abs(10*np.log10(A[selected,ch]/weight));detailed.append(dict(channel=ch,bins=int(selected.sum()),
                    expected_power_weighted_absolute_db=float(np.dot(weight,db)/weight.sum()),maximum_absolute_db=float(db.max())))
            P=m['theoretical_power'] if stage=='raw' else m['filtered_theoretical_power'];power_db=10*np.log10(values['power_mean'].mean(axis=1)/P)
            stages[stage]=dict(spectral_budgets=budgets,detailed_spectral_error=detailed,actual_summary=actual_summary,expected_summary=expected_summary,
                run_power_db=power_db.tolist(),denominator_effect_max=float(abs(finite_mean-primary_mean).max()),
                primary_mean=primary_mean.tolist(),finite_mean=finite_mean.tolist(),run_means=run_means.tolist(),
                pre_refilter_energy_expectation_applies=stage=='raw')
            if stage=='raw':
                stages[stage].update(primary_mean_prediction_max_error=float(abs(primary_mean-expected).max()),
                    primary_mean_prediction_rms_error=float(np.mean((primary_mean-expected)**2)**.5),
                    finite_mean_prediction_max_difference=float(abs(finite_mean-expected).max()),
                    primary_mean_source_cost=float(np.sum((primary_mean-target)**2)/2),finite_mean_source_cost=float(np.sum((finite_mean-target)**2)/2),
                    theory_source_cost=float(np.sum((expected-target)**2)/2),all3_run_prediction_max_errors=abs(run_means-expected).max(axis=(1,2,3)).tolist())
            arrays.update({stage+'_'+key:value for key,value in values.items()});arrays[stage+'_expected_spectrum']=expected_C
        file=a.out/(row['segment']+'_'+row['branch']+'.npz');np.savez_compressed(file,**arrays)
    item=dict(segment=row['segment'],branch=row['branch'],fit_available=row['fit_available'],file=file.name,sha256=sha(file),
        frames_per_run=row['records'][0]['frames'],runs=3,blocks_per_run=8,within_run_blocks_not_independent=True,stages=stages)
    r['cases'].append(item);labels.append(row['segment'].replace('F3_','')+' / '+row['branch'].replace('phase_','P'))
    errors.append(stages['raw']['primary_mean_prediction_max_error']);denominators.append(stages['raw']['denominator_effect_max']);powers.append(np.mean(stages['raw']['run_power_db'],axis=0))
    if row['branch']!='original':continue
    col=['F3_fifth1','F3_fifth2','F3_sixth'].index(row['segment']);raw=stages['raw'];mean=np.array(raw['primary_mean']);finite=np.array(raw['finite_mean']);run_mean=np.array(raw['run_means'])
    for rr,(i,j,label) in enumerate([(0,2,'L cross-band'),(1,3,'R cross-band')]):
        ax=axes[rr,col];lag=np.arange(-5,6)*10;ax.plot(lag,target[:,i,j],'o-',color='#247f73',label='Source',ms=3)
        ax.plot(lag,expected[:,i,j],color='#596168',label='Model expectation');ax.fill_between(lag,run_mean[:,:,i,j].min(axis=0),run_mean[:,:,i,j].max(axis=0),color='#365eaa',alpha=.15,label='Range of 3 run means')
        ax.plot(lag,mean[:,i,j],'o-',color='#365eaa',label='Generated, model-power denominator',ms=3);ax.plot(lag,finite[:,i,j],'--',color='#b28650',label='Generated, finite-power denominator')
        ax.set(title=row['segment']+' | '+label,xlabel='Signed within-tile lag (ms)',ylabel='Normalized energy covariance');ax.axhline(0,color='#a2aaae',lw=.6);ax.grid(alpha=.15)
        if rr==col==0:ax.legend(fontsize=6.7)
    x=np.arange(4);raw_db=np.array([stages['raw']['spectral_budgets'][b]['stereo_power_db'] for b in [1,2]]).ravel();filtered_db=np.array([stages['refilter']['spectral_budgets'][b]['stereo_power_db'] for b in [1,2]]).ravel()
    ax=ax2[0,col];ax.bar(x-.17,raw_db,width=.32,color='#365eaa',label='Before refilter');ax.bar(x+.17,filtered_db,width=.32,color='#b28650',label='After refilter')
    ax.set_xticks(x,['4-8 L','4-8 R','8-14 L','8-14 R'],rotation=25);ax.set(title=row['segment'],ylabel='Generated vs own expected band power (dB)');ax.axhline(0,color='#a2aaae',lw=.6);ax.grid(axis='y',alpha=.15)
    if col==0:ax.legend(fontsize=7)
    ax=ax2[1,col]
    for stage,colour in [('raw','#365eaa'),('refilter','#b28650')]:
        b=stages[stage]['spectral_budgets'];ax.plot([0,1],[b[k]['pooled_MSC'] for k in [1,2]],'o-',color=colour,label=stage+' pooled actual')
        ax.plot([0,1],[b[k]['expected_spectrum_MSC'] for k in [1,2]],'s--',color=colour,label=stage+' expected spectrum')
    ax.set_xticks([0,1],['4-8 kHz','8-14 kHz']);ax.set_ylabel('Power-weighted MSC of pooled spectrum');ax.grid(alpha=.15)
    if col==0:ax.legend(fontsize=7)
x=np.arange(12);ax3[0].bar(x,errors,color='#365eaa');ax3[1].bar(x,denominators,color='#b28650')
for ax in ax3[:2]:ax.set_xticks(x,labels,rotation=70,ha='right',fontsize=7);ax.grid(axis='y',alpha=.15)
ax3[0].set(title='All12: finite realization vs expectation',ylabel='Max absolute energy covariance error');ax3[1].set(title='All12: denominator effect',ylabel='Max |finite-power mean - model-power mean|')
im=ax3[2].imshow(powers,aspect='auto',cmap='coolwarm');ax3[2].set_yticks(range(12),labels,fontsize=7);ax3[2].set_xticks(range(4),['4-8 L','4-8 R','8-14 L','8-14 R'],rotation=30);ax3[2].set_title('Mean of 3 run power changes (dB)');fig3.colorbar(im,ax=ax3[2],shrink=.7)
fig.suptitle('Continuous source-carrier x joint-gain generation | 3 runs x 8 original-length blocks\nRange is descriptive, not a confidence band; original source residual remains',fontsize=12)
fig2.suptitle('Actual generated spectra vs each stage\'s exact expected spectrum\nMSC of the pooled matrix is not the expected finite-estimator MSC',fontsize=12)
fig3.suptitle('Every frozen terminal retained, including unavailable controls as diagnostics\nNo per-run power correction, seed selection or fit change',fontsize=12)
for name,figure in [('energy.png',fig),('spectral_budgets.png',fig2),('all_cases.png',fig3)]:
    path=a.out/name;figure.savefig(path,dpi=150);plt.close(figure);r['figures'].append(dict(file=name,sha256=sha(path)))
r.update(new_listening_audio=False,new_runtime_profile=False,only3independent_runs=True,no_statistical_acceptance_gate=True,
    post_refilter_fourth_moment_still_not_qualified=True,
    next='Use actual generation/observation residuals to decide a controllable low-latency carrier representation and the remaining nonstationary slow-colour/state model. Do not promote a stationary Gaussian carrier as mechanical timbre or use pre-refilter fourth moments after refilter. Keep pending idle candidate hearing before its C port.')
save(a.out/'report.json',r)
for item in r['cases']:
    if item['branch']=='original':print(dict(segment=item['segment'],primary_error=item['stages']['raw']['primary_mean_prediction_max_error'],denominator=item['stages']['raw']['denominator_effect_max'],
        theory_source_cost=item['stages']['raw']['theory_source_cost'],actual_source_cost=item['stages']['raw']['primary_mean_source_cost'],budgets=item['stages']['raw']['spectral_budgets'][1:3]),flush=True)
