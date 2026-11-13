"""Read-only source/model comparison, without normalization or new fitting."""
import argparse,json,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--input',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from drive_evidence_v1.sources import sha

a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_plot.py')
audit=json.loads((a.input/'audit1/report.json').read_text(encoding='utf-8'))
assert audit['result']=='generic_F2_identity_verified_A_portability_not_qualified'
fig,axes=plt.subplots(3,1,figsize=(11,10),constrained_layout=True)
for ax,identity,label in zip(axes[:2],['F2_tailpipe','A_exterior_low_rev'],['F2 fixed-idle candidate','A low-rev portability attempt (not qualified)']):
    folder=a.input/'trial1'/identity
    original,rate=sf.read(folder/'training.wav',always_2d=True)
    generated,_=sf.read(folder/'fine_149921.wav',always_2d=True)
    for x,title,color in [(original,'Native training recording','#253e56'),(generated,'One generic source kernel, seed149921','#db7744')]:
        hz,power=signal.welch(x[:,0],fs=rate,nperseg=24000,noverlap=12000,detrend=False)
        keep=(hz>=30)&(hz<=1200)
        ax.plot(hz[keep],10*np.log10(np.maximum(power[keep],1e-30)),label=title,color=color,lw=1)
    model=json.loads((folder/'profile.json').read_text(encoding='utf-8'))
    for f in model['modal']['frequencies_hz']:ax.axvline(f,ymin=0,ymax=.05,color='#253e56',lw=1)
    ax.set(title=label,xlabel='Native frequency (Hz)',ylabel='Left PSD (dBFS/Hz)',xlim=(30,1200),ylim=(-105,-10))
    ax.grid(alpha=.2);ax.legend(fontsize=9,loc='upper right')
row=next(x for x in audit['contexts'] if x['id']=='A_exterior_low_rev')
for k,frequencies in enumerate(row['low_window_inventories_hz']):
    axes[2].scatter(frequencies,[208+(k*12000+12000)/48000]*len(frequencies),s=17,color='#253e56')
axes[2].set(title='A: every observed 30-120Hz peak in the fixed windows (no forced matching)',
    xlabel='Native frequency (Hz)',ylabel='Window centre (source seconds)',xlim=(30,120))
axes[2].grid(alpha=.2)
path=a.out/'source_profiles.png';fig.savefig(path,dpi=140);plt.close(fig)
report=dict(result='saved_reports_plotted_no_new_fit',file=path.name,sha256=sha(path),
    limits='Source mixtures and a single declared seed, not physical source separation, inferred RPM or listening acceptance.')
(a.out/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(report))
