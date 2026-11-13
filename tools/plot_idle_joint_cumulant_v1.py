"""All pairwise source/control/generated observations, no seed or block selection."""
import argparse, shutil, sys
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','audit','out']:
    p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args()
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from research_archive_v1 import load,save,sha

audit=load(a.audit/'report.json')
assert audit['result']=='all57_joint_observations_and_independent_architecture_verified'
assert audit['input_report_sha256']==sha(a.input/'report.json')
r=load(a.input/'report.json')
pairs=[row['bands'] for row in r['pairs']]
labels=['1.2-2.2k','2.2-4k','4-8k','8-14k']
x=np.arange(6)
a.out.mkdir(parents=True,exist_ok=False)
shutil.copy2(__file__,a.out/'executed_plot.py')
fig,axes=plt.subplots(2,1,figsize=(15,9),layout='constrained')
for ax,transform in zip(axes,['raw','local40ms']):
    for name,color in [('training','#182e39'),('check','#c26a27')]:
        row=next(v for v in r['observations'] if v['label']==name)
        ax.plot(x,[row[transform]['normalized'][b][c] for b,c in pairs],'-o',color=color,lw=2,label='F2 '+name)
    groups=[('phase',None,'#9ca3af','Same-PSD controls'),('sparse',0,'#64748b','Independent0%'),
        ('sparse',.5,'#0d9488','Independent50%'),('sparse',1,'#2563eb','Independent100%'),
        ('conditioned50',.5,'#a855f7','Previous conditional50%')]
    for family,amount,color,label in groups:
        rows=[v for v in r['observations'] if v['kind']==family and (amount is None or v['amount']==amount)]
        for j,row in enumerate(rows):
            offset=(j-(len(rows)-1)/2)*.011
            ax.scatter(x+offset,[row[transform]['normalized'][b][c] for b,c in pairs],s=14,
                marker='x' if family=='phase' else '.',alpha=.65,color=color,label=label if j==0 else None)
    if transform=='raw':
        ax.plot(x,[row['independent_full'] for row in r['pairs']],'--',color='#2563eb',lw=1.5,label='Independent100% stationary expectation + finite main')
    ax.axhline(0,color='black',lw=.7)
    ax.set_xticks(x,[labels[b]+' / '+labels[c] for b,c in pairs],rotation=12)
    ax.set(ylabel='Normalized mixed fourth cumulant',title='Raw bands' if transform=='raw' else 'After separate40ms per-band RMS normalization (diagnostic)')
    ax.grid(alpha=.2)
    ax.legend(fontsize=8,loc='center left',bbox_to_anchor=(1.01,.5))
fig.suptitle('Idle cross-band concentration: both source portions, all6phase controls, all48generated blocks\nFinite mixed-recording comparison; no mechanical-source, significance or listening acceptance',fontsize=11)
path=a.out/'idle_joint_all_pairs.png'
fig.savefig(path,dpi=150)
plt.close(fig)
save(a.out/'report.json',dict(result='all_pairs_and_all_conditions_plotted',image_sha256=sha(path),
    input_report_sha256=sha(a.input/'report.json'),audit_sha256=sha(a.audit/'report.json'),
    source_portions=2,phase_controls=6,generated_blocks=48))
