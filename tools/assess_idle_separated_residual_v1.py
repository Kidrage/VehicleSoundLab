"""Summarize the fixed low-residual hypothesis without converting metrics to hearing scores."""
import argparse,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','audit','observation','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from research_archive_v1 import load,save,sha

a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_assessment.py')
audit=load(a.audit/'report.json');assert audit['result']=='passed'
render=load(a.input/'report.json');observation=load(a.observation/'report.json')
profile=load(a.workspace/'baselines/fixed_source_profiles_v1/evidence/trial1/F2_tailpipe/profile.json')
with np.load(a.input/'extraction.npz') as f:taps=f['taps'];residual=f['residual']
source={row['part']:row['aware'] for row in observation['observations'] if row['seed'] is None}
conditions={'0.0':'Previous idle','0.5':'New low residual','1.0':'New residual + AM50%'}
r=dict(result='fixed_residual_shape_contrasts_assessed',input_sha256=sha(a.input/'report.json'),
       audit_sha256=sha(a.audit/'report.json'),source_stats=source,generated_summary=[],
       covariance_is_not_a_hearing_score=True,source_CHECK_not_fitted=True,source_CHECK_already_inspected=True,
       phase_aware_projection_not_physical_separation=True,AM_not_fully_separated_from_low_residual=True,
       runtime_changed=False,listening_accepted=False)
fig,axes=plt.subplots(2,2,figsize=(12,8),layout='constrained')
for condition,color in [('0.0','#8798a4'),('0.5','#28776c'),('1.0','#d9a449')]:
    selected=[x for x in audit['comparisons'] if x['condition']==condition]
    values=np.array([x['median_observed_std'] for x in selected]);median=np.median(values,axis=0)
    r['generated_summary'].append(dict(condition=condition,label=conditions[condition],
        median_of_seed_medians=median.tolist(),minimum=values.min(axis=0).tolist(),maximum=values.max(axis=0).tolist()))
    axes[0,0].plot([75,112,187],median,'o-',color=color,label=conditions[condition]);axes[0,0].fill_between([75,112,187],values.min(axis=0),values.max(axis=0),color=color,alpha=.12)
for part,color in [('train','#243d5a'),('check','#697c86')]:axes[0,0].plot([75,112,187],source[part]['raw_log_std'],'s--',color=color,label='F2 '+part)
axes[0,0].set(title='Same acoustic observer, all 72 generated blocks',xlabel='acoustic line (Hz)',ylabel='log amplitude std');axes[0,0].legend(fontsize=8)
hz=np.fft.rfftfreq(65536,1/48000)
for j in range(2):
    ax=axes[0,1] if j==0 else axes[1,0]
    for name,h,color in [('Previous',np.array(profile['kernels'][j]['taps']),'#8798a4'),('Projected residual',taps[j],'#28776c')]:
        response=abs(np.fft.rfft(h,65536))
        ax.plot(hz,20*np.log10(np.maximum(response,1e-12)),label=name,color=color)
    ax.set(xlim=(50,1400),ylim=(-55,40),title=str(profile['kernels'][j]['band_hz'])+' Hz kernel, unit norm',xlabel='Hz',ylabel='response dB');ax.legend(fontsize=8)
ax=axes[1,1]
for seed,color in [(149921,'#28776c'),(277139,'#d9a449'),(381611,'#697c86')]:
    before=next(x for x in audit['comparisons'] if x['seed']==seed and x['condition']=='0.0')
    after=next(x for x in audit['comparisons'] if x['seed']==seed and x['condition']=='0.5')
    ax.plot([112,187],np.array(after['median_observed_std'])[1:]/np.array(before['median_observed_std'])[1:],'o-',label=str(seed),color=color)
ax.set(title='New/old observed fluctuation; not perceived quality',xlabel='acoustic line (Hz)',ylabel='ratio');ax.legend()
for ax in axes.flat:ax.grid(alpha=.2)
fig.suptitle('Idle: project main lines before shaping independent low detail; 187 Hz gap remains',fontsize=13)
figure=a.out/'assessment.png';fig.savefig(figure,dpi=150);plt.close(fig)
r['figure']=dict(file=figure.name,sha256=sha(figure));save(a.out/'report.json',r)
print(dict(result=r['result'],summaries=r['generated_summary']),flush=True)
