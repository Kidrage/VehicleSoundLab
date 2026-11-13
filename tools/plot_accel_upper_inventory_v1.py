"""Every F3 window and both upper bands, with original reference-floor line."""
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
a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_plot.py')
audit=load(a.audit/'report.json');assert audit['result']=='all48_upper_cells_rejections_descriptors_verified'
assert audit['input_report_sha256']==sha(a.input/'report.json')
report=load(a.input/'report.json');fig,axes=plt.subplots(2,3,figsize=(15,8),layout='constrained')
for column,summary in enumerate(report['observations']):
    case=summary['segment'];rows=[load(a.input/case/f'tile_{i:02d}.json') for i in range(summary['windows'])]
    for b,(label,color) in enumerate([('4-8kHz','#0d9488'),('8-14kHz','#c26a27')]):
        axes[0,column].plot([row['bands'][b]['maximum_relative_to_old_db'] for row in rows],'o-',color=color,ms=3,label=label)
        axes[1,column].plot([row['bands'][b]['counts']['local_candidate'] for row in rows],'o-',color=color,ms=3,label=label+' local candidates')
    axes[0,column].axhline(-42,color='black',ls='--',lw=1,label='Original relative floor -42dB')
    axes[0,column].set(title=case,ylabel='Band maximum / original200-7000Hz maximum (dB)',ylim=(-90,-37))
    axes[1,column].plot([sum(row['bands'][b]['counts']['old_accepted'] for b in range(2)) for row in rows],'x--',color='#65758b',label='Original accepted upper peaks')
    axes[1,column].set(xlabel='Every original0.25s window',ylabel='Peak candidates; NOT identified sources',ylim=(-5,180))
for ax in axes.flat:ax.grid(alpha=.2);ax.legend(fontsize=8)
fig.suptitle('All48 F3 upper inventories: original global floor censors every upper raw peak\nBand-local reference restores candidates, including noise-like peaks; no source or sound promotion',fontsize=12)
image=a.out/'upper_floor_and_counts.png';fig.savefig(image,dpi=150);plt.close(fig)
save(a.out/'report.json',dict(result='all48_upper_floor_and_counts_plotted',input_report_sha256=sha(a.input/'report.json'),
    audit_sha256=sha(a.audit/'report.json'),image_sha256=sha(image)))
