"""Read-only full-case comparison of the audited known candidate experiment."""
import argparse
import shutil
import sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','audit','diagnostic','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args()
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from research_archive_v1 import load,save,sha
a.out.mkdir(parents=True,exist_ok=False)
audit=load(a.audit/'report.json')
diag=load(a.diagnostic/'report.json')
assert audit['input_report_sha256']==diag['input_report_sha256']==sha(a.input/'report.json')
assert diag['audit_report_sha256']==sha(a.audit/'report.json') and audit['qualified'] is False
fig,axes=plt.subplots(2,2,figsize=(16,10),layout='constrained')
ax=axes[0,0]
folder=a.input/'cubic_control'
truth=load(folder/'truth.json')['rows']
for filename,label,color in [('native_fits.json','Native candidates','#9f6b48'),('fits.json','Causal candidates + current wave','#087b78')]:
    rows=load(folder/filename)
    freq=[next((v['frequency_hz'] for v in row['lines'] if v['eligible'] and abs(v['frequency_hz']-115.7)<2),np.nan) for row in rows]
    ax.plot(range(12),freq,'o-',label=label,color=color,alpha=.8)
ax.axhline(115.7,color='black',ls=':',label='Known weak component')
ax.axvspan(8.5,11.5,color='#eee1cb',alpha=.5)
ax.set(xlabel='Window (0.25 s)',ylabel='Frequency (Hz)',title='Weak-line prerequisite: all 3 omissions recovered',ylim=(115.65,115.75),xticks=range(12))
ax.legend(fontsize=8)
ax=axes[0,1]
base=np.arange(6)
palette=['#bbbbbb','#4084ad','#087b78']
for shift,case in [(0,'fm_only'),(7.5,'am_fm')]:
    score=load(a.input/case/'scores.json')
    for j,key in enumerate(['previous_old','native_boundary','augmented_boundary']):
        values=[v['longest_correct_contiguous'] for v in score[key]['components'][:6]]
        ax.bar(base+shift+(j-1)*.25,values,width=.23,color=palette[j],label=key if shift==0 else None)
ax.axhline(5,color='#a73838',ls='--',lw=1,label='Required 5 windows')
ax.set(xticks=list(base)+list(base+7.5),xticklabels=['43','65','89','116','138','179']*2,
    ylabel='Longest correctly identified contiguous run',title='FM (left) / AM+FM (right): complete low-band inventory',ylim=(0,13))
ax.legend(fontsize=8,loc='lower left')
ax=axes[1,0]
case_names=[]
for k,value in enumerate(diag['cases']):
    case_names.append(value['case'])
    ax.plot(range(12),[k]*12,'o',color='#dbe3e8',ms=7)
    ax.plot(value['native_failed_windows'],[k-.1]*len(value['native_failed_windows']),'x',color='#4084ad',ms=7,
        label='Native fit failed' if k==0 else None)
    ax.plot(value['augmented_failed_windows'],[k+.1]*len(value['augmented_failed_windows']),'x',color='#ba4b3d',ms=7,
        label='Augmented fit failed' if k==0 else None)
ax.set(yticks=range(9),yticklabels=case_names,xticks=range(12),xlabel='Window (0.25 s)',title='All 108 windows retained, including failures')
ax.invert_yaxis()
ax.legend(fontsize=8,loc='lower left')
ax=axes[1,1]
for i,test in enumerate(diag['all_conditional_tests']):
    gain=min(test['partial_gain_LR'])
    ax.scatter(i,gain,color='#087b78' if test['accepted'] else '#ba4b3d',marker='o' if test['accepted'] else 'x',s=45)
ax.axhline(.8,color='black',ls='--',lw=1)
ax.set(xlabel='All added candidates, in fixed case/window order',ylabel='Minimum LR conditional partial gain',
    title='22 null tests: 4 accepted / 18 rejected',ylim=(-.05,1.05),xticks=range(0,22,2))
ax.text(.03,.48,'Gain alone is insufficient: original local gates + unique predecessor also required.\nConditional fixed-parameter null, not statistical confidence.',
    transform=ax.transAxes,fontsize=8)
for ax in axes.flat:ax.grid(axis='y',alpha=.15)
fig.suptitle('Observed candidate propagation V1 — known prerequisite repaired; full qualification FAILED',fontsize=15)
path=a.out/'comparison.png'
fig.savefig(path,dpi=140)
plt.close(fig)
dest=a.out/'exact_sources/tools/plot_candidate_presence_v1.py'
dest.parent.mkdir(parents=True,exist_ok=True)
shutil.copy2(Path(__file__),dest)
save(a.out/'report.json',dict(result='audited_all108_and22null_comparison_plotted',
    input_report_sha256=sha(a.input/'report.json'),audit_report_sha256=sha(a.audit/'report.json'),
    diagnostic_report_sha256=sha(a.diagnostic/'report.json'),images={'comparison.png':sha(path)},
    truth_used_only_for_postfit_display=True))
print(path)
