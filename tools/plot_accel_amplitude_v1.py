"""All six transfers and all primary source laws; read-only, no curve selection."""
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
report=load(a.input/'report.json');pairs=[load(a.input/(row['source']+'_to_'+row['target']+'.json')) for row in report['pairs']]
labels=[row['source'].replace('F3_','')+' -> '+row['target'].replace('F3_','') for row in pairs]
fig,axes=plt.subplots(1,3,figsize=(16,4.7),layout='constrained');summary=[]
for i,pair in enumerate(pairs):
    used=[r for r in pair['references'] if r['status']=='compared']
    x=[r['median_absolute_error_db']['geometric'] for r in used];y=[r['median_absolute_error_db']['log_linear'] for r in used]
    axes[0].scatter(x,y,label=labels[i],s=28,alpha=.8)
    row=dict(source=pair['source'],target=pair['target'],shape={})
    for key in ['RMS','geometric','log_linear']:
        common=np.array([r['common_error_db_LR'][key] for r in pair['window_shape']])
        shape=np.array([e for r in pair['window_shape'] for e in r['centered_error_db_LR'][key]])
        row['shape'][key]=dict(median_absolute_common_db=float(np.median(abs(common))),median_absolute_centered_db=float(np.median(abs(shape))))
    summary.append(row)
limit=max(axes[0].get_xlim()[1],axes[0].get_ylim()[1]);axes[0].plot([0,limit],[0,limit],color='0.5',lw=1)
axes[0].set(xlabel='Geometric constant median |error| (dB)',ylabel='Log-linear median |error| (dB)',xlim=(0,limit),ylim=(0,limit))
axes[0].legend(fontsize=7);axes[0].set_title('74 compared references / below line is better')
x=np.arange(6)
for offset,key,color in [(-.24,'RMS','C0'),(0,'geometric','C2'),(.24,'log_linear','C1')]:
    axes[1].bar(x+offset,[p['summary']['median_reference_error_db'][key] for p in pairs],width=.23,label=key,color=color)
axes[1].set_xticks(x,labels,rotation=35,ha='right',fontsize=8);axes[1].set_ylabel('Median reference error (dB)');axes[1].legend(fontsize=8)
axes[1].set_title('Same target rows for all three laws')
for offset,key,color in [(-.18,'geometric','C2'),(.18,'log_linear','C1')]:
    axes[2].bar(x+offset,[s['shape'][key]['median_absolute_centered_db'] for s in summary],width=.34,color=color,label=key)
axes[2].set_xticks(x,labels,rotation=35,ha='right',fontsize=8);axes[2].set_ylabel('Median |centered error| (dB)');axes[2].legend(fontsize=8)
axes[2].set_title('Observed shape error after reporting-only centering')
for ax in axes:ax.grid(alpha=.18)
fig.suptitle('F3 cross-passage amplitude: scale alone does not consistently predict colour\nPreviously inspected same recording; error centering never changes predictions or audition gain',fontsize=11)
fig.savefig(a.out/'transfer_errors.png',dpi=150);plt.close(fig)

# All compared primary references, no best-example selection. L only in this figure.
primary=pairs[0];assert (primary['source'],primary['target'])==('F3_fifth1','F3_fifth2')
used=[row for row in primary['references'] if row['status']=='compared'];models=load(a.input/'F3_fifth1_models.json')
fits=load(a.workspace/'baselines/accel_chirp_v1/evidence/observe1/F3_fifth1/fits.json')
fig,axes=plt.subplots(4,4,figsize=(14,11),layout='constrained')
for ax,row in zip(axes.ravel(),used):
    k=row['source_reference'];item=models[k];model=item['model'];xx=[];aa=[]
    for window in fits:
        if not window['guide_supported']:continue
        for line in window['lines']:
            if line['reference_index']==k and line['eligible']:
                xx.append(np.log(window['ratio']));aa.append(line['amplitude_LR'][0])
    x=np.linspace(model['coordinate_min'],model['coordinate_max'],100);center=model['log_amplitude_mean_LR'][0]
    ax.scatter(np.exp(xx),20*np.log10(aa),marker='o',color='C0',s=16,label='source L')
    for within,color,label in [(True,'C3','target L / inside'),(False,'0.6','target L / outside')]:
        checks=[v for v in row['rows'] if v['within_source_range']==within]
        if not checks:continue
        if within:observed=[v['observed_amplitude_LR'][0] for v in checks]
        else:
            targetfits=load(a.workspace/'baselines/accel_chirp_v1/evidence/observe1/F3_fifth2/fits.json')
            observed=[next(line['amplitude_LR'][0] for line in targetfits[v['tile']]['lines'] if line['reference_index']==row['target_reference']) for v in checks]
        ax.scatter([np.exp(v['coordinate']) for v in checks],20*np.log10(observed),marker='x',color=color,s=20,label=label)
    ax.plot(np.exp(x),np.full(len(x),20*np.log10(model['RMS_amplitude_LR'][0])),color='C0',ls=':',label='RMS')
    ax.plot(np.exp(x),np.full(len(x),20/np.log(10)*center),color='C2',ls='--',label='geometric')
    ax.plot(np.exp(x),20/np.log(10)*(center+model['slope_LR'][0]*(x-model['coordinate_mean'])),color='C1',label='log-linear')
    ax.set_title(f'Ref{k} / {model["frequency_at_ratio1_hz"]:.1f}Hz',fontsize=9);ax.tick_params(labelsize=7);ax.grid(alpha=.2)
for ax in axes.ravel()[len(used):]:ax.axis('off')
axes[0,0].legend(fontsize=6)
fig.supxlabel('Relative acoustic frequency scale (not RPM)');fig.supylabel('Observed / predicted L amplitude (dBFS)')
fig.suptitle('Primary fifth1 -> fifth2: every compared reference, source-only training\nPredictions remain inside source coordinate range; gray target observations are excluded',fontsize=11)
fig.savefig(a.out/'primary_laws.png',dpi=150);plt.close(fig)
save(a.out/'report.json',dict(result='all6_errors_and_all13_primary_laws_plotted',
    input_report_sha256=sha(a.input/'report.json'),shape_diagnostics=summary,
    images={name:sha(a.out/name) for name in ['transfer_errors.png','primary_laws.png']},
    plot_is_read_only=True,source_or_load_identity=False))
