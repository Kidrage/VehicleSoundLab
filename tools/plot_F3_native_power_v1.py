"""Display every native-time control, including the missed known AM control."""
import argparse
import os
from pathlib import Path
import shutil
import sys
p=argparse.ArgumentParser(description=__doc__)
for key in ('workspace','study','out'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'));os.environ['MPLBACKEND']='Agg'
import numpy as np
import matplotlib.pyplot as plt
from research_archive_v1 import load,save,sha
a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(Path(__file__),a.out/'plot_source.py')
report=load(a.study/'report.json');source=report['source']['result']
cases=list(report['known_before_frozen_map']['controls'].values())+report['controls']+[report['source']]
labels=[v['name'].replace('_',' ') for v in cases]
bands=[v['band_hz'] for v in source['residual']['bands']]
fig=plt.figure(figsize=(14,10),layout='constrained');grid=fig.add_gridspec(2,2,height_ratios=[2.1,1])
axes=[fig.add_subplot(grid[0,0]),fig.add_subplot(grid[0,1])]
for ax,route,title in zip(axes,['full','residual'],['Native full-band power (diagnostic)','Native residual power (PRIMARY)']):
    probabilities=np.array([[b['familywise_p'] for b in row['result'][route]['bands']] for row in cases])
    im=ax.imshow(-np.log10(probabilities),aspect='auto',vmin=0,vmax=np.log10(257),cmap='viridis')
    ax.set_xticks(range(10),[f'{lo/1000:g}-{hi/1000:g}' for lo,hi in bands],rotation=35)
    ax.set_yticks(range(len(cases)),labels,fontsize=8)
    ax.set(xlabel='Native frequency band (kHz)',title=title)
    for i,row in enumerate(probabilities):
        for j,pvalue in enumerate(row):
            if pvalue<=.01:ax.text(j,i,'*',color='white',ha='center',va='center',fontsize=13)
    for i in (1.5,3.5,5.5,7.5,9.5):ax.axhline(i,color='white',lw=.7)
bar=fig.colorbar(im,ax=axes,shrink=.85,pad=.02);bar.set_label('-log10(descriptive p); * = original .01 condition')
ax=fig.add_subplot(grid[1,:]);d=source['decomposition']
coherent=np.array(d['coherent_power']).mean(axis=1);residual=np.array(d['residual_power']).mean(axis=1)
fraction=coherent/(coherent+residual);x=np.arange(10)
ax.bar(x,100*fraction,label='Periodic native projection',color='#457b9d')
ax.bar(x,100*(1-fraction),bottom=100*fraction,label='Remaining native samples',color='#e9c46a')
ax.set_xticks(x,[f'{lo/1000:g}-{hi/1000:g}' for lo,hi in bands])
ax.set(xlabel='Native frequency band (kHz)',ylabel='Power share (%)',ylim=(0,100),
    title='Source: orthogonal sample projection over ALL13cycles, not physical source separation')
ax.legend(loc='upper right',fontsize=9)
fig.suptitle('F3 native-time check: 13 complete cycles; nine interior cycles (5 / 4)\nKnown AM61927 is missed in primary analysis; no qualified cyclic modulation law',fontsize=13)
fig.savefig(a.out/'native_results.png',dpi=150);plt.close(fig)
save(a.out/'report.json',dict(result='all_native_results_plotted',
    producer_report_sha256=sha(a.study/'report.json'),plot_sha256=sha(a.out/'native_results.png'),
    cases=len(cases),routes=2,source_residual_high_p=[v['familywise_p'] for v in source['residual']['bands'][-2:]],
    missed_known_AM_seeds=[61927],primary_qualified=False))
print(a.out/'native_results.png')
