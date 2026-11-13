"""Plot all coordinate lag curves and every long-run output block without selecting seeds."""
import argparse,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for name in ['workspace','input','audit','out']:p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from research_archive_v1 import load,save,sha
a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_plot.py')
report=load(a.input/'report.json');audit=load(a.audit/'report.json');assert audit['result']=='passed'
colors=['#242f37','#965821','#167577','#39938b','#75b2a7'];rows=audit['phase_observations']
rows=rows[-2:]+rows[:-2]
fig,axes=plt.subplots(2,2,figsize=(12,7),layout='constrained')
for row,color in zip(rows,colors):
    with np.load(a.audit/row['file']) as data:v=data['values'];c=data['curves']
    label=row['label'].replace('source_','F2 ')
    for j,name in enumerate(['psi','eta']):
        axes[0,j].plot(np.arange(min(len(v),2500))/1000,v[:2500,j]-v[:,j].mean(),color=color,alpha=.8,lw=1,label=label)
        axes[1,j].plot(np.arange(501),c[j,j]/c[j,j,0],color=color,lw=1.5,label=label)
        axes[0,j].set(title=name+' deviation: first 2.5s',xlabel='Time (s)',ylabel='Radians from own mean')
        axes[1,j].set(title=name+' autocorrelation: complete duration',xlabel='Lag (ms)',ylabel='Correlation')
for ax in axes.flat:ax.grid(alpha=.2)
axes[0,0].legend(fontsize=8);axes[1,0].legend(fontsize=8)
fig.suptitle('Source-derived statistical phase motion; source check remains imperfect')
fig.savefig(a.out/'phase_statistics.png',dpi=150);plt.close(fig)
fig,axes=plt.subplots(4,2,figsize=(12,10),layout='constrained');long=report['renders'][0]
colors=dict(static='#737d84',post='#b37b3f',relation_q='#819e78',relation_full='#176d78')
for j,band in enumerate(report['bands_hz']):
    ax=axes.flat[j]
    for method in report['methods']:
        values=[x for x in long['blocks'] if x['method']==method]
        ax.plot([x['start_seconds']+1.5 for x in values],10*np.log10([x['bandpower'][j] for x in values]),lw=1,color=colors[method],label=method)
    ax.set(title=f'{band[0]}–{band[1]} Hz',xlabel='Time (s)',ylabel='Band power (dBFS)');ax.grid(alpha=.2)
axes[0,0].legend(fontsize=8)
fig.suptitle('All 60 contiguous 3s windows, first seed, actual saved mixtures; no loudness matching')
fig.savefig(a.out/'longrun_bands.png',dpi=150);plt.close(fig)
r=dict(result='all_phase_lags_and_all60_longrun_blocks_plotted',input_report_sha256=sha(a.input/'report.json'),
  audit_sha256=sha(a.audit/'report.json'),images=[dict(file=f,sha256=sha(a.out/f)) for f in ['phase_statistics.png','longrun_bands.png']])
save(a.out/'report.json',r);print(r['result'])
