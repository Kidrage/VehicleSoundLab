"""Read-only plot of the preserved false negative and complete model comparison."""
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
assert diag['audit_report_sha256']==sha(a.audit/'report.json')
assert audit['qualified'] is False and audit['remaining96_executed'] is False
fig,axes=plt.subplots(1,2,figsize=(13,5),layout='constrained')
ax=axes[0]
gains=audit['screen_gains']
for channel,label,offset in [(0,'Left',-.035),(1,'Right',.035)]:
    ax.plot([v['window']+offset for v in gains],[v['gain_LR'][channel] for v in gains],'o-',label=label,alpha=.8)
ax.axhline(.8,color='#a73838',ls='--',label='Declared acceptance: 0.8')
ax.annotate('True weak line rejected\n0.79253 < 0.8',xy=(11,gains[-1]['gain_LR'][0]),xytext=(10.25,.86),
    arrowprops={'arrowstyle':'->','color':'#a73838'},fontsize=9)
ax.set(xticks=[9,10,11],xlabel='Window (0.25 s)',ylabel='Conditional weighted residual reduction',
    title='Fixed native nonlinear basis: false negative',ylim=(.76,1.02))
ax.legend(loc='lower left',fontsize=8)
ax=axes[1]
for key,label,color in [('native_weighted_relative_LR','Native 9/10-line fit','#a56f4d'),
    ('screen_fixed_weighted_relative_LR','Native basis + forecast, linear re-fit','#4c85ad'),
    ('joint_weighted_relative_LR','Frozen full joint fit from previous experiment','#087b78')]:
    data=[max(v[key]) if v[key] is not None else np.nan for v in diag['windows']]
    ax.semilogy(range(12),data,'o-',label=label,color=color)
ax.axvspan(8.5,11.5,color='#eadcce',alpha=.3)
ax.set(xticks=range(12),xlabel='All 12 prerequisite windows',ylabel='Maximum LR weighted relative waveform residual',
    title='Fixing the native basis restricts the missing-mode test')
ax.legend(loc='center left',fontsize=8)
for ax in axes:ax.grid(axis='y',alpha=.2)
fig.suptitle('Candidate residual screen V1 — prerequisite FAILED; remaining 96 windows not executed',fontsize=12)
path=a.out/'false_negative.png'
fig.savefig(path,dpi=150)
plt.close(fig)
dest=a.out/'exact_sources/tools/plot_candidate_residual_v1.py'
dest.parent.mkdir(parents=True,exist_ok=True)
shutil.copy2(Path(__file__),dest)
save(a.out/'report.json',dict(result='all12_prerequisite_and3conditional_screen_comparison_plotted',
    input_report_sha256=sha(a.input/'report.json'),audit_report_sha256=sha(a.audit/'report.json'),
    diagnostic_report_sha256=sha(a.diagnostic/'report.json'),images={'false_negative.png':sha(path)}))
print(path)
