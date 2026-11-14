"""Expose conservative native observer bounds, including uninformative tail results."""
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
r=dict(result='all12_energy_observer_upper_bounds_assessed_NOT_acceptance',input_sha256=sha(args.input/'report.json'),audit_sha256=sha(args.audit/'report.json'),cases=[],figures=[],vacuous_counts=dict(path=0,carrier=0,total=0))
figure,axes=plt.subplots(1,3,figsize=(14,5),layout='constrained');coords=['4-8 L','4-8 R','8-14 L','8-14 R'];tables=[[],[],[]];labels=[]
for row in run['observations']:
    assert sha(args.input/row['file'])==row['sha256']
    with np.load(args.input/row['file']) as f:
        item=dict(segment=row['segment'],branch=row['branch'],fit_available=row['fit_available'],expected=f['expected'].tolist(),source_target=f['source_target'].tolist(),
            actual_mean=f['actual'].mean(axis=(0,1)).tolist(),conditional_mean=f['conditional'].mean(axis=(0,1)).tolist(),bounds={})
        for table,name in zip(tables,['path','carrier','total']):
            difference=f[name+'_difference'];bound=f[name+'_variance_bound_pooled'];prob=f[name+'_marginal_Chebyshev_upper']
            item['bounds'][name]=dict(difference=difference.tolist(),variance_upper=bound.tolist(),sqrt_variance_upper=np.sqrt(bound).tolist(),
                marginal_Chebyshev_upper=prob.tolist(),all24_effects=(f['conditional']-f['expected'] if name=='path' else f['actual']-f['conditional'] if name=='carrier' else f['actual']-f['expected']).tolist())
            table.append(prob);r['vacuous_counts'][name]+=int(np.sum(prob==1.))
        r['cases'].append(item);labels.append(row['segment'].replace('F3_','')+' / '+row['branch'].replace('phase_','P'))
        if row['branch']!='original':continue
        column=['F3_fifth1','F3_fifth2','F3_sixth'].index(row['segment']);ax=axes[column];x=np.arange(4)
        for index,(name,colour) in enumerate([('path','#a68050'),('carrier','#365eaa'),('total','#7d5c78')]):
            b=item['bounds'][name];ax.plot(x+(index-1)*.18,np.sqrt(b['variance_upper']),'s',color=colour,ms=5,label=name+' sqrt(variance upper bound)')
            ax.plot(x+(index-1)*.18,abs(np.array(b['difference'])),'x',color=colour,ms=5,label=name+' |existing mean discrepancy|')
        ax.set_yscale('log');ax.set_xticks(x,coords,rotation=25);ax.set(title=row['segment'],ylabel='Different quantities on common statistic scale');ax.grid(alpha=.15)
        if column==0:ax.legend(fontsize=6)
figure.suptitle('Actual finite energy observer | conservative variance upper bounds vs existing discrepancies\nSquare roots are UPPER bounds on SD, NOT estimated SDs or confidence intervals',fontsize=12)
fig2,axes2=plt.subplots(1,3,figsize=(14,7),layout='constrained')
for table,ax,name in zip(tables,axes2,['Conditional path','Carrier remainder','Total']):
    table=np.array(table);im=ax.imshow(table,aspect='auto',vmin=0,vmax=1,cmap='viridis');ax.set_xticks(range(4),coords,rotation=25)
    ax.set_yticks(range(12),labels,fontsize=7);ax.set_title(name+' | marginal probability UPPER bound',fontsize=9)
    for i in range(12):
        for j in range(4):ax.text(j,i,f'{table[i,j]:.2f}',ha='center',va='center',fontsize=7,color='black' if table[i,j]>.6 else 'white')
fig2.colorbar(im,ax=axes2,shrink=.65);fig2.suptitle('Chebyshev upper bounds at the existing fixed-coordinate discrepancies\n1.00 means uninformative; no significance, familywise or postselected worst-cell claim',fontsize=12)
for name,fig in [('bounds.png',figure),('tail_limits.png',fig2)]:
    path=args.out/name;fig.savefig(path,dpi=150);plt.close(fig);r['figures'].append(dict(file=name,sha256=sha(path)))
r.update(not_exact_variance_or_normal_CI=True,full_finite_observer_discrepancy_not_settled=True,new_audio=False,
    next='The valid but conservative bounds do not settle the existing output-energy discrepancy. Next a tighter four-time moment contraction retaining signed group centering, or a separately qualified source-supported gain law; do not use a probability upper bound of1 as evidence that the draw is typical, or promote to realtime. Full cross-lags/refilter/state/source phase qualifications remain.')
save(args.out/'report.json',r)
print(dict(result=r['result'],vacuous_counts=r['vacuous_counts']),flush=True)
for row in r['cases']:
    if row['branch']=='original':print(dict(segment=row['segment'],right_high_band={k:{key:value[3] for key,value in v.items() if key!='all24_effects'} for k,v in row['bounds'].items()}),flush=True)
