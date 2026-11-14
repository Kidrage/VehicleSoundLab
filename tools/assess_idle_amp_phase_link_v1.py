"""Plot source transfer and existing stream support, with explicit posthoc MSE accounting."""
import argparse,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','audit','stream','stream-audit','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from research_archive_v1 import load,save,sha

a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_assessment.py')
r=dict(result='running',posthoc_bias_variance_decomposition=True,no_model_refit=True)
try:
    source=load(a.input/'report.json');stream=load(a.stream/'report.json')
    assert load(a.audit/'report.json')['result']==load(a.stream_audit/'report.json')['result']=='passed'
    r.update(source_report_sha256=sha(a.input/'report.json'),source_audit_sha256=sha(a.audit/'report.json'),
        stream_report_sha256=sha(a.stream/'report.json'),stream_audit_sha256=sha(a.stream_audit/'report.json'))
    r['source_MSE_decomposition']=[]
    for part in ['train','check']:
        row=next(v for v in source['evaluations'] if v['family']=='source' and v['part']==part)
        case=next(v for v in source['cases'] if v['label']=='source_'+part)
        with np.load(a.input/case['file']) as f:y=f['y']
        pred=np.load(a.input/row['prediction_file']);error=pred-y
        reference=np.array(source['models']['source']['TRAIN_target_mean'])-y
        variance=np.var(error,axis=0);bias=np.mean(error,axis=0)**2
        identity=float(abs(variance+bias-row['MSE']).max());assert identity<1e-12
        r['source_MSE_decomposition'].append(dict(part=part,
            error_variance=variance.tolist(),error_squared_bias=bias.tolist(),
            TRAIN_constant_error_variance=np.var(reference,axis=0).tolist(),
            TRAIN_constant_squared_bias=(np.mean(reference,axis=0)**2).tolist(),
            fractional_error_variance_reduction=(1-variance/np.var(reference,axis=0)).tolist(),
            MSE_identity_error=identity,
            note='Descriptive posthoc accounting only; no CHECK intercept/predictor refit or new model selection'))
    fig,axes=plt.subplots(2,3,figsize=(13,7),layout='constrained')
    check=[v for v in source['evaluations'] if v['part']=='check']
    modes=['75 Hz','112 Hz','187 Hz'];colors=['#28776c','#8999a6','#a7b2bb','#c1c9cf']
    with np.load(a.stream/stream['streams'][0]['file']) as f:
        centers=(f['starts']+4800)/48000;prediction=f['predicted_window_log_magnitude']
    mean=np.array(source['models']['source']['TRAIN_target_mean'])
    for j,name in enumerate(modes):
        values=np.array([row['fractional_MSE_reduction'][j]*100 for row in check])
        axes[0,j].bar(range(4),values,color=colors);axes[0,j].axhline(0,color='#475563',linewidth=.8)
        axes[0,j].set_xticks(range(4),['F2','phase1','phase2','phase3'],rotation=20)
        fluctuation=100*r['source_MSE_decomposition'][1]['fractional_error_variance_reduction'][j]
        axes[0,j].set(title=name+' CHECK MSE\nfluctuation error '+f'{-fluctuation:+.1f}%',
            ylabel='MSE reduction vs TRAIN constant (%)',ylim=(-110,25))
        for k,value in enumerate(values):axes[0,j].text(k,value+(2 if value>=0 else -2),f'{value:.1f}',ha='center',va='bottom' if value>=0 else 'top',fontsize=8)
        axes[1,j].plot(centers,prediction[:,j]-mean[j],linewidth=.8,color='#28776c',label='Existing180s phase stream')
        for part,color in [('train','#465f76'),('check','#c08c36')]:
            lo,hi=np.array(stream['source_observed_log_ranges'][part])[:,j]-mean[j]
            axes[1,j].axhline(lo,color=color,linestyle='--',linewidth=.8,label='F2 '+part+' observed min/max')
            axes[1,j].axhline(hi,color=color,linestyle='--',linewidth=.8)
        axes[1,j].set(title=name+' hypothetical WINDOW prediction',xlabel='existing phase-stream time (s)',ylabel='log magnitude offset')
        axes[1,j].legend(fontsize=7)
    for ax in axes.flat:ax.grid(alpha=.18)
    fig.suptitle('Idle AM / relative phase: short-source association; no instantaneous gain or new audio',fontsize=13)
    path=a.out/'evidence.png';fig.savefig(path,dpi=150);plt.close(fig)
    r.update(result='AM_phase_source_and_stream_evidence_assessed',figure=dict(file=path.name,sha256=sha(path)),
        source_CHECK_MSE_reductions=check[0]['fractional_MSE_reduction'],
        source_model_condition=source['models']['source']['condition'],
        full_stream_windows=sum(row['windows'] for row in stream['streams']),
        full_stream_feature_box_outside=[(row['seed'],row['any_feature_outside_TRAIN_box_fraction']) for row in stream['streams']],
        source_short_previously_inspected=True,physical_AM_PM_identified=False,new_audio_generated=False,runtime_changed=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(dict(result=r['result'],bias_variance=r['source_MSE_decomposition'],outside=r.get('full_stream_feature_box_outside')),flush=True)
