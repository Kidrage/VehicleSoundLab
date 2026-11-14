"""Present the complete fixed shared-iid forward probe without fitting a new voice."""
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
r=dict(result='all12_forward_probes_assessed_not_a_voice',input_sha256=sha(a.input/'report.json'),
       audit_sha256=sha(a.audit/'report.json'),segments=[],figures=[],unavailable_pairs=0,pairs=0)
fig,axes=plt.subplots(2,3,figsize=(14,8),layout='constrained')
fig2,ax2=plt.subplots(1,3,figsize=(13,4.5),layout='constrained')
names=['4-8 L','4-8 R','8-14 L','8-14 R'];lags=np.arange(-5,6)*10
for column,segment in enumerate(['F3_fifth1','F3_fifth2','F3_sixth']):
    source=next(v for v in run['observations'] if v['segment']==segment and v['branch']=='original')
    controls=[v for v in run['observations'] if v['segment']==segment and v['branch']!='original'];assert len(controls)==3
    table=[]
    for row in [source,*controls]:
        r['pairs']+=len(row['pairs']);r['unavailable_pairs']+=sum(not v['Bernoulli_Gaussian_available'] for v in row['pairs'])
        table.append(dict(branch=row['branch'],pairs=row['pairs']))
    r['segments'].append(dict(segment=segment,observations=table))
    for row,(i,j,label) in enumerate([(0,2,'L cross-band'),(1,3,'R cross-band')]):
        pair=next(v for v in source['pairs'] if v['indices']==[i,j]);ctrl=np.array([next(v for v in c['pairs'] if v['indices']==[i,j])['observed_all11'] for c in controls])
        ax=axes[row,column];ax.fill_between(lags,ctrl.min(axis=0),ctrl.max(axis=0),color='#607481',alpha=.18,label='3 phase controls, not CI')
        ax.plot(lags,pair['observed_all11'],'o-',color='#247f73',ms=4,label='Original recording')
        ax.plot(lags,pair['prediction_all11'],'--',color='#aa7131',label='Shared iid, zero-lag matched')
        ax.scatter([0],[pair['observed_all11'][5]],s=75,facecolors='none',edgecolors='#352e3a',zorder=4,label='Matched by construction')
        ax.set(title=segment+' | '+label,xlabel='Within-tile lag (ms)',ylabel='Energy covariance / product of means')
        ax.axhline(0,color='#88939a',lw=.7);ax.grid(axis='y',alpha=.2)
        if row==column==0:ax.legend(fontsize=7)
    error=np.array([v['max_other_lag_error'] for v in source['pairs']]).reshape(4,4)
    image=ax2[column].imshow(error,cmap='magma',vmin=0,vmax=.3)
    ax2[column].set(title=segment);ax2[column].set_xticks(range(4),names,rotation=30);ax2[column].set_yticks(range(4),names)
    for i in range(4):
        for j in range(4):ax2[column].text(j,i,f'{error[i,j]:.3f}',ha='center',va='center',color='white' if error[i,j]<.16 else 'black',fontsize=8)
fig.suptitle('F3 high-frequency shared-iid/filter baseline | zero-lag match is not temporal validation\nExact 10ms energy + original finite-group centering; all signed lags retained',fontsize=12)
fig2.suptitle('All source pairs: maximum error across the 10 nonzero lags\nPairwise coefficients are optimistic diagnostics, not a valid four-channel model',fontsize=12)
fig2.colorbar(image,ax=ax2,shrink=.8,label='Normalized energy covariance error')
for name,figure in [('lag_shape.png',fig),('all_pairs.png',fig2)]:
    path=a.out/name;figure.savefig(path,dpi=150);plt.close(figure);r['figures'].append(dict(file=name,sha256=sha(path)))
assert r['pairs']==192
r.update(zero_lag_matching_not_validation=True,source_PSD_fitted=False,multichannel_model=False,error_figure_color_maximum=.3,
    new_audio=False,new_profile=False,runtime_changed=False,
    next='Retain this native forward observer as a baseline. Joint temporally persistent positive amplitude/variance processes must be qualified through native filters and finite group centering; preserve slow colour, band/LR-specific and independent components. Do not infer mechanical clock or copy source energy trajectories, and do not boost impulse kurtosis to repair lag-shape failure. Pending idle candidate remains unchanged before listening and isolated C migration.')
save(a.out/'report.json',r);print(dict(result=r['result'],pairs=r['pairs'],unavailable_pairs=r['unavailable_pairs']),flush=True)
