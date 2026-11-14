"""Plot all fits and generated spectra; no cherry-picked seed or retuning."""
import argparse
import shutil
import sys
from pathlib import Path
p = argparse.ArgumentParser(description=__doc__)
for key in ['workspace','fit','review','out']:
    p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args()
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from research_archive_v1 import load,save,sha

a.out.mkdir(parents=True,exist_ok=False)
shutil.copy2(__file__,a.out/'executed_plot.py')
fit=load(a.fit/'report.json')
data=load(a.review/'actual_spectra.json')
fig,axes=plt.subplots(2,1,figsize=(11,8.5),layout='constrained')
labels=['F2 recording','same-PSD 149921','same-PSD 277139','same-PSD 381611']
x=np.arange(4)
axes[0].bar(x-.18,[r['check']['independent_relative_distance'] for r in fit['observations']],.36,label='Own-carrier blocks')
axes[0].bar(x+.18,[r['check']['joint_relative_distance'] for r in fit['observations']],.36,label='Full joint moment')
axes[0].set(xticks=x,xticklabels=labels,ylabel='CHECK moment distance (lower is closer)',
            title='Complete joint fit does not transfer; same-PSD controls show similar behavior')
axes[0].legend()
frequency=np.array(data['frequency_hz'])
for name,color in [('old','#89959b'),('independent','#377fba'),('joint','#c57336')]:
    p=np.array([data['spectra'][f'{name}_{seed}_mix'] for seed in [149921,277139,381611]])
    axes[1].plot(frequency,10*np.log10(p.mean(axis=0)+1e-30),label=name,color=color)
    axes[1].fill_between(frequency,10*np.log10(p.min(axis=0)+1e-30),10*np.log10(p.max(axis=0)+1e-30),color=color,alpha=.12)
source=(np.array(data['spectra']['reference_train'])+data['spectra']['reference_check'])/2
axes[1].plot(frequency,10*np.log10(source+1e-30),color='#315142',label='Original F2 (two portions)',alpha=.9)
axes[1].set(xscale='log',xlim=(30,16000),ylim=(-125,-20),xlabel='Frequency (Hz)',ylabel='PSD (dB FS²/Hz)',
            title='Actual outputs: mean and full range of all three seeds; common gain')
axes[1].legend(ncol=2);axes[1].grid(alpha=.2)
path=a.out/'idle_joint_osc_v1.png';fig.savefig(path,dpi=145);plt.close(fig)
save(a.out/'report.json',dict(result='published',fit_sha256=sha(a.fit/'report.json'),
     spectra_sha256=sha(a.review/'actual_spectra.json'),file=path.name,sha256=sha(path)))
print(path)
