"""All source-shaped carrier fits, unrepaired controls and separate stereo budgets."""
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

a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_assessment.py')
run=load(a.input/'report.json');audit=load(a.audit/'report.json');assert audit['result']=='passed'
parent=a.workspace/'baselines/accel_upper_carrier_v1';assert sha(parent/'manifest.json')==run['parent_manifest_sha256']
summary=load(parent/'evidence/summary2/report.json')
r=dict(result='all12_source_shaped_carrier_fits_assessed_NOT_voice',input_sha256=sha(a.input/'report.json'),audit_sha256=sha(a.audit/'report.json'),
    cases=[],figures=[],source_available=0,control_available=0)
M=np.array([[1.,0.,1.,0.],[0.,1.,0.,1.]]);hz=np.arange(6001)*4;mask=(hz>=4000)&(hz<14000)
fig,axes=plt.subplots(3,3,figsize=(14,11),layout='constrained');fig2,ax2=plt.subplots(1,2,figsize=(14,6),layout='constrained')
fig3,ax3=plt.subplots(2,3,figsize=(14,8),layout='constrained');costs=[];taus=[];available=[];labels=[]
for row,old_summary in zip(run['observations'],summary['observations']):
    assert row['segment']==old_summary['segment'] and row['branch']==old_summary['branch']
    fit=row['fit'];budgets=[]
    for b in range(4):
        old=old_summary['summaries'];carrier=old['Welch_carrier'][b];filtered=old['Welch_refilter_carrier'][b]
        gain=row['summaries']['Welch_gain'][b];fgain=row['summaries']['Welch_refilter_gain'][b]
        budgets.append(dict(band_hz=gain['band_hz'],gain_only_power_db=(10*np.log10(np.array(gain['stereo_power'])/carrier['stereo_power'])).tolist(),
            refilter_gain_only_power_db=(10*np.log10(np.array(fgain['stereo_power'])/filtered['stereo_power'])).tolist(),
            carrier_MSC=carrier['power_weighted_MSC'],gain_MSC=gain['power_weighted_MSC'],refilter_carrier_MSC=filtered['power_weighted_MSC'],refilter_gain_MSC=fgain['power_weighted_MSC']))
    with np.load(a.input/row['file']) as f,np.load(parent/row['carrier_parent_file']) as c:
        target=np.einsum('ai,fij,bj->fab',M,c['target'],M)[:,[0,1],[0,1]].real
        detail=[]
        for key in ['Welch_gain','Welch_refilter_gain']:
            P=np.einsum('ai,fij,bj->fab',M,f[key],M)[:,[0,1],[0,1]].real
            for ch in range(2):
                assert np.all(P[mask,ch]>0) and np.all(target[mask,ch]>0)
                error=abs(10*np.log10(P[mask,ch]/target[mask,ch]));weight=target[mask,ch]
                detail.append(dict(configuration=key,channel=ch,bins=int(mask.sum()),weighted_absolute_db=float(np.dot(weight,error)/weight.sum()),maximum_absolute_db=float(error.max())))
        item=dict(segment=row['segment'],branch=row['branch'],available=fit['available'],success=fit['success'],nfev=fit['nfev'],
            bound_mask=fit['bound_mask'],tau_ms=1000*row['tau_seconds'],old_white_cost=row['old_white_cost'],fixed_coloured_cost=row['fixed_coloured_cost'],
            fitted_coloured_cost=fit['cost'],improvement_from_fixed=1-fit['cost']/row['fixed_coloured_cost'],improvement_from_white=1-fit['cost']/row['old_white_cost'],
            maximum_error=row['maximum_error'],Gamma=row['Gamma'],budgets=budgets,detailed_spectral_error=detail)
        r['cases'].append(item);r['source_available']+=int(row['branch']=='original' and fit['available']);r['control_available']+=int(row['branch']!='original' and fit['available'])
        costs.append([row['old_white_cost'],row['fixed_coloured_cost'],fit['cost']]);taus.append(item['tau_ms']);available.append(fit['available'])
        labels.append(row['segment'].replace('F3_','')+' / '+row['branch'].replace('phase_','P'))
        if row['branch']!='original':continue
        col=['F3_fifth1','F3_fifth2','F3_sixth'].index(row['segment'])
        for rr,(i,j,name) in enumerate([(0,2,'L cross-band'),(1,3,'R cross-band')]):
            ax=axes[rr,col]
            for key,label,colour in [('target','Source','#247f73'),('white_prediction','Old white fit','#879199'),('fixed_prediction','Source carrier, old gains','#b28650'),('prediction','Source carrier, joint fit','#365eaa')]:
                ax.plot(np.arange(-5,6)*10,f[key][:,i,j],'o-',color=colour,label=label,ms=3)
            ax.set(title=row['segment']+' | '+name,xlabel='Signed within-tile lag (ms)',ylabel='Normalized energy covariance');ax.axhline(0,color='#a0a8ac',lw=.6);ax.grid(alpha=.15)
            if rr==col==0:ax.legend(fontsize=7)
        error=abs(f['prediction']-f['target']).max(axis=0);ax=axes[2,col];im=ax.imshow(error,vmin=0,vmax=.06,cmap='magma')
        ax.set_xticks(range(4),['4-8 L','4-8 R','8-14 L','8-14 R'],rotation=25);ax.set_yticks(range(4),['4-8 L','4-8 R','8-14 L','8-14 R']);ax.set_title('Max absolute error over all 11 lags')
        for i in range(4):
            for j in range(4):ax.text(j,i,f'{error[i,j]:.3f}',ha='center',va='center',fontsize=8,color='white' if error[i,j]<.03 else 'black')
        fig.colorbar(im,ax=ax,shrink=.8)
        x=np.arange(4);gain=np.array([budgets[b]['gain_only_power_db'] for b in [1,2]]).ravel();ref=np.array([budgets[b]['refilter_gain_only_power_db'] for b in [1,2]]).ravel()
        ax=ax3[0,col];ax.bar(x-.17,gain,width=.32,color='#365eaa',label='Gain vs carrier');ax.bar(x+.17,ref,width=.32,color='#b28650',label='Refilter gain vs refilter carrier')
        ax.set_xticks(x,['4-8 L','4-8 R','8-14 L','8-14 R'],rotation=25);ax.set(title=row['segment'],ylabel='Band power change (dB)');ax.axhline(0,color='#a0a8ac',lw=.6);ax.grid(axis='y',alpha=.15)
        if col==0:ax.legend(fontsize=7)
        ax=ax3[1,col]
        for field,label,colour,style in [('carrier_MSC','Carrier','#247f73','o-'),('gain_MSC','Joint fit','#365eaa','o-'),('refilter_carrier_MSC','Refilter carrier','#b28650','s--'),('refilter_gain_MSC','Refilter joint fit','#7b596c','s--')]:
            ax.plot([0,1],[budgets[b][field] for b in [1,2]],style,color=colour,label=label,ms=4)
        ax.set_xticks([0,1],['4-8 kHz','8-14 kHz']);ax.set_ylabel('Power-weighted stereo MSC');ax.grid(alpha=.15)
        if col==0:ax.legend(fontsize=7)
