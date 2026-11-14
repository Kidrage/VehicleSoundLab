"""Plot all fixed seeds/routes and the frozen F3 map; no audio or new fitting."""
import argparse
import os
from pathlib import Path
import shutil
import sys
p=argparse.ArgumentParser(description=__doc__)
for key in ('workspace','study','out'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
os.environ['MPLBACKEND']='Agg'
import numpy as np
import matplotlib.pyplot as plt
from research_archive_v1 import load,save,sha
a.out.mkdir(parents=True,exist_ok=False)
shutil.copy2(Path(__file__),a.out/'plot_source.py')
report=load(a.study/'report.json');plan=load(repo/'research/F3_warp_noise_v1_plan.json')
source_path=a.workspace/'references/analysis/F3_detail_v1/observe1/report.json'
source=load(source_path)
with np.load(a.study/'coordinates.npz') as f:actual=f['actual'].copy();affine=f['affine'].copy()
frequency=1/(1024*np.diff(actual));affine_hz=1/(1024*(affine[-1]-affine[0])/(len(affine)-1))
fold=(np.diff(actual,append=actual[-1]+actual[-1]-actual[-2])).reshape(14,1024)
fold_hz=1/(1024*np.mean(fold,axis=0))
fig,ax=plt.subplots(3,1,figsize=(14,11),gridspec_kw={'height_ratios':[1,1,3]},layout='constrained')
ax[0].plot((np.arange(len(frequency))+.5)/1024,frequency,lw=1,label='Actual frozen inverse-map rate')
ax[0].axhline(affine_hz,color='gray',ls='--',label='Same endpoints, affine rate')
ax[0].set(xlabel='Canonical acoustic cycles',ylabel='Acoustic root (Hz)',title='Frozen F3 map: small rate changes, not calibrated engine RPM')
ax[0].legend(loc='upper left',fontsize=9)
ax[1].plot(np.arange(1024)/1024,100*(fold_hz/affine_hz-1),color='#287f62')
ax[1].axhline(0,color='gray',ls='--')
ax[1].set(xlabel='Cycle phase',ylabel='Rate vs affine (%)',title='Fourteen-cycle folded rate; descriptive, last step linearly extended for this plot only')
rows=[];labels=[]
for route in plan['routes']:
    for seed in plan['noise_seeds']:
        row=next(v for v in report['cases'] if v['route']==route and v['seed']==seed)
        rows.append([b['familywise_p'] for b in row['dependence']['bands']])
        short={'direct_canonical':'Unmapped','same_endpoints_affine_map':'Affine',
            'actual_frozen_map':'Actual map','known_AM_actual_frozen_map':'Known AM + map'}[route]
        labels.append(f'{short} / {seed}')
rows.append([b['familywise_p'] for b in source['source_dependence']['bands']]);labels.append('Original F3 residual (prior observation)')
values=-np.log10(rows)
im=ax[2].imshow(values,aspect='auto',vmin=0,vmax=np.log10(257),cmap='viridis')
bands=[b['band_hz'] for b in source['source_dependence']['bands']]
ax[2].set_xticks(range(10),[f'{lo/1000:g}-{hi/1000:g}' for lo,hi in bands],rotation=30)
ax[2].set_yticks(range(len(labels)),labels,fontsize=8)
ax[2].set(xlabel='Native acoustic band (kHz)',title='All retained descriptive phase-shift p values; original condition p <= .01')
for y,row in enumerate(rows):
    for x,value in enumerate(row):
        if value<=.01:ax[2].text(x,y,'*',ha='center',va='center',color='white',fontsize=12)
for y in (3.5,7.5,11.5,15.5):ax[2].axhline(y,color='white',lw=.8)
bar=fig.colorbar(im,ax=ax[2],shrink=.8,pad=.01);bar.set_label('-log10(p); * marks original descriptive condition')
fig.suptitle('Stationary noise through frozen F3 coordinates: four paired seeds, no route selection',fontsize=13)
fig.savefig(a.out/'all_controls.png',dpi=150);plt.close(fig)
save(a.out/'report.json',dict(result='all_fixed_controls_plotted',
    producer_report_sha256=sha(a.study/'report.json'),source_prior_report_sha256=sha(source_path),
    plot_sha256=sha(a.out/'all_controls.png'),map_rate_hz=[float(frequency.min()),float(frequency.max())],
    affine_rate_hz=float(affine_hz),folded_rate_relative_percent=[float(min(100*(fold_hz/affine_hz-1))),float(max(100*(fold_hz/affine_hz-1)))],
    caution='Conditional fixed-map noise transfer only; no phase re-estimation, mechanical source qualification or timbre acceptance.'))
print(a.out/'all_controls.png')
