"""All conditional means and signed realization decompositions, without variance-component claims."""
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
r=dict(result='all12_fixed_gain_conditional_means_assessed_NOT_variance_or_voice',input_sha256=sha(a.input/'report.json'),audit_sha256=sha(a.audit/'report.json'),cases=[],figures=[])
coords=['4-8 L','4-8 R','8-14 L','8-14 R'];fig,axes=plt.subplots(2,3,figsize=(14,8),layout='constrained');labels=[];tables=[[],[],[]]
for row in run['observations']:
    assert sha(a.input/row['file'])==row['sha256']
    with np.load(a.input/row['file']) as f:
        item=dict(segment=row['segment'],branch=row['branch'],fit_available=row['fit_available'],
            expected=f['expected'].tolist(),source_target=f['source_target'].tolist(),
            mean_actual=f['actual'].mean(axis=(0,1)).tolist(),mean_conditional=f['conditional'].mean(axis=(0,1)).tolist(),
            mean_path_part=f['path'].mean(axis=(0,1)).tolist(),mean_carrier_part=f['carrier'].mean(axis=(0,1)).tolist(),
            mean_gain_path_effect=f['gain_path_effect'].mean(axis=(0,1)).tolist(),mean_carrier_realization_effect=f['carrier_realization_effect'].mean(axis=(0,1)).tolist(),
            mean_total_effect=f['total_effect'].mean(axis=(0,1)).tolist(),minimum_conditional_carrier_part=float(f['carrier'].min()),
            run_mean_actual=f['actual'].mean(axis=1).tolist(),run_mean_conditional=f['conditional'].mean(axis=1).tolist(),
            all24_actual=f['actual'].tolist(),all24_conditional=f['conditional'].tolist(),
            maximum_arithmetic_error=float(abs(f['total_effect']-f['gain_path_effect']-f['carrier_realization_effect']).max()))
        r['cases'].append(item);labels.append(row['segment'].replace('F3_','')+' / '+row['branch'].replace('phase_','P'))
        for table,key in zip(tables,['mean_gain_path_effect','mean_carrier_realization_effect','mean_total_effect']):table.append(item[key])
        if row['branch']!='original':continue
        col=['F3_fifth1','F3_fifth2','F3_sixth'].index(row['segment']);ax=axes[0,col];x=np.arange(24)
        ax.plot(x,f['actual'][:,:,3].ravel(),'o-',color='#365eaa',label='Existing actual S',ms=3)
        ax.plot(x,f['conditional'][:,:,3].ravel(),'s-',color='#b28650',label='Exact E[S | existing gain path]',ms=3)
        ax.axhline(f['expected'][3],color='#596168',label='Unconditional E[S]');ax.axhline(f['source_target'][3],color='#247f73',ls='--',label='Source target')
        for k in [7.5,15.5]:ax.axvline(k,color='#9aa4a8',lw=.6)
        ax.set(title=row['segment']+' | 8-14 R, zero lag',xlabel='All24 blocks, 8 per run',ylabel='Normalized within-tile energy variance');ax.grid(alpha=.15)
        if col==0:ax.legend(fontsize=7)
        ax=axes[1,col];x=np.arange(4)
        for index,(key,label,colour) in enumerate([('mean_gain_path_effect','E[S|g] - E[S]','#b28650'),('mean_carrier_realization_effect','S - E[S|g]','#365eaa'),('mean_total_effect','S - E[S]','#7d5c78')]):
            ax.bar(x+(index-1)*.24,item[key],width=.22,color=colour,label=label)
        ax.set_xticks(x,coords,rotation=25);ax.set_ylabel('Signed mean discrepancy');ax.axhline(0,color='#9aa4a8',lw=.6);ax.grid(axis='y',alpha=.15)
        if col==0:ax.legend(fontsize=7)
fig.suptitle('Condition on the original gain trajectories | exact Gaussian-carrier conditional mean\nArithmetic realization decomposition, not independent variance components or a confidence interval',fontsize=12)
fig2,ax2=plt.subplots(1,3,figsize=(14,7),layout='constrained');limit=max(abs(np.array(table)).max() for table in tables)
for table,ax,title in zip(tables,ax2,['Gain-path shift: E[S|g] - E[S]','Carrier realization: S - E[S|g]','Total: S - E[S]']):
    table=np.array(table);im=ax.imshow(table,aspect='auto',cmap='coolwarm',vmin=-limit,vmax=limit);ax.set_yticks(range(12),labels,fontsize=7)
    ax.set_xticks(range(4),coords,rotation=25);ax.set_title(title,fontsize=10)
    for i in range(12):
        for j in range(4):ax.text(j,i,f'{table[i,j]:.4f}',ha='center',va='center',fontsize=7,color='white' if abs(table[i,j])>.6*limit else 'black')
fig2.colorbar(im,ax=ax2,shrink=.65);fig2.suptitle('All12 terminal models, all4 zero-lag diagonal entries\nUnavailable controls remain diagnostic; all existing blocks retained',fontsize=12)
for name,figure in [('conditional_paths.png',fig),('all_cases.png',fig2)]:
    path=a.out/name;figure.savefig(path,dpi=150);plt.close(figure);r['figures'].append(dict(file=name,sha256=sha(path)))
r.update(conditional_mean_not_VarS_qualification=True,not_independent_variance_components=True,new_audio=False,
    next='The existing fifth2 high-band excess is largely already present in the conditional mean given its gain paths. Next quantify finite gain-path observer uncertainty or qualify a source-supported gain law; preserve carrier residual and all original source-state/time gaps. Do not infer mechanical causes, clip peaks or change seeds/strengths. Full Var(S), cross-lags and post-refilter fourth moments remain unsolved before realtime promotion.')
save(a.out/'report.json',r)
for row in r['cases']:
    if row['branch']=='original':print(dict(segment=row['segment'],expected=row['expected'],actual=row['mean_actual'],conditional=row['mean_conditional'],path_shift=row['mean_gain_path_effect'],carrier_remainder=row['mean_carrier_realization_effect']),flush=True)
