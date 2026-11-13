"""Read-only short-time concentration of all seeds, without retuning."""
import argparse,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','evidence','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from research_archive_v1 import load,save,sha
a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_plot.py')
observed=load(a.evidence/'observe1/report.json');audit=load(a.evidence/'audit1/report.json')
fig,axes=plt.subplots(1,2,figsize=(12,4.5),layout='constrained');x=np.arange(4);summary={}
for name,label,color,style in [('F2_train','Native6-9s','black','-'),('F2_check','Native9-12s','0.5','--')]:
    row=next(v for v in observed['observations'] if v['name']==name)['whole']
    kurt=row['moments']['excess_kurtosis'][2:];cv=row['energy']['480']['CV'][2:]
    axes[0].plot(x,kurt,style,color=color,label=label);axes[1].plot(x,cv,style,color=color,label=label)
    summary[name]=dict(excess_kurtosis=kurt,energy_CV_10ms=cv)
for amount,color in [(0,'C0'),(.5,'C2'),(1,'C1')]:
    rows=[row for row in audit['renders'] if row['amount']==amount]
    for axis,key in [(axes[0],'excess_kurtosis'),(axes[1],'energy_CV_10ms')]:
        values=np.array([[v[key] for v in row['concentration']] for row in rows])
        axis.plot(x,values.mean(axis=0),marker='o',color=color,label=f'Candidate{round(amount*100)}% (3seeds)')
        axis.fill_between(x,values.min(axis=0),values.max(axis=0),color=color,alpha=.13)
        summary.setdefault(str(amount),{})[key]=values.tolist()
for ax in axes:
    ax.set_xticks(x,['1.2-2.2k','2.2-4k','4-8k','8-14k']);ax.set_xlabel('Frequency band (Hz)');ax.legend(fontsize=8);ax.grid(alpha=.2)
axes[0].set_ylabel('Excess kurtosis');axes[1].set_ylabel('Nonoverlap10ms energy CV')
fig.suptitle('Fixed-idle fast detail: same core/spectrum/innovations; only fresh correlated gain changes\nFinite3s comparisons; concentration is a diagnostic, not mechanical identity or listening acceptance',fontsize=11)
fig.savefig(a.out/'idle_fast_detail.png',dpi=150);plt.close(fig)
save(a.out/'report.json',dict(result='read_only_concentration_plot_generated',summary=summary,
    audit_sha256=sha(a.evidence/'audit1/report.json'),observation_sha256=sha(a.evidence/'observe1/report.json'),image_sha256=sha(a.out/'idle_fast_detail.png')))
