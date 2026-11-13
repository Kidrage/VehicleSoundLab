"""Every seed and condition, without choosing the best-looking realization."""
import argparse,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','render','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from research_archive_v1 import load,save,sha
a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_plot.py')
obs=load(a.input/'report.json');trial=load(a.render/'report.json');x=np.arange(4)
fig,axes=plt.subplots(1,2,figsize=(12,5),layout='constrained')
for name,label in [('train','F2 native6-9s train'),('check','F2 native9-12s check')]:
    axes[0].plot(x,obs[name]['excess'],'o-',lw=2,label=label)
for j,row in enumerate(obs['phase_controls']):axes[0].plot(x,row['statistics']['excess'],'x--',alpha=.6,label=f'Same-PSD phase {j+1}')
colors={0:'#64748b',.5:'#0d9488',1:'#c2410c'}
for row in trial['renders']:
    axes[0].plot(x,row['statistics']['excess'],'.:',color=colors[row['amount']],alpha=.55,
        label=f"Generated {row['amount']:.0%}" if row['seed']==149921 else None)
for seed in [149921,277139,381611]:
    rows=[r for r in trial['renders'] if r['seed']==seed];base=np.array(rows[0]['statistics']['variance'])
    for row in rows:
        axes[1].plot(x,10*np.log10(np.array(row['statistics']['variance'])/base),'.-',
            color=colors[row['amount']],alpha=.6,label=f"Generated {row['amount']:.0%}" if seed==149921 else None)
axes[0].set_ylabel('Finite band excess kurtosis');axes[1].set_ylabel('Finite band power vs same-seed static (dB)')
for ax in axes:
    ax.set_xticks(x,['1.2-2.2k','2.2-4k','4-8k','8-14k']);ax.grid(alpha=.2);ax.legend(fontsize=8)
fig.suptitle('Idle spectral excitation: new concentration, unchanged13OSC /6filters\nAll3seeds shown; adjacent same-recording statistics do not establish mechanical realism',fontsize=11)
fig.savefig(a.out/'excitation_moments.png',dpi=150);plt.close(fig)
save(a.out/'report.json',dict(result='plot_prepared',image_sha256=sha(a.out/'excitation_moments.png'),
    max_finite_band_power_delta_db=float(max(abs(10*np.log10(np.array(row['statistics']['variance'])/
        np.array(next(r for r in trial['renders'] if r['seed']==row['seed'] and r['amount']==0)['statistics']['variance']))).max() for row in trial['renders']))))
