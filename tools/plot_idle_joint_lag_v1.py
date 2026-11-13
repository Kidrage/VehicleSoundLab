"""Complete fixed-grid source/control/current curves, without lag selection."""
import argparse,shutil,sys
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','audit','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from research_archive_v1 import load,save,sha

audit=load(a.audit/'report.json')
assert audit['result']=='all33_lag_observations_660curves_and_response_support_verified'
assert audit['input_report_sha256']==sha(a.input/'report.json')
r=load(a.input/'report.json');a.out.mkdir(parents=True,exist_ok=False)
shutil.copy2(__file__,a.out/'executed_plot.py')
data={}
for row in r['observations']:
    assert sha(a.input/row['file'])==row['sha256']
    with np.load(a.input/row['file']) as archive:data[row['label']]={key:archive[key] for key in archive.files}
with np.load(a.input/'expectation.npz') as archive:expectation={key:archive[key] for key in archive.files}
pairs=[(b,c) for b in range(4) for c in range(b,4)]
labels=['1.2-2.2k','2.2-4k','4-8k','8-14k'];images=[]
for transform,kind in [('raw','cross'),('local40ms','cross'),('raw','auto')]:
    selected=[j for j,(b,c) in enumerate(pairs) if (b==c)==(kind=='auto')]
    fig,axes=plt.subplots(2,2 if kind=='auto' else 3,figsize=(13,8),layout='constrained')
    for ax,j in zip(axes.flat,selected):
        for row in r['observations']:
            if row['kind']=='main':continue
            z=data[row['label']];label=None
            if row['kind']=='source':
                color='#182e39' if row['label']=='training' else '#c26a27';alpha=1.;width=1.8
                label='F2 '+row['label']
            elif row['kind']=='phase':
                color='#9ca3af';alpha=.5;width=.7
                if row['label']=='training_phase_149921':label='All6same-PSD phase controls'
            else:
                color='#64748b' if row['amount']==0 else '#0d9488';alpha=.28;width=.7
                if row['seed']==149921 and row['block']==0:label='All12current'+str(round(row['amount']*100))+'% blocks'
            ax.plot(z['lags']/48,z[transform+'_normalized'][j],color=color,alpha=alpha,lw=width,label=label,
                zorder=5 if row['kind']=='source' else 1)
        if transform=='raw':
            ax.plot(expectation['lags']/48,expectation['normalized'][j],'--',lw=1.2,color='#2563eb',label='Current100% expectation + finite main',zorder=4)
        b,c=pairs[j];ax.set(title=labels[b]+' / '+labels[c],xlabel='Lag (ms); second band later at positive lag',ylabel='Normalized fourth cumulant')
        ax.axhline(0,color='black',lw=.7);ax.axvline(0,color='black',lw=.5,alpha=.4);ax.grid(alpha=.2)
    handles,names=axes.flat[0].get_legend_handles_labels()
    fig.legend(handles,names,loc='outside lower center',ncol=3,fontsize=8)
    fig.suptitle('F2 idle '+kind+'-band time structure: '+('raw' if transform=='raw' else 'after40ms per-band RMS diagnostic')+
        '\nAll81declared lags / all2source portions /6phase controls /24generated blocks; no fitted delay or engine identity',fontsize=12)
    name=kind+'_'+transform+'.png';fig.savefig(a.out/name,dpi=150);plt.close(fig)
    images.append(dict(file=name,sha256=sha(a.out/name)))
save(a.out/'report.json',dict(result='all_declared_lag_curves_plotted',images=images,
    input_report_sha256=sha(a.input/'report.json'),audit_sha256=sha(a.audit/'report.json'),
    source_portions=2,phase_controls=6,generated_blocks=24))
