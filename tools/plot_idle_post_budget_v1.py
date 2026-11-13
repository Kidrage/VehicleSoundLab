"""Display allocation and all ten zero-lag outcomes, including remaining cross gaps."""
import argparse
import shutil
import sys
from pathlib import Path
p = argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','audit','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from research_archive_v1 import load,save,sha

a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_plot.py')
r=load(a.input/'report.json');audit=load(a.audit/'report.json')
assert audit['result']=='all2048_POST_kernels_source_budget_inverse_and64jackknife_verified'
assert audit['input_report_sha256']==sha(a.input/'report.json')
source=np.asarray(r['sourceQ']);old=np.asarray(r['old_predictions']);new=np.asarray(r['new_predictions'])
gaussian=np.array([np.asarray(z['gaussian'])/z['denominator'] for z in r['states']])
low=np.asarray(r['jackknife']['low'])[4:].reshape(2,10);high=np.asarray(r['jackknife']['high'])[4:].reshape(2,10)
bands=['1.2-2.2','2.2-4','4-8','8-14'];pairs=[(b,c) for b in range(4) for c in range(b,4)]
auto=[0,4,7,9];cross=[i for i,(b,c) in enumerate(pairs) if b!=c]
images=[]
fig,axes=plt.subplots(1,2,figsize=(13,5),layout='constrained')
x=np.arange(4)
axes[0].bar(x-.17,r['old_kappa'],width=.34,color='#b87a60',label='Old independent kappa')
kappa=np.asarray(r['allocation']['kappa']);error=np.asarray(r['jackknife']['high'][:4])-kappa
axes[0].bar(x+.17,kappa,width=.34,color='#267f8d',label='Reallocated kappa',yerr=error,capsize=3)
axes[0].set(title='Independent concentration after adding periodic amplitude',xticks=x,xticklabels=bands,
            xlabel='Input branch nominal band (kHz)',ylabel='Innovation excess kappa')
axes[0].legend();axes[0].grid(axis='y',alpha=.2)
for block,offset in [(0,-.1),(1,.1)]:
    axes[1].plot(x+offset,source[block,auto],'o',color='black',label=f'F2 {"TRAIN" if block==0 else "check"}')
    axes[1].plot(x+offset,old[block,auto],':',color='#b87a60',label=f'POST + old kappa B{block}')
    axes[1].errorbar(x+offset,new[block,auto],yerr=[new[block,auto]-low[block,auto],high[block,auto]-new[block,auto]],
                     fmt='o-',color='#267f8d',alpha=1 if block==0 else .6,capsize=3,label=f'POST + allocated B{block}')
axes[1].set(title='All four marginal cumulants; TRAIN fit is not validation',xticks=x,xticklabels=bands,
            xlabel='Observed band (kHz)',ylabel='Normalized fourth cumulant')
axes[1].legend(fontsize=8);axes[1].grid(alpha=.2)
fig.suptitle('Actual POST-resonance + main | 2048 sampled time origins\nConditional innovation moments computed from kernels; approximate time-MC intervals only')
name='allocation_and_marginals.png';fig.savefig(a.out/name,dpi=150);plt.close(fig)
images.append(dict(file=name,sha256=sha(a.out/name)))
fig,axes=plt.subplots(2,3,figsize=(13,8),layout='constrained')
for ax,j in zip(axes.flat,cross):
    b,c=pairs[j]
    ax.plot([0,1],source[:,j],'o-',color='black',lw=2,label='F2 TRAIN / check')
    ax.plot([0,1],gaussian[:,j],':',color='#8c68a4',label='POST Gaussian budget')
    ax.plot([0,1],old[:,j],'--',color='#b87a60',label='POST + old kappa')
    ax.errorbar([0,1],new[:,j],yerr=[new[:,j]-low[:,j],high[:,j]-new[:,j]],fmt='o-',
                color='#267f8d',capsize=4,label='POST + allocated kappa')
    ax.set(title=bands[b]+' / '+bands[c]+' kHz',xticks=[0,1],xticklabels=['TRAIN vs B0','check vs B1'],ylabel='Normalized fourth cumulant')
    ax.grid(alpha=.2);ax.set_ylim(bottom=0)
handles,labels=axes.flat[0].get_legend_handles_labels()
fig.legend(handles,labels,loc='outside lower center',ncol=2)
fig.suptitle('All six mixed moments remain below F2 despite marginal allocation\nZero lag only; no full lag, source-separation, listening or runtime qualification')
name='all_cross_gaps.png';fig.savefig(a.out/name,dpi=150);plt.close(fig)
images.append(dict(file=name,sha256=sha(a.out/name)))
save(a.out/'report.json',dict(result='all10zero_moments_and_all4allocations_plotted',input_report_sha256=sha(a.input/'report.json'),
    audit_sha256=sha(a.audit/'report.json'),images=images,
    old_marginal_relative_error=(old[:,auto]/source[:,auto]-1).tolist(),
    new_cross_fraction_of_source=(new[:,cross]/source[:,cross]).tolist(),
    all12_cross_under_source=bool(np.all(new[:,cross]<source[:,cross]))))
print(dict(result='plot_complete',cross_fraction=(new[:,cross]/source[:,cross]).tolist()))
