"""Read-only all48 source status and low-frequency observation graphs."""
import argparse
import shutil
import sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','audit','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args()
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from research_archive_v1 import load,save,sha
a.out.mkdir(parents=True,exist_ok=False)
report=load(a.input/'report.json')
audit=load(a.audit/'report.json')
assert audit['result']=='all48_F3_native_augmented_masked_predictions_adoption_graphs_verified'
assert audit['input_report_sha256']==sha(a.input/'report.json') and audit['windows']==48
cases=[v['segment'] for v in report['observations']]
fig,axes=plt.subplots(2,3,figsize=(16,8),layout='constrained')
for column,case in enumerate(cases):
    folder=a.input/case
    native=load(folder/'native_fits.json')
    raw=load(folder/'raw_fits.json')
    rows=load(folder/'fits.json')
    decisions=load(folder/'decisions.json')
    old=load(folder/'profiled_linear_fits.json')
    ax=axes[0,column]
    for level,values in [(0,old),(1,native),(3,rows)]:
        for i,value in enumerate(values):ax.scatter(i,level,c='#bac6cf' if value['success'] else '#ac443d',
            marker='o' if value['success'] else 'x',s=35)
    for i,(value,decision) in enumerate(zip(raw,decisions)):
        if decision['reason']=='no_added_candidate':ax.scatter(i,2,c='#e5e9ed',s=20)
        else:ax.scatter(i,2,c='#087b78' if decision['augmented_adopted'] else '#71869d' if decision['reason']=='augmentation_unknown' else '#c16d32',
            marker='o' if value['success'] else 'x',s=45)
    ax.set(yticks=range(4),yticklabels=['Old linear','Native cubic','Augmented attempt','Selected observation'],
        xticks=range(0,len(rows),2),xlabel='Every original 0.25s window',title=case,ylim=(-.4,3.4))
    ax.invert_yaxis()
    ax=axes[1,column]
    links=load(folder/'links.json')['selected_boundary']
    for i,row in enumerate(rows):
        rejected=[v['frequency_hz'] for v in row['lines'] if not v['eligible'] and v['frequency_hz']<200]
        if rejected:ax.scatter([i]*len(rejected),rejected,c='#ced5dc',marker='x',s=18)
    for track in links['tracks']:
        nodes=[v for frame in links['frames'] for v in frame if v['track_id']==track['track_id']]
        low=[v for v in nodes if v['frequency_hz']<200]
        if low:ax.plot([v['window'] for v in low],[v['frequency_hz'] for v in low],'o-',ms=4,lw=1)
    summary=next(v for v in report['observations'] if v['segment']==case)
    stats=summary['variants']['selected_boundary']
    ax.set(ylim=(25,205),xticks=range(0,len(rows),2),xlabel='Every original 0.25s window',ylabel='Observed frequency (Hz)',
        title='Longest low-start track: '+str(stats['longest_low_start_track'])+'; >=5: '+str(stats['low_start_tracks_atleast5']))
for ax in axes.flat:ax.grid(alpha=.15)
fig.suptitle('All48 F3 cabin windows — original inventories, complete failures and model adoption retained\nColored low points are local graph observations, not physical engine identities; gray crosses are ineligible',fontsize=13)
first=a.out/'source_status_tracks.png'
fig.savefig(first,dpi=140)
plt.close(fig)

fig,axes=plt.subplots(1,3,figsize=(16,4.5),layout='constrained')
all_tests=[]
for column,case in enumerate(cases):
    ax=axes[column]
    decisions=load(a.input/case/'decisions.json')
    tests=[dict(window=i,**test) for i,value in enumerate(decisions) for test in value['tests']]
    all_tests.extend(tests)
    for j,test in enumerate(tests):
        color='#087b78' if test['state']=='supported' else '#71869d' if test['state']=='unknown_solver_failure' else '#c16d32'
        ax.scatter(j,min(test['prediction_gain_LR']),c=color,marker='s' if test['state']=='unknown_solver_failure' else 'o',s=30)
    ax.axhline(.8,color='black',ls='--',lw=1)
    ax.set_yscale('symlog',linthresh=1)
    ax.set(xlabel='Every added candidate, original temporal order',ylabel='Minimum LR check residual reduction',
        title=case+'; candidates='+str(len(tests)))
    ax.grid(axis='y',alpha=.15)
fig.suptitle('Complete prediction tests — unknown solver outcomes are retained, not evidence of absence',fontsize=13)
second=a.out/'source_predictions.png'
fig.savefig(second,dpi=140)
plt.close(fig)
dest=a.out/'exact_sources/tools/plot_accel_candidate_prediction_v1.py'
dest.parent.mkdir(parents=True,exist_ok=True)
shutil.copy2(Path(__file__),dest)
save(a.out/'report.json',dict(result='all48_source_status_tracks_and_all_prediction_tests_plotted',
    input_report_sha256=sha(a.input/'report.json'),audit_report_sha256=sha(a.audit/'report.json'),
    prediction_tests=len(all_tests),images={v.name:sha(v) for v in [first,second]}))
print(first)
print(second)
