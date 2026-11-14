"""Native F3 spectrum, band envelopes and stereo relation, with selected bounds visible."""
import argparse
import os
from pathlib import Path
import shutil
import sys
p=argparse.ArgumentParser(description=__doc__)
for key in ('workspace','study','audit','out'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'));os.environ['MPLBACKEND']='Agg'
import numpy as np
import matplotlib.pyplot as plt
from research_archive_v1 import load,save,sha
a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(Path(__file__),a.out/'plot_source.py')
report=load(a.study/'report.json');stats=report['source']['statistics'];audit=load(a.audit/'report.json')
with np.load(a.study/'source/arrays.npz') as f:data={k:f[k].copy() for k in f.files}
with np.load(a.audit/'source_direct_spectra.npz') as f:direct={k:f[k].copy() for k in f.files}
plan=load(repo/'research/F3_shift_transient_v1_plan.json');times=data['seconds']
labels=[f'{lo:g}-{hi:g}' for lo,hi in plan['bands_hz']]
fig,axes=plt.subplots(5,1,figsize=(14,13),sharex=True,layout='constrained',
    gridspec_kw={'height_ratios':[2.2,1.4,1.8,1.8,1.8]})
selected=(direct['hz']>=100)&(direct['hz']<=1200)
power=10*np.log10(np.maximum(direct['density'][:,selected].mean(axis=2),1e-14))
im=axes[0].pcolormesh(times,direct['hz'][selected],power.T,shading='nearest',cmap='magma',vmin=-65,vmax=-15)
axes[0].set(ylabel='Hz',title='Unchanged native sample spectrum (40ms Hann,5ms hop)')
fig.colorbar(im,ax=axes[0],pad=.01,label='Per-bin power (dBFS)')
axes[1].plot(times,data['primary_curve_dB'],lw=1.2,color='#246b95',label='Median300-8000Hz band change')
axes[1].axhline(-3,color='gray',ls='--',lw=1,label='Original descriptive -3dB condition')
axes[1].scatter([stats['dip_center_seconds'],stats['recovery_center_seconds']],
    [stats['dip_relative_db'],stats['recovery_relative_db']],color=['#c44235','#d48715'],zorder=5)
axes[1].set(ylabel='dB vs baseline',title='Selected dip200.990s; recovery201.340s reaches allowed endpoint')
axes[1].legend(fontsize=8,loc='lower left')
for ax,values,title,cmap,vmin,vmax,label in [
    (axes[2],data['relative_band_dB'],'Each native band changes separately','RdBu_r',-8,8,'dB vs baseline'),
    (axes[3],data['RL_dB'],'Original right / left level; no widening','RdBu_r',-8,8,'R / L (dB)'),
    (axes[4],abs(data['correlation']),'Magnitude of band-integrated complex correlation; not frequency MSC','viridis',0,1,'|integrated rho|')]:
    im=ax.pcolormesh(times,np.arange(9),values.T,shading='nearest',cmap=cmap,vmin=vmin,vmax=vmax)
    ax.set_yticks(range(9),labels,fontsize=8);ax.set(ylabel='Native band (Hz)',title=title)
    fig.colorbar(im,ax=ax,pad=.01,label=label)
for ax in axes:
    ax.axvspan(200.5,200.75,color='#38a36a',alpha=.13)
    ax.axvspan(199.8,200.3,color='#3278b7',alpha=.05)
    ax.axvline(stats['dip_center_seconds'],color='#c44235',ls=':',lw=.8)
    ax.axvline(stats['recovery_center_seconds'],color='#d48715',ls=':',lw=.8)
    ax.set_xlim(199.5,201.5)
axes[-1].set_xlabel('Source seconds; green = sampled6-to7DISPLAY bracket, not acoustic trigger timing')
fig.suptitle('F3 transient evidence: selected minima are boundary limited; no engine-event envelope qualified',fontsize=13)
fig.savefig(a.out/'source_transient.png',dpi=150);plt.close(fig)
save(a.out/'report.json',dict(result='all_source_transient_and_stereo_diagnostics_plotted',
    producer_report_sha256=sha(a.study/'report.json'),audit_report_sha256=sha(a.audit/'report.json'),
    image_sha256=sha(a.out/'source_transient.png'),
    original_preview_sha256=sha(a.study/'source_original.wav'),
    native_frames=96000,source_seconds=[199.5,201.5],
    dip_recovery=stats,endpoint_diagnostics=audit['source']['endpoint_distances_seconds'],
    display_timing_calibrated=False,event_envelope_qualified=False))
print(a.out/'source_transient.png')
