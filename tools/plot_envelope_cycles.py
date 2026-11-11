"""Compact publication-sized figure from saved analysis grids only."""
import json
from runtime_review import ROOT, sha
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT=ROOT/'references/analysis/envelope_cycles_detrended_v1'


def main():
    if (OUT/'verification.json').exists():raise SystemExit('Preserve frozen envelope review.')
    cases=[('phase_modulated_noise','AM noise · known signal'),
        ('first_upper_128ms_mean_power','A first descent · observed ridge'),
        ('mid_base_mix','C 4000 RPM · fixed bench')]
    fig,axes=plt.subplots(1,3,figsize=(13,4.8),constrained_layout=True)
    for ax,(name,title) in zip(axes,cases):
        data=np.load(OUT/f'{name}_grid.npz');power=data['power']
        shape=power/power.mean(axis=1,keepdims=True)-1
        first=max(0,len(shape)//2-10);selected=shape[first:first+20,:,0]
        z=np.fft.rfft(selected,axis=1);z[:,17:]=0
        view=np.fft.irfft(z,n=selected.shape[1],axis=1)
        image=ax.imshow(view,aspect='auto',origin='lower',extent=[0,1,first,first+len(view)],
            vmin=-1,vmax=2,cmap='magma')
        ax.set(title=title,xlabel='Supplied cycle phase',ylabel='Complete cycle index')
    fig.suptitle('3–8 kHz envelope shape · channel1 · 16 harmonics for display',fontsize=13)
    fig.colorbar(image,ax=axes,label='Relative band-power shape',shrink=.88)
    fig.text(.5,-.02,'Slow log-power trend removed; each cycle scaled by its own mean. Recording and bench conditions differ.',ha='center',fontsize=10)
    path=OUT/'envelope_cycles_checked.png';fig.savefig(path,dpi=160,bbox_inches='tight');plt.close(fig)
    report=dict(plot_sha256=sha(path),script_sha256=sha(__file__),primary_sha256=sha(OUT/'results.json'),
        inputs={f'{name}_grid.npz':sha(OUT/f'{name}_grid.npz') for name,_ in cases},
        scope='Replot saved analysis grids with compact labels. No reanalysis, matched conditions or physical source identification.')
    (OUT/'checked_plot.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
