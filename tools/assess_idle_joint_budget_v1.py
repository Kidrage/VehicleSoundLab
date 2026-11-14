"""Finite audio assessment, source transfer limits and one figure; no listening claims."""
import argparse,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','audit','model','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from research_archive_v1 import load,save,sha

a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_assessment.py')
r=dict(result='running',input_sha256=sha(a.input/'report.json'),audit_sha256=sha(a.audit/'report.json'),conditions=[])
try:
    audit=load(a.audit/'report.json');assert audit['result']=='passed'
    render=load(a.input/'report.json');compilation=load(a.model/'report.json');model=load(a.model/'model.json')
    source=load(a.workspace/'baselines/idle_phase_amplitude_v1/evidence/observe1/report.json')
    source={row['part']:row['aware'] for row in source['observations'] if row['seed'] is None}
    labels={'0.0':'Previous separated residual','0.5':'Joint power allocation','1.0':'Joint allocation + full AM'}
    for key,label in labels.items():
        selected=[x for x in audit['observations'] if x['condition']==key]
        values=np.array([x['median_observed_std'] for x in selected])
        r['conditions'].append(dict(condition=key,label=label,seed_medians=values.tolist(),
            median=np.median(values,axis=0).tolist(),minimum=values.min(axis=0).tolist(),maximum=values.max(axis=0).tolist()))
    fig,axes=plt.subplots(2,2,figsize=(12,8),layout='constrained');line=[75,112,187]
    for row,color in zip(r['conditions'],['#8798a4','#28776c','#d9a449']):
        axes[0,0].plot(line,row['median'],'o-',label=row['label'],color=color)
        axes[0,0].fill_between(line,row['minimum'],row['maximum'],alpha=.12,color=color)
    for part,color in [('train','#243d5a'),('check','#697c86')]:axes[0,0].plot(line,source[part]['raw_log_std'],'s--',label='F2 '+part,color=color)
    axes[0,0].set(title='Same observer: all72blocks; range of3seeds',xlabel='acoustic line (Hz)',ylabel='log magnitude std');axes[0,0].legend(fontsize=8)
    for part,color in [('train','#243d5a'),('check','#d9a449')]:
        row=next(x for x in compilation['assessment'] if x['part']==part)
        axes[0,1].plot(np.arange(7),np.array(row['band_error_dB'])[1:-1,0],'o-',label=part,color=color)
    axes[0,1].set_xticks(np.arange(7),['30-120','120-400','400-1.2k','1.2-2.2k','2.2-4k','4-8k','8-14k'],rotation=22)
    axes[0,1].set(title='Expected residual band error; only2bands fitted',ylabel='prediction/source dB');axes[0,1].legend()
    for key,color in [('0.0','#8798a4'),('0.5','#28776c'),('1.0','#d9a449')]:
        rms=[row['files']['mix_'+key]['rms'] for row in render['renders']]
        axes[1,0].plot([149921,277139,381611],rms,'o-',label=labels[key],color=color)
    axes[1,0].set(title='Realized whole mix RMS, unchanged shared gain',xlabel='seed',ylabel='RMS FS');axes[1,0].legend(fontsize=8)
    profile=load(a.workspace/'baselines/fixed_source_profiles_v1/evidence/trial1/F2_tailpipe/profile.json')
    old=np.array(profile['modal']['amplitude_LR'])[[1,2,4],0];new=np.array(model['main_amplitude_LR'])[:,0]
    axes[1,1].bar(np.arange(3)-.15,old,width=.3,label='old main RMS',color='#8798a4');axes[1,1].bar(np.arange(3)+.15,new,width=.3,label='source-derived RMS',color='#28776c')
    axes[1,1].set_xticks(np.arange(3),line);axes[1,1].set(title='Coherent main allocation, not a master gain',xlabel='acoustic line (Hz)',ylabel='amplitude');axes[1,1].legend(fontsize=8)
    for ax in axes.flat:ax.grid(alpha=.2)
    fig.suptitle('Idle joint budget:187Hz fluctuation closer;75Hz dynamics and AM/PM gaps remain',fontsize=13)
    figure=a.out/'assessment.png';fig.savefig(figure,dpi=150);plt.close(fig)
    r.update(result='finite_joint_budget_audio_assessed',source_stats=source,
        low_gain_ratio=(np.array(compilation['new_low_gains'])/np.array(compilation['old_low_gains'])).tolist(),
        main_amplitude_ratio=(new/old).tolist(),figure=dict(file=figure.name,sha256=sha(figure)),
        expected_band_fit_not_realized_audio_identity=True,source_CHECK_already_inspected=True,
        independent_phase_AM_and_source_cross_limits_remain=True,runtime_changed=False,listening_accepted=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(dict(result=r['result'],conditions=r['conditions'],low_gain_ratio=r['low_gain_ratio']),flush=True)
