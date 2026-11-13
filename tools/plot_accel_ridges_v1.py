"""Read-only native spectral peaks and conservative guided-match results."""
import argparse,sys,shutil
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--observation',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from research_archive_v1 import load,save,sha
a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_plot.py')
plan=load(a.observation/'exact_sources/research/accel_ridges_v1_plan.json')
fig,axes=plt.subplots(2,3,figsize=(14,8),layout='constrained')
summary=[]
for col,name in enumerate(plan['segments']):
    row=load(a.observation/(name+'.json'));audio=np.load(a.observation/(name+'.npz'))['audio'];e=row['evidence']
    n=plan['tile_frames'];win=np.hanning(n+1)[:-1];centers=(np.arange(len(row['inventories']))+.5)*.25
    z=np.array([np.fft.rfft(audio[i:i+n]*win[:,None],axis=0) for i in range(0,len(audio),n)])
    hz=np.fft.rfftfreq(n,1/48000);power=(abs(z)**2).mean(axis=2)*2/(n*np.sum(win*win))
    mask=(hz>=250)&(hz<=6000)
    axes[0,col].pcolormesh(centers,hz[mask],10*np.log10(np.maximum(power[:,mask].T,1e-15)),shading='nearest',vmin=-90,vmax=-25,cmap='magma')
    for i,inv in enumerate(row['inventories']):axes[0,col].scatter([centers[i]]*len(inv['hz']),inv['hz'],s=4,c='lightgrey',alpha=.6)
    for k,cl in enumerate(e['classes']):
        if cl['classification']=='uncertain':continue
        indices=cl['hypothesis_unique_tiles'][cl['classification']]
        f=[row['inventories'][i]['hz'][e['rows'][i][cl['classification']]['chosen'][k]] for i in indices]
        axes[0,col].plot(centers[indices],f,lw=1.2,c='cyan' if cl['classification']=='moving' else 'lime')
    axes[0,col].set(yscale='log',ylim=(250,6000),xlabel='Local time (s)',ylabel='Native frequency (Hz)',title=name)
    refs=[cl['reference_hz'] for cl in e['classes']]
    for hypothesis,color,marker in [('moving','C0','o'),('fixed','C1','x')]:
        axes[1,col].scatter(refs,[cl['support_fraction'][hypothesis] for cl in e['classes']],s=25,c=color,marker=marker,label=hypothesis+' query')
    axes[1,col].axhline(.8,c='.5',ls=':',lw=1);axes[1,col].axhline(.2,c='.7',ls=':',lw=1)
    axes[1,col].set(xlabel='First-tile peak frequency (Hz)',ylabel='Unique-match fraction of eligible tiles',ylim=(-.04,1.05),xlim=(250,5000))
    axes[1,col].legend(fontsize=8)
    summary.append(dict(segment=name,counts=e['counts'],raw_moving80=sum(cl['support_fraction']['moving']>=.8 for cl in e['classes']),
        raw_fixed80=sum(cl['support_fraction']['fixed']>=.8 for cl in e['classes']),
        reference_above2k=sum(f>=2000 for f in refs)))
fig.suptitle('F3 guided spectral peaks: grey inventory / cyan conservative moving matches\nDense moving comb also gives competing fixed queries: classifications do not identify physical sources',fontsize=12)
fig.savefig(a.out/'F3_guided_peaks.png',dpi=150);plt.close(fig)
save(a.out/'report.json',dict(result='read_only_plot_generated',observation_sha256=sha(a.observation/'report.json'),
    summary=summary,plot_sha256=sha(a.out/'F3_guided_peaks.png'),listening_or_source_identity=False))
print(summary,flush=True)
