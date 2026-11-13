"""All known controls, every prediction decision and retained solver failures."""
import argparse
import shutil
import sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','audit','out']:p.add_argument('--'+key,type=Path,required=True)
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
assert audit['input_report_sha256']==sha(a.input/'report.json') and audit['qualified_known_controls']
fig,axes=plt.subplots(2,2,figsize=(15,9),layout='constrained')
ax=axes[0,0]
offsets=np.arange(6)
for shift,case in [(0,'fm_only'),(7.5,'am_fm')]:
    scores=load(a.input/case/'scores.json')
    for j,(key,label,color) in enumerate([('unscreened_boundary','Previous augmentation','#b95b4e'),
        ('native_boundary','Native observation','#9ca8b2'),('selected_boundary','Declared prediction/adoption','#087b78')]):
        values=[v['longest_correct_contiguous'] for v in scores[key]['components'][:6]]
        ax.bar(offsets+shift+(j-1)*.25,values,width=.23,color=color,label=label if not shift else None)
ax.axhline(5,color='black',ls='--',lw=1)
ax.set(xticks=list(offsets)+list(offsets+7.5),xticklabels=['43','65','89','116','138','179']*2,
    ylabel='Correct contiguous windows',title='FM (left) and AM+FM (right): all six low components',ylim=(0,13))
ax.legend(fontsize=8,loc='lower left')
ax=axes[0,1]
records=[]
labels=[]
for case in [v['case'] for v in audit['cases']]:
    for i,decision in enumerate(load(a.input/case/'decisions.json')):
        for test in decision['tests']:records.append((case,i,test))
colors={'supported':'#087b78','unknown_solver_failure':'#71869d','unsupported_by_verification':'#c16d32'}
markers={'supported':'o','unknown_solver_failure':'s','unsupported_by_verification':'x'}
for i,(case,window,test) in enumerate(records):
    state=test['state']
    ax.scatter(i,min(test['prediction_gain_LR']),color=colors[state],marker=markers[state],s=36,
        label=state if state not in labels else None)
    labels.append(state)
ax.axhline(.8,color='black',ls='--',lw=1)
ax.set_yscale('symlog',linthresh=1)
ax.set(xlabel='Every added candidate, fixed case/window order',ylabel='Minimum LR check residual reduction',
    title='26 predictions: 4 supported / 10 unknown / 12 unsupported')
ax.legend(fontsize=8,loc='lower left')
ax=axes[1,0]
cases=[v['case'] for v in audit['cases']]
for j,case in enumerate(cases):
    for i,(decision,row) in enumerate(zip(load(a.input/case/'decisions.json'),load(a.input/case/'fits.json'))):
        reason=decision['reason']
        color='#e3e8ec' if reason=='no_added_candidate' else '#087b78' if decision['augmented_adopted'] else '#71869d' if reason=='augmentation_unknown' else '#c16d32'
        ax.scatter(i,j,c=color,s=42)
        if not row['success']:ax.scatter(i,j,color='#9e3030',marker='x',s=65)
ax.set(xticks=range(12),yticks=range(9),yticklabels=cases,xlabel='Window (0.25 s)',
    title='All108 selected observations; native noise failures retained')
ax.invert_yaxis()
ax=axes[1,1]
folder=a.input/'cubic_control'
for filename,label,color in [('native_fits.json','Native (weak line omitted in last 3)','#9ca8b2'),
    ('fits.json','Selected complete source model','#087b78')]:
    rows=load(folder/filename)
    values=[next((v['frequency_hz'] for v in row['lines'] if v['eligible'] and abs(v['frequency_hz']-115.7)<2),np.nan) for row in rows]
    ax.plot(range(12),values,'o-',label=label,color=color)
ax.axhline(115.7,color='black',ls=':',lw=1)
ax.axvspan(8.5,11.5,color='#eadcce',alpha=.3)
ax.set(xticks=range(12),xlabel='All prerequisite windows',ylabel='Frequency (Hz)',ylim=(115.65,115.75),
    title='Weak-line prerequisite: all10 components x12 windows')
ax.legend(fontsize=8)
for ax in axes.flat:ax.grid(axis='y',alpha=.18)
fig.suptitle('Full-hypothesis prediction V1 — known-control criteria pass; conditioned candidates, no real-source claim',fontsize=13)
path=a.out/'known_comparison.png'
fig.savefig(path,dpi=140)
plt.close(fig)
dest=a.out/'exact_sources/tools/plot_candidate_prediction_v1.py'
dest.parent.mkdir(parents=True,exist_ok=True)
shutil.copy2(Path(__file__),dest)
save(a.out/'report.json',dict(result='all108_and26prediction_decisions_plotted',
    input_report_sha256=sha(a.input/'report.json'),audit_report_sha256=sha(a.audit/'report.json'),
    images={'known_comparison.png':sha(path)},conditioned_candidates_not_pristine_holdout=True))
print(path)