x=np.arange(12);costs=np.array(costs)
for col,(label,colour) in enumerate([('Old white fit','#879199'),('Source carrier, old gains','#b28650'),('Source carrier, joint fit','#365eaa')]):ax2[0].bar(x+(col-1)*.24,costs[:,col],width=.22,color=colour,label=label)
ax2[0].set_xticks(x,labels,rotation=70,ha='right',fontsize=7);ax2[0].set(yscale='log',ylabel='Half sum of 176 squared residuals',title='All12 cases, same fit rules');ax2[0].legend(fontsize=7)
for k,(tau,ok) in enumerate(zip(taus,available)):ax2[1].plot(k,tau,'o' if ok else 'x',color='#247f73' if ok else '#9a6673',ms=7)
ax2[1].set_xticks(x,labels,rotation=70,ha='right',fontsize=7);ax2[1].set(ylabel='Fitted time constant (ms)',title='O = available; X = unavailable, no rescue');ax2[1].axhline(3,color='#b28650',ls='--',lw=.8,label='Unchanged 3ms bound');ax2[1].legend(fontsize=7)
fig.suptitle('Frozen source carrier inside the native joint-gain fit | all original passages\nStationary moment agreement is not mechanical timbre acceptance',fontsize=12)
fig2.suptitle('All original and phase-control terminal results | one fixed initial / bounds / max60',fontsize=12)
fig3.suptitle('Refitted gains: separate post-gain / refilter / stereo budgets\nNo new voice, source trajectory loop, room model or C integration',fontsize=12)
for name,figure in [('energy_fit.png',fig),('all_cases.png',fig2),('stereo_budget.png',fig3)]:
    path=a.out/name;figure.savefig(path,dpi=150);plt.close(figure);r['figures'].append(dict(file=name,sha256=sha(path)))
r.update(new_listening_audio=False,numerical_available_not_voice=True,carrier_not_refitted=True,old_rule_not_relaxed=True,
    next='Qualify actual stationary carrier-times-gain synthesis and finite-realization observation, then a controllable low-latency carrier representation. Remaining nonstationary slow colour/state and source firing identity are unsolved. No immediate audio/C promotion; pending idle_complex75 hearing comes before its own C port.')
save(a.out/'report.json',r)
for item in r['cases']:
    if item['branch']=='original':print(item,flush=True)
