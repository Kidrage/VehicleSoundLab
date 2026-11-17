"""Count-aware local-observer presentation; no new source fit or estimator."""
import argparse
import csv
from pathlib import Path
import shutil

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from research_archive_v1 import load,save,sha


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=False)
    shutil.copy2(__file__,out/Path(__file__).name)
    root=Path('E:/VehicleSoundLab/references/analysis/event_local_structure_v1')
    known=load(root/'known1/report.json');real=load(root/'source1/report.json');audit=load(root/'audit1/report.json')
    assert known['result']==real['result']==audit['result']=='passed'
    lookup={}
    for case in real['cases']:
        for entry in case['observations']:
            frames,policy=entry['id'].split('-')
            lookup[case['id'],int(frames),policy]=entry['summaries']
    for row in known['observations']:
        policy='nonoverlap' if row['hop_frames']==row['window_frames'] else 'overlap'
        lookup[row['fixture'],row['window_frames'],policy]=row['summaries']
    names=['off_grid_tones','independent_white_noise','stochastic_resonance','crank','catch']
    labels=['Known tones','White noise','Narrow noise','A early','A later']
    fig,axes=plt.subplots(2,2,figsize=(12,8),layout='constrained')
    for col,n in enumerate((768,1536)):
        for row,band in enumerate((1,3)):
            ax=axes[row,col]
            for policy,offset,color,label in [('overlap',-.18,'#a76439','75% overlap'),('nonoverlap',.18,'#2b7e9a','No overlap')]:
                values=[];counts=[]
                for name in names:
                    summary=lookup[name,n,policy][band]
                    v=summary['phase_resultant_magnitude_LR']
                    values.append(float(np.mean(v)) if v is not None else np.nan)
                    counts.append(summary['phase_links'])
                bars=ax.bar(np.arange(len(names))+offset,values,.34,label=label,color=color)
                for bar,count in zip(bars,counts):
                    if np.isfinite(bar.get_height()):ax.text(bar.get_x()+bar.get_width()/2,bar.get_height()+.015,'n='+str(count),ha='center',fontsize=7,rotation=60)
            ax.set_xticks(np.arange(len(names)),labels,rotation=14);ax.set_ylim(0,1.22)
            ax.set_title(str(n/48)+'ms / '+str([(60,300),(300,1200),(1200,4500),(4500,14000)][band])+' Hz')
            ax.set_ylabel('Selected-link phase resultant')
    fig.suptitle('Counts shown; selected links, overlap and finite samples prevent physical identity inference',fontsize=11)
    handles,legend_labels=axes[0,0].get_legend_handles_labels()
    fig.legend(handles,legend_labels,loc='lower center',bbox_to_anchor=(.5,-.035),ncol=2,fontsize=10)
    fig.savefig(out/'phase-memory-counted.png',dpi=160,bbox_inches='tight');plt.close(fig)
    flat=[]
    for (name,n,policy),bands in lookup.items():
        for b in bands:
            phase=b['phase_resultant_magnitude_LR']
            flat.append(dict(source=name,window_ms=n/48,hop_policy=policy,
                band_low_hz=b['band_hz'][0],band_high_hz=b['band_hz'][1],
                observed_peaks=b['observed_peaks'],unique_links=b['unique_links'],
                absent_links=b['absent_links'],ambiguous_links=b['ambiguous_links'],phase_links=b['phase_links'],
                mean_phase_resultant=None if phase is None else float(np.mean(phase)),
                median_width_native_bins=b['median_half_power_width_native_bins']))
    with (out/'measurements.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(flat[0]));writer.writeheader();writer.writerows(flat)
    primary=[]
    for name in names:
        for n in (768,1536):
            b=lookup[name,n,'nonoverlap'][1]
            primary.append(dict(source=name,window_frames=n,band_hz=b['band_hz'],
                phase_links=b['phase_links'],phase_resultant_LR=b['phase_resultant_magnitude_LR'],
                median_width_native_bins=b['median_half_power_width_native_bins']))
    sparse=[]
    for case in real['cases']:
        for entry in case['observations']:
            for b in entry['summaries']:
                if b['phase_links']<=2:
                    sparse.append(dict(source=case['id'],observation=entry['id'],band_hz=b['band_hz'],
                        phase_links=b['phase_links'],descriptive_resultant_LR=b['phase_resultant_magnitude_LR']))
    save(out/'report.json',dict(result='passed',source_reports={str(root/name/'report.json'):sha(root/name/'report.json') for name in ['known1','source1','audit1']},
        displayed_primary=primary,sparse_or_absent_phase_observations=sparse,
        no_estimator_gate_or_source_change=True,
        limitation='A one-link resultant is identically1; high resultants at long windows with zero/one/two selected links do not demonstrate physical or long-term phase memory. Counts retained, not masked into a pass.',
        goal_complete=False,timbre_accepted=False))
    print('counted phase comparison and complete CSV written; sparse observations retained',flush=True)


if __name__=='__main__':main()
