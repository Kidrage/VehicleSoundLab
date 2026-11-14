"""Summarize finite source transfer; descriptor distances are not hearing scores."""
import argparse,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','audit','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from research_archive_v1 import load,save,sha

a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_assessment.py')
audit=load(a.audit/'report.json');assert audit['result']=='passed'
render=load(a.input/'report.json');model=load(a.input/'model.json')
source=audit['source_curves'];TRAIN=source['source_train'];CHECK=source['source_check']
curves=np.array(model['predicted_node_covariance_lags']);lags=np.arange(51)*.02
r=dict(result='all_declared_idle_amplitude_contrasts_observed',input_sha256=sha(a.input/'report.json'),
       audit_sha256=sha(a.audit/'report.json'),contrasts=render['renders'],
       predicted_node_trace_rho200ms=audit['predicted_trace_200ms_correlation'],
       source_train_trace_rho200ms=TRAIN['trace_200ms_correlation'],source_check_trace_rho200ms=CHECK['trace_200ms_correlation'],
       same_observer_generated_comparisons=audit['same_observer_generated_comparisons'],
       source_CHECK_not_used_for_fit=True,source_CHECK_already_inspected=True,
       covariance_match_is_at_latent_nodes_not_full_recording=True,
       observed_main_75Hz_motion_increases_but_other_two_bands_remain_excessive=True,
       phase_and_amplitude_independence_incomplete=True,source_timbre_match_claim=False,
       listening_accepted=False,runtime_changed=False)
fig,axes=plt.subplots(2,2,figsize=(12,8),layout='constrained')
for name,color in [('source_train','#243d5a'),('source_check','#697c86')]:
    y=source[name];axes[0,0].plot(lags,np.trace(np.array(y['covariance_lags']),axis1=1,axis2=2)/np.trace(y['covariance']),color=color,label=name)
axes[0,0].plot(lags,np.trace(curves,axis1=1,axis2=2)/np.trace(curves[0]),color='#b75929',label='FIR expected nodes')
axes[0,0].set(title='All signed trace covariance lags',xlabel='lag (s)',ylabel='trace(C[k])/trace(C[0])');axes[0,0].legend()
for s,color in [('0.0','#8798a4'),('0.5','#d9a449'),('1.0','#28776c')]:
    rows=[x for x in audit['same_observer_generated_comparisons'] if x['amount']==s]
    values=np.array([x['median_observed_std'] for x in rows])
    axes[0,1].plot([75,112,187],np.median(values,axis=0),'o-',color=color,label='amount '+s)
    axes[0,1].fill_between([75,112,187],values.min(axis=0),values.max(axis=0),color=color,alpha=.12)
axes[0,1].plot([75,112,187],TRAIN['raw_log_std'],'s--',color='#243d5a',label='source TRAIN')
axes[0,1].plot([75,112,187],CHECK['raw_log_std'],'s:',color='#697c86',label='source CHECK')
axes[0,1].set(title='Same observer on actual MIX; range of 3 seeds',xlabel='acoustic line (Hz)',ylabel='log amplitude std');axes[0,1].legend(fontsize=8)
for row in render['renders']:
    with np.load(a.input/row['trace']) as f:x=f['native_log']
    if row['seed']==149921:
        g=np.exp(x-np.diag(model['training_covariance']))
        for j,hz in enumerate([75,112,187]):axes[1,0].plot(np.arange(0,len(x),48)/48000,g[::48,j],label=str(hz)+' Hz',lw=.7)
        break
axes[1,0].set(title='Fresh generated gains, strength 100%, seed149921',xlabel='time (s)',ylabel='linear gain');axes[1,0].legend()
for row in render['renders']:
    c=np.array(row['empirical_20msmean_covariance_lags'])
    axes[1,1].plot(lags,np.trace(c,axis1=1,axis2=2)/np.trace(c[0]),label=str(row['seed']))
axes[1,1].set(title='Finite latent generation: all lags, 3 seeds',xlabel='lag (s)',ylabel='normalized covariance');axes[1,1].legend()
for ax in axes.flat:ax.grid(alpha=.2);ax.axhline(0,color='#999',lw=.5)
fig.suptitle('Idle amplitude V1: latent covariance retained; full mixed-recording gap remains',fontsize=13)
figure=a.out/'assessment.png';fig.savefig(figure,dpi=150);plt.close(fig)
r['figure']=dict(file=figure.name,sha256=sha(figure));save(a.out/'report.json',r)
print(dict(result=r['result'],predicted_rho=r['predicted_node_trace_rho200ms'],
           source_train_rho=r['source_train_trace_rho200ms'],source_check_rho=r['source_check_trace_rho200ms']),flush=True)
