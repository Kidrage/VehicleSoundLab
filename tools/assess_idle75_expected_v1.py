"""Assess conditional expected75 fit without mistaking it for idle listening acceptance."""
import argparse,os,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','audit','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from research_archive_v1 import load,save,sha
a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_assessment.py')
run=load(a.input/'report.json');audit=load(a.audit/'report.json')
assert audit['result']=='conditional_expected75_operator_and_terminal_moments_independently_checked'
assert audit['input_sha256']==sha(a.input/'report.json')
source=run['models'].get('source');lags=np.array([0,40,100,200]);curves=[]
prior=next(x for x in run['controls']['grid_moments'] if x['parameters']==[1.,1.])['moments_1000']
curves.append(('Expected 1x / 1x',np.array(prior),'#718691','--'))
if source:
    curves.append(('F2 TRAIN',np.array(source['target']),'#202f3b','-'))
    curves.append(('Conditional fit',np.array(source['prediction']),'#b7683e','-'))
    check=next(row for row in run['CHECK'] if row['family']=='source')
    curves.append(('F2 CHECK (already inspected)',np.array(check['target']),'#29878b',':'))
fig,axes=plt.subplots(1,2,figsize=(12,4.5),layout='constrained')
for label,value,colour,style in curves:
    axes[0].plot(lags,value,'o',ls=style,color=colour,label=label)
    axes[1].plot(lags,value/value[0],'o',ls=style,color=colour,label=label)
axes[0].set(title='Finite-window covariance',ylabel='Normalized real coefficient covariance')
axes[1].set(title='Time structure (each curve divided by its lag0)',ylabel='Lag covariance / variance')
for ax in axes:ax.set_xlabel('Observer lag (ms)');ax.grid(alpha=.2);ax.legend(fontsize=8)
title='Known inverse qualified; source solved, time-structure mismatch remains' if source else 'Known controls only'
fig.suptitle(title+'\nConditional phases/detail; no new audio or C voice',fontsize=12)
figure=a.out/'evidence.png';fig.savefig(figure,dpi=150);plt.close(fig)
models=[]
for family,result in run['models'].items():
    target=np.array(result['target']);pred=np.array(result['prediction'])
    check=next(row for row in run['CHECK'] if row['family']==family)
    models.append(dict(family=family,available=result['available'],parameters=result['parameters'],active_mask=result['active_mask'],
        TRAIN_scaled_squared_error=result['scaled_squared_error'],CHECK_scaled_squared_error=check['scaled_squared_error'],
        target_std=float(np.sqrt(target[0])),prediction_std=float(np.sqrt(pred[0])),
        target_rho=(target/target[0]).tolist(),prediction_rho=(pred/pred[0]).tolist(),
        rank=result['rank'],condition=result['condition'],nfev=result['nfev']))
result=dict(result='conditional_expected75_fit_assessed',input_sha256=sha(a.input/'report.json'),audit_sha256=sha(a.audit/'report.json'),
    known_recovery_errors={label:x['maximum_parameter_error'] for label,x in run['known'].items() if label!='truth'},
    maximum_native_coefficient_compression_error=max(x['maximum_normalized_coefficient_error'] for x in run['controls']['native_coefficients']),
    maximum_grid_relative_moment_error=max(x['maximum_relative_moment_error'] for x in run['controls']['grid_moments']),
    models=models,figure=dict(file=figure.name,sha256=sha(figure)),
    conditional_not_full_phase_estimator_expectation=True,source_physical_excitation_identified=False,new_audio=False,new_C=False,
    source_optimizer_available_is_numerical_only=True,
    adoption='Not adopted: descriptive TRAIN/CHECK temporal mismatch; no new numerical gate or global impossibility claim.',
    next='Investigate source-derived temporal shape and phase/amplitude conditioning through the observer, retaining source TRAIN/CHECK variation. The current two-parameter local fit has not matched time structure. No clock/strength/start/bounds/grid sweep or blind gain boost. Later source-forward validation must include actual MIX phase estimator; retain independent75 control if rendering. Pending idle allocation hearing remains separate.')
if source:
    target=np.array(source['target']);pred=np.array(source['prediction']);baseline=np.array(prior)
    result['source_baseline_TRAIN_scaled_squared_error']=float(np.sum(((baseline-target)/target[0])**2))
    result['source_local_fit_TRAIN_scaled_squared_error']=float(np.sum(((pred-target)/target[0])**2))
    source_check=next(row for row in run['CHECK'] if row['family']=='source')
    result['source_baseline_CHECK_scaled_squared_error']=float(np.sum(((baseline-np.array(source_check['target']))/target[0])**2))
save(a.out/'report.json',result);print(result)
