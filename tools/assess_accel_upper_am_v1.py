"""All persistent joint-gain fits, signed lag shapes and complete covariance matrices."""
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
run=load(a.input/'report.json');audit=load(a.audit/'report.json');assert audit['result']=='passed'
parent=a.workspace/'baselines/accel_upper_forward_v1';assert sha(parent/'manifest.json')==run['parent_manifest_sha256']
r=dict(result='all12_joint_gain_fits_assessed_not_voice',input_sha256=sha(a.input/'report.json'),
       audit_sha256=sha(a.audit/'report.json'),cases=[],figures=[])
fig,axes=plt.subplots(2,3,figsize=(14,8),layout='constrained')
fig2,ax2=plt.subplots(2,3,figsize=(13,8),layout='constrained')
names=['4-8 L','4-8 R','8-14 L','8-14 R'];lags=np.arange(-5,6)*10
for row in run['observations']:
    result=row['fit'];r['cases'].append(dict(segment=row['segment'],branch=row['branch'],available=result['available'],
        success=result['success'],status=result['status'],nfev=result['nfev'],rank=result['rank'],condition=result['condition'],
        tau_ms=1000*row['tau_seconds'],bound_mask=result['bound_mask'],initial_cost=result['initial_cost'],final_cost=result['cost'],
        cost_reduction_from_initial=1-result['cost']/result['initial_cost'],maximum_error=row['maximum_error'],Gamma=row['Gamma']))
for column,segment in enumerate(['F3_fifth1','F3_fifth2','F3_sixth']):
    source=next(v for v in run['observations'] if v['segment']==segment and v['branch']=='original')
    controls=[v for v in run['observations'] if v['segment']==segment and v['branch']!='original'];assert len(controls)==3
    with np.load(a.input/source['file']) as f:target=f['target'];prediction=f['prediction'];Gamma=f['Gamma']
    with np.load(parent/source['parent_file']) as f:iid=f['prediction']
    control_values=[]
    for control in controls:
        with np.load(a.input/control['file']) as f:control_values.append(f['target'])
    control_values=np.array(control_values)
    for row,(i,j,label) in enumerate([(0,2,'L cross-band'),(1,3,'R cross-band')]):
        ax=axes[row,column];ctrl=control_values[:,:,i,j]
        ax.fill_between(lags,ctrl.min(axis=0),ctrl.max(axis=0),color='#607481',alpha=.15,label='3 phase controls, not CI')
        ax.plot(lags,target[:,i,j],'o-',color='#247f73',ms=4,label='Original recording')
        ax.plot(lags,prediction[:,i,j],'-',color='#365eaa',lw=2,label='Joint positive gain')
        ax.plot(lags,iid[:,i,j],'--',color='#a97a3f',lw=1,label='Prior optimistic pairwise iid')
        ax.set(title=segment+' | '+label,xlabel='Within-tile lag (ms)',ylabel='Energy covariance / product of means')
        ax.axhline(0,color='#87959c',lw=.6);ax.grid(axis='y',alpha=.2)
        if row==column==0:ax.legend(fontsize=7)
    gm=ax2[0,column].imshow(Gamma,cmap='RdBu_r',vmin=-.14,vmax=.14)
    em=ax2[1,column].imshow(np.max(abs(prediction-target),axis=0),cmap='magma',vmin=0,vmax=.06)
    ax2[0,column].set_title(segment+f" | tau={1000*source['tau_seconds']:.2f}ms")
    for ax in ax2[:,column]:ax.set_xticks(range(4),names,rotation=25);ax.set_yticks(range(4),names)
    error=np.max(abs(prediction-target),axis=0)
    for i in range(4):
        for j in range(4):
            ax2[0,column].text(j,i,f'{Gamma[i,j]:.3f}',ha='center',va='center',fontsize=8,color='white' if abs(Gamma[i,j])>.07 else 'black')
            ax2[1,column].text(j,i,f'{error[i,j]:.3f}',ha='center',va='center',fontsize=8,color='white' if error[i,j]<.032 else 'black')
fig.suptitle('Joint OU positive gain AFTER Gaussian carrier filters | original finite energy observer\nOne joint 11-parameter fit per passage; numerical availability is not timbre acceptance',fontsize=12)
fig2.suptitle('Full 4x4 joint log-gain covariance (top) and all-11-lag maximum errors (bottom)\nSource carrier PSD/stereo not fitted; no runtime or listening candidate',fontsize=12)
fig2.colorbar(gm,ax=ax2[0,:],shrink=.8,label='Gamma: log-gain covariance')
fig2.colorbar(em,ax=ax2[1,:],shrink=.8,label='Normalized energy covariance error')
for name,figure in [('lag_shape.png',fig),('joint_matrix.png',fig2)]:
    path=a.out/name;figure.savefig(path,dpi=150);plt.close(figure);r['figures'].append(dict(file=name,sha256=sha(path)))
r.update(source_available=sum(v['branch']=='original' and v['available'] for v in r['cases']),
         control_available=sum(v['branch']!='original' and v['available'] for v in r['cases']),
         no_independent_recordings_or_holdout=True,gain_after_filter_not_prefilter=True,new_listening_audio=False,
         next='Retain joint positive-gain controls and native observer, not a new accepted voice. Source PSD and stereo carrier covariance, post-gain sideband/refilter budgets, residual time structure and state-conditioned slow colour remain unqualified. Do not expand tau/bounds or add random strengths to rescue residuals. Preserve the pending idle candidate and accepted moving35; no C migration before qualified listening/source coverage.')
save(a.out/'report.json',r);print(dict(result=r['result'],source_available=r['source_available'],control_available=r['control_available']),flush=True)
