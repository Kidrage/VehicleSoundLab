"""Training/check and all phase controls; visualize the new amplitude-only law."""
import argparse,sys,shutil
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from research_archive_v1 import load,save,sha
a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_plot.py')
r=load(a.input/'report.json');b=np.asarray(r['model']['coefficients']);freq=np.array(r['frequencies_hz'])
fig,axes=plt.subplots(1,2,figsize=(12,4.8),layout='constrained');x=np.arange(4)
axes[0].plot(x,100*np.array(r['real']['train']['relative_mse_improvement']),'o-',label='Native6-9s / train')
axes[0].plot(x,100*np.array(r['real']['check']['relative_mse_improvement']),'o-',label='Native9-12s / same-recording check')
for j,row in enumerate(r['phase_controls']):
    axes[0].plot(x,100*np.array(row['check']['relative_mse_improvement']),'x--',alpha=.65,label=f'Same-PSD phase control {j+1}')
axes[0].axhline(0,color='0.5',lw=.7);axes[0].set_xticks(x,['1.2-2.2k','2.2-4k','4-8k','8-14k'])
axes[0].set_ylabel('Check MSE reduction against training constant (%)');axes[0].legend(fontsize=8)
t=np.arange(4800)/48000;phase=np.array([-.3,.4,1.1])
z=np.exp(1j*(2*np.pi*t[:,None]*freq+phase))
law=1+sum(z[:,k].real[:,None]*b[k+1]+z[:,k].imag[:,None]*b[k+4] for k in range(3))/b[0]
for j,label in enumerate(['1.2-2.2k','2.2-4k','4-8k','8-14k']):axes[1].plot(t*1000,np.sqrt(law[:,j]),label=label)
axes[1].set_xlabel('Newly synthesized time (ms)');axes[1].set_ylabel('Detail amplitude gain (100%)');axes[1].legend(fontsize=8)
for ax in axes:ax.grid(alpha=.2)
fig.suptitle('Independent acoustic modes -> learned high-band POWER law\nAmplitude-only proxy; finite same-recording transfer is not mechanical identity or listening acceptance',fontsize=11)
fig.savefig(a.out/'conditional_idle.png',dpi=150);plt.close(fig)
save(a.out/'report.json',dict(result='plot_prepared',input_sha256=sha(a.input/'report.json'),image_sha256=sha(a.out/'conditional_idle.png')))
