"""Report complete second-chaos variance bounds, without converting them to listening approval."""
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
r=dict(result='all12_second_chaos_brackets_assessed_NOT_acceptance',input_sha256=sha(a.input/'report.json'),
    audit_sha256=sha(a.audit/'report.json'),cases=[],figures=[],vacuous_counts=dict(path=0,total=0),improved_coordinates=0)
keys=['expected','first_variance_pooled','second_variance_pooled','remainder_upper_pooled','variance_lower_pooled','variance_upper_pooled',
    'prior_path_upper','prior_total_upper','prior_carrier_upper','combined_path_upper','combined_total_upper','path_difference','carrier_difference','total_difference',
    'path_tail_upper','total_tail_upper','actual','conditional']
fig,axes=plt.subplots(1,3,figsize=(14,5),layout='constrained');labels=[];ratios=[];tails=[];coords=['4-8 L','4-8 R','8-14 L','8-14 R']
for row in run['observations']:
    assert sha(a.input/row['file'])==row['sha256']
    with np.load(a.input/row['file']) as f:
        item={k:f[k].tolist() for k in keys};item.update(segment=row['segment'],branch=row['branch'],fit_available=row['fit_available'])
        item['upper_ratio']=(f['combined_path_upper']/f['prior_path_upper']).tolist()
        r['cases'].append(item);labels.append(row['segment'].replace('F3_','')+' / '+row['branch'].replace('phase_','P'))
        ratios.append(item['upper_ratio']);tails.append(item['path_tail_upper'])
        r['improved_coordinates']+=int(np.sum(f['combined_path_upper']<f['prior_path_upper']))
        for name in ['path','total']:r['vacuous_counts'][name]+=int(np.sum(f[name+'_tail_upper']==1))
        if row['branch']!='original':continue
        column=['F3_fifth1','F3_fifth2','F3_sixth'].index(row['segment']);ax=axes[column];x=np.arange(4)
        ax.vlines(x,f['variance_lower_pooled'],f['combined_path_upper'],color='#30679f',lw=3,label='Variance bracket, NOT confidence interval')
        ax.plot(x,f['variance_lower_pooled'],'o',color='#30679f',ms=4,label='Exact first + second lower bound')
        ax.plot(x,f['combined_path_upper'],'s',color='#30679f',ms=4,label='Cubic remainder upper bound (min prior)')
        ax.plot(x,f['prior_path_upper'],'_',color='#ad7948',ms=13,label='Prior first-chaos upper bound')
        ax.set_yscale('log');ax.set_xticks(x,coords,rotation=25);ax.set(title=row['segment'],ylabel='Pooled3 Var(F), dimensionless');ax.grid(alpha=.15)
        if column==0:ax.legend(fontsize=6)
fig.suptitle('Exact FULL second Gaussian chaos | all native groups and eight continuous blocks\nThis is a statistical order, not engine firing order or OSC count',fontsize=12)
fig2,axes2=plt.subplots(1,2,figsize=(13,7),layout='constrained')
for values,ax,title in [(ratios,axes2[0],'New / prior path variance upper bound'),(tails,axes2[1],'Marginal probability upper bound | 1 = uninformative')]:
    values=np.array(values);im=ax.imshow(values,vmin=0,vmax=1,aspect='auto',cmap='viridis')
    ax.set_yticks(range(12),labels,fontsize=7);ax.set_xticks(range(4),coords,rotation=25);ax.set_title(title,fontsize=10)
    for i in range(12):
        for j in range(4):ax.text(j,i,f'{values[i,j]:.3g}',ha='center',va='center',fontsize=7,color='black' if values[i,j]>.6 else 'white')
    fig2.colorbar(im,ax=ax,shrink=.65)
fig2.suptitle('All12 frozen models / four coordinates | old actual observations unchanged',fontsize=12)
for name,figure in [('variance_brackets.png',fig),('bound_changes.png',fig2)]:
    path=a.out/name;figure.savefig(path,dpi=150);plt.close(figure);r['figures'].append(dict(file=name,sha256=sha(path)))
r.update(variance_brackets_not_CI=True,full_variance_not_computed=True,not_listening_approval=True,
    next='Close this bounded numerical study. Its bounds do not qualify timbre or full observer uncertainty. Return to the pending source-derived idle candidate and driving/state work; do not automatically start another higher-chaos study or change source gains to force a pass. Preserve original common-phase/full-MSC/refilter requirements.')
save(a.out/'report.json',r)
print(dict(result=r['result'],vacuous=r['vacuous_counts'],improved=r['improved_coordinates']),flush=True)
for row in r['cases']:
    if row['branch']=='original':print(dict(segment=row['segment'],right_high={key:row[key][3] for key in ['first_variance_pooled','second_variance_pooled','variance_lower_pooled','combined_path_upper','combined_total_upper','path_tail_upper','total_tail_upper']}),flush=True)
