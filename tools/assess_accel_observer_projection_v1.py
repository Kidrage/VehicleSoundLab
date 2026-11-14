"""Assess all variance brackets without presenting first-chaos variance as the full answer."""
import argparse,os,shutil,sys
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','audit','out']:parser.add_argument('--'+key,type=Path,required=True)
args=parser.parse_args();sys.path.insert(0,str(args.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from research_archive_v1 import load,save,sha

args.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,args.out/'executed_assessment.py')
run=load(args.input/'report.json');audit=load(args.audit/'report.json');assert audit['result']=='passed'
r=dict(result='all12_signed_projection_brackets_assessed_NOT_acceptance',input_sha256=sha(args.input/'report.json'),audit_sha256=sha(args.audit/'report.json'),cases=[],figures=[],vacuous_counts=dict(path=0,total=0))
fig,axes=plt.subplots(1,3,figsize=(14,5),layout='constrained');coords=['4-8 L','4-8 R','8-14 L','8-14 R'];labels=[];ratios=[];table=[]
for row in run['observations']:
    assert sha(args.input/row['file'])==row['sha256']
    with np.load(args.input/row['file']) as f:
        item=dict(segment=row['segment'],branch=row['branch'],fit_available=row['fit_available'],expected=f['expected'].tolist(),first_lower=f['first_variance_pooled'].tolist(),
            remainder_upper=f['remainder_variance_upper_pooled'].tolist(),new_projection_upper=f['variance_upper_pooled'].tolist(),prior_path_upper=f['prior_path_upper'].tolist(),
            combined_path_upper=f['combined_path_upper'].tolist(),prior_carrier_upper=f['prior_carrier_upper'].tolist(),prior_total_upper=f['prior_total_upper'].tolist(),combined_total_upper=f['combined_total_upper'].tolist(),
            path_difference=f['path_difference'].tolist(),carrier_difference=f['carrier_difference'].tolist(),total_difference=f['total_difference'].tolist(),
            path_tail_upper=f['path_marginal_tail_upper'].tolist(),total_tail_upper=f['total_marginal_tail_upper'].tolist(),
            combined_over_prior_path_ratio=(f['combined_path_upper']/f['prior_path_upper']).tolist(),
            combined_over_prior_total_ratio=(f['combined_total_upper']/f['prior_total_upper']).tolist(),
            all24_actual=f['actual'].tolist(),all24_conditional=f['conditional'].tolist())
        r['cases'].append(item);labels.append(row['segment'].replace('F3_','')+' / '+row['branch'].replace('phase_','P'))
        ratios.append(item['combined_over_prior_path_ratio']);table.append(item['path_tail_upper'])
        for name in ['path','total']:r['vacuous_counts'][name]+=int(np.sum(f[name+'_marginal_tail_upper']==1.))
        if row['branch']!='original':continue
        column=['F3_fifth1','F3_fifth2','F3_sixth'].index(row['segment']);ax=axes[column];x=np.arange(4)
        ax.vlines(x,f['first_variance_pooled'],f['combined_path_upper'],color='#365eaa',lw=3,label='Variance bracket for F, NOT a confidence interval')
        ax.plot(x,f['first_variance_pooled'],'o',ms=4,color='#365eaa',label='Exact first-chaos lower bound')
        ax.plot(x,f['combined_path_upper'],'s',ms=4,color='#365eaa',label='Projection + remainder upper bound')
        ax.plot(x,f['prior_path_upper'],'_',ms=12,color='#a68050',label='Prior Poincare upper bound')
        ax.set_yscale('log');ax.set_xticks(x,coords,rotation=25);ax.set(title=row['segment'],ylabel='Pooled3 Var(F) | lower and upper bounds');ax.grid(alpha=.15)
        if column==0:ax.legend(fontsize=6)
fig.suptitle('Signed native first projection of the actual conditional energy observer\nFirst order is only part of Var(F); remainder and full carrier variance are still unresolved',fontsize=12)
fig2,ax=plt.subplots(1,2,figsize=(13,7),layout='constrained')
for values,axis,title in [(ratios,ax[0],'Combined / prior path-variance upper bound'),(table,ax[1],'Path marginal probability upper bound | 1 = uninformative')]:
    values=np.array(values);im=axis.imshow(values,vmin=0,vmax=1,aspect='auto',cmap='viridis');axis.set_yticks(range(12),labels,fontsize=7);axis.set_xticks(range(4),coords,rotation=25);axis.set_title(title,fontsize=10)
    for i in range(12):
        for j in range(4):axis.text(j,i,f'{values[i,j]:.3g}',ha='center',va='center',fontsize=7,color='black' if values[i,j]>.6 else 'white')
    fig2.colorbar(im,ax=axis,shrink=.65)
fig2.suptitle('All12 models / all4 coordinates | no seeds, strength or observed blocks changed',fontsize=12)
for name,figure in [('variance_brackets.png',fig),('bound_changes.png',fig2)]:
    path=args.out/name;figure.savefig(path,dpi=150);plt.close(figure);r['figures'].append(dict(file=name,sha256=sha(path)))
r.update(first_projection_not_exact_full_variance=True,variance_brackets_not_confidence_intervals=True,full_observer_discrepancy_not_settled=True,new_audio=False,
    next='The exact signed first projection tightens the conditional-mean variance bound, but its positive remainder and conditional-carrier uncertainty still prevent qualification of the existing discrepancy. Next retain signed higher-chaos/four-time contractions rather than replacing all remaining terms by absolute row sums; no voice/C promotion, new seed/strength rescue or normality claim. Full11lags/refilter/state/source-phase requirements remain.')
save(args.out/'report.json',r);print(dict(result=r['result'],vacuous_counts=r['vacuous_counts']),flush=True)
for row in r['cases']:
    if row['branch']=='original':print(dict(segment=row['segment'],right_high={key:row[key][3] for key in ['first_lower','new_projection_upper','prior_path_upper','combined_path_upper','combined_total_upper','path_tail_upper','total_tail_upper']}),flush=True)
