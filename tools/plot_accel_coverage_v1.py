"""All native coverage and first-window spectra, without source compensation."""
import argparse,shutil,sys
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
r=load(a.input/'report.json');fig,axes=plt.subplots(2,3,figsize=(15,8),layout='constrained')
labels=['30-150','150-300','300-1k','1-2.2k','2.2-4k','4-8k','8-14k'];x=np.arange(7)
for col,row in enumerate(r['observations']):
    name=row['segment'];all=row['aggregate']['all_parts'];eligible=row['aggregate']['eligible_parts']
    ax=axes[0,col];ax.bar(x,np.array(all['source_fraction'])[:,0]*100,label='Source power fraction / L',color='0.75')
    ax.plot(x,np.array(all['model_over_source'])[:,0]*100,'o-',label='All model / source',color='C0')
    ax.plot(x,np.array(eligible['model_over_source'])[:,0]*100,'o-',label='Eligible model / source',color='C1')
    ax.set_title(name+' / all original windows');ax.set_xticks(x,labels,rotation=35,ha='right',fontsize=8)
    ax.set_ylabel('Percent (ratios are not explained power)');ax.legend(fontsize=7);ax.grid(alpha=.2)
    saved=np.load(a.input/name/'tile_00.npz');w=.5-.5*np.cos(2*np.pi*np.arange(12000)/12000);hz=np.fft.rfftfreq(12000,1/48000)
    ax=axes[1,col]
    for key,label in [('audio','Native source'),('all_model','All fitted lines'),('eligible_model','Eligible only')]:
        z=np.fft.rfft(saved[key][:,0]*w);power=abs(z)**2/(12000*np.sum(w*w))
        ax.semilogx(hz[1:],10*np.log10(np.maximum(power[1:],1e-25)),label=label,lw=.8)
    ax.set_xlim(30,14000);ax.set_ylim(-160,-10);ax.set_title('Original first tile / no chirplet applied')
    ax.set_xlabel('Native frequency (Hz)');ax.set_ylabel('Windowed cell power (dBFS)');ax.legend(fontsize=7);ax.grid(alpha=.2)
fig.suptitle('F3 native line coverage: the partial model misses core bands as well as LF/HF\nSigned interference is retained in reports; residual is not identified physical noise or rumble',fontsize=12)
fig.savefig(a.out/'coverage.png',dpi=150);plt.close(fig)
save(a.out/'report.json',dict(result='coverage_and_first_native_spectra_plotted',
    input_report_sha256=sha(a.input/'report.json'),image_sha256=sha(a.out/'coverage.png'),source_compensation=False))
