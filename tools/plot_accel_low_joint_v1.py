"""Show every native fit failure and low track; no source labels or refits."""
import argparse
import shutil
import sys
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','out']:
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
roots=[a.workspace/'references/analysis/accel_low_fit_v1',a.workspace/'references/analysis/accel_low_profiled_v1']
folders=[roots[0]/'observe2',roots[1]/'observe1']
audits=[load(root/'audit1/report.json') for root in roots]
reports=[load(folder/'report.json') for folder in folders]
assert audits[0]['result']=='all_known_and48_native_waves_initials_tracks_phase_reports_predictions_verified'
assert audits[1]['result']=='all_profiled_controls_left_LS_reduced_gradient_64native_waves_tracks_predictions_verified'
for folder,audit in zip(folders,audits):
    assert sha(folder/'report.json')==audit['input_report_sha256']
names=reports[0]['plan']['segments']
labels=['Full nonlinear fit','Exact profiled fit']
fig,axes=plt.subplots(3,3,figsize=(15,10),layout='constrained')
summaries=[]
for col,name in enumerate(names):
    pairs=[load(folder/name/'fits.json') for folder in folders]
    t=(np.arange(len(pairs[0]))+.5)*.25
    ax=axes[0,col]
    for method,rows in enumerate(pairs):
        for channel,style in [(0,'-'),(1,'--')]:
            y=[v['weighted_relative_residual_LR'][channel] for v in rows]
            ax.plot(t,y,style,color='C'+str(method),lw=1,label=labels[method]+(' L' if channel==0 else ' R'))
        failed=np.array([not v['success'] for v in rows])
        ax.scatter(t[failed],np.array([v['weighted_relative_residual_LR'][0] for v in rows])[failed],
                   marker='x',s=34,color='C'+str(method))
    ax.set_title(name+' / weighted waveform residual')
    ax.set_ylabel('Relative residual norm')
    ax.legend(fontsize=6)
    ax.grid(alpha=.2)
    ax=axes[1,col]
    for method,rows in enumerate(pairs):
        ax.plot(t,[v['cost'] for v in rows],'.-',lw=1,color='C'+str(method),label=labels[method])
        failed=np.array([not v['success'] for v in rows])
        ax.scatter(t[failed],np.array([v['cost'] for v in rows])[failed],marker='x',s=40,color='C'+str(method))
    ax.set_yscale('log')
    ax.set_ylabel('Left weighted LS cost')
    ax.legend(fontsize=7)
    ax.grid(alpha=.2)
    ax=axes[2,col]
    for method,rows in enumerate(pairs):
        count=[sum(v['eligible'] for v in row['lines']) for row in rows]
        ax.plot(t,count,'.-',color='C'+str(method),label=labels[method])
    ax.set_xlabel('Passage time (s)')
    ax.set_ylabel('Eligible lines / whole inventory')
    ax.grid(alpha=.2)
    summaries.append(dict(segment=name,methods=[dict(label=label,successful=sum(v['success'] for v in rows),
        failed=[i for i,v in enumerate(rows) if not v['success']],
        eligible_lines=sum(v['eligible'] for row in rows for v in row['lines'])) for label,rows in zip(labels,pairs)]))
fig.suptitle('All 48 native windows, unchanged model / bounds / 60-evaluation budget\nCrosses show ALL failed windows; lower cost or solver success does not establish engine sound',fontsize=12)
fig.savefig(a.out/'fit_status.png',dpi=140)
plt.close(fig)

fig,axes=plt.subplots(2,3,figsize=(15,7.5),layout='constrained')
phase_reports=[]
for col,name in enumerate(names):
    for method,(folder,label) in enumerate(zip(folders,labels)):
        rows=load(folder/name/'fits.json')
        linked=load(folder/name/'temporal.json')
        ax=axes[method,col]
        for i,row in enumerate(rows):
            if not row['success']:
                ax.axvspan(i*.25,(i+1)*.25,color='red',alpha=.09)
            points=[v for v in row['lines'] if 20<=v['frequency_hz']<=260]
            eligible=[v for v in points if v['eligible']]
            other=[v for v in points if not v['eligible']]
            ax.scatter(np.full(len(other),(i+.5)*.25),[v['frequency_hz'] for v in other],s=15,color='.65',marker='x')
            ax.scatter(np.full(len(eligible),(i+.5)*.25),[v['frequency_hz'] for v in eligible],s=22,color='C'+str(method))
        low_ids=[]
        lengths=[]
        for track in linked['tracks']:
            if track['frequencies_hz'][0]<200:
                low_ids.append(track['track_id'])
                lengths.append(len(track['windows']))
                ax.plot((np.array(track['windows'])+.5)*.25,track['frequencies_hz'],color='black',lw=1)
        phases=[v for v in linked['phase_advance_diagnostics'] if v['track_id'] in low_ids]
        phase_reports.append(dict(segment=name,method=label,low_start_tracks=len(low_ids),
            longest_low_track=max(lengths,default=0),low_phase_advance_edges=len(phases),phase_reports=phases))
        ax.axhline(200,color='green',ls='--',lw=.8)
        ax.set_ylim(20,260)
        ax.set_title(name+' / '+label+f' / longest low track {max(lengths,default=0)}')
        ax.set_ylabel('Fitted native frequency (Hz)')
        ax.set_xlabel('Passage time (s)')
        ax.grid(alpha=.15)
fig.suptitle('No qualifying five-window low track in either method\nGray crosses: rejected lines; colored dots: eligible; red: failed whole windows; black: contiguous low tracks only; no bridging',fontsize=12)
fig.savefig(a.out/'low_tracks.png',dpi=140)
plt.close(fig)
save(a.out/'report.json',dict(result='all48_fit_status_and_low_tracks_plotted_no_refit',summaries=summaries,
    low_phase_diagnostics=phase_reports,input_report_sha256=[sha(folder/'report.json') for folder in folders],
    audit_report_sha256=[sha(root/'audit1/report.json') for root in roots],
    images={name:sha(a.out/name) for name in ['fit_status.png','low_tracks.png']}))
print(summaries)
