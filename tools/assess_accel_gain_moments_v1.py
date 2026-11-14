"""All finite power-moment summaries, with exact SDs and no Gaussian confidence claims."""
import argparse, os, shutil, sys
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','audit','out']:parser.add_argument('--'+key,type=Path,required=True)
args=parser.parse_args();sys.path.insert(0,str(args.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from research_archive_v1 import load,save,sha

args.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,args.out/'executed_assessment.py')
run=load(args.input/'report.json');audit=load(args.audit/'report.json');assert audit['result']=='passed'
r=dict(result='all12_finite_gain_power_moments_assessed_NOT_voice_or_VarS',input_sha256=sha(args.input/'report.json'),
       audit_sha256=sha(args.audit/'report.json'),cases=[],figures=[])
coords=['4-8 L','4-8 R','8-14 L','8-14 R'];labels=[f'g{p} {ch}' for p in [2,4] for ch in coords]
figure,axes=plt.subplots(2,3,figsize=(14,8),layout='constrained');names=[];scores=[];fifth2=None
for row in run['observations']:
    assert sha(args.input/row['file'])==row['sha256']
    with np.load(args.input/row['file']) as f:
        covariance=f['independent3_run_mean_covariance'];sd=f['pooled3_sd'];single=f['block_lag_covariance'][0]
        independent=np.diag(single)/(3*8);defined=independent>0;ratio=np.zeros(8)
        ratio[defined]=np.diag(covariance)[defined]/independent[defined]
        denominator=np.outer(sd,sd);correlation=np.zeros((8,8));valid=denominator>0
        correlation[valid]=covariance[valid]/denominator[valid]
        item=dict(segment=row['segment'],branch=row['branch'],fit_available=row['fit_available'],
            expected=f['mean'].tolist(),actual_mean=f['actual_mean'].tolist(),actual3_run_means=f['actual_run'].tolist(),all24_block_means=f['actual_block'].tolist(),
            block_sd=np.sqrt(np.diag(single)).tolist(),continuous_run_sd=np.sqrt(np.diag(f['continuous_run_covariance'])).tolist(),pooled3_sd=sd.tolist(),
            descriptive_standardized_difference=f['descriptive_standardized_difference'].tolist(),standardized_defined=f['standardized_defined'].tolist(),
            actual_minimum_block=f['actual_block'].min(axis=(0,1)).tolist(),actual_maximum_block=f['actual_block'].max(axis=(0,1)).tolist(),
            actual_minimum_run=f['actual_run'].min(axis=0).tolist(),actual_maximum_run=f['actual_run'].max(axis=0).tolist(),
            exact_over_independent8blocks_variance_ratio=ratio.tolist(),independence_ratio_defined=defined.tolist(),
            pooled3_power_crosscorrelation=correlation.tolist(),minimum_full64x64_eigenvalue=float(np.linalg.eigvalsh(f['full_block_covariance']).min()))
        r['cases'].append(item);names.append(row['segment'].replace('F3_','')+' / '+row['branch'].replace('phase_','P'));scores.append(item['descriptive_standardized_difference'])
        if row['branch']!='original':continue
        column=['F3_fifth1','F3_fifth2','F3_sixth'].index(row['segment']);ax=axes[0,column]
        ax.plot(np.arange(24),f['actual_block'][:,:,7].ravel(),'o-',ms=3,color='#365eaa',label='All existing blocks')
        ax.axhline(f['mean'][7],color='#996c42',label='Analytic stationary mean')
        for boundary in [7.5,15.5]:ax.axvline(boundary,color='#aab1b4',lw=.7)
        ax.set(title=row['segment']+' | mean(g4), 8-14 R',xlabel='24 consecutive blocks, 8 per run',ylabel='Gain fourth-power mean');ax.grid(alpha=.15)
        if column==0:ax.legend(fontsize=7)
        ax=axes[1,column];x=np.arange(4);difference=f['actual_mean'][4:]-f['mean'][4:]
        ax.errorbar(x,difference,yerr=sd[4:],fmt='o',capsize=4,color='#365eaa',label='Actual mean minus expectation; bars = exact SD')
        ax.axhline(0,color='#996c42',lw=1);ax.set_xticks(x,coords,rotation=25);ax.set_ylabel('Pooled3 mean(g4) discrepancy');ax.grid(alpha=.15)
        if column==0:ax.legend(fontsize=6)
        if row['segment']=='F3_fifth2':fifth2=correlation.copy()
figure.suptitle('Existing continuous gain paths | native exact finite power-moment covariance\nSD bars are NOT confidence intervals; adjacent blocks are not independent; this is NOT Var(S)',fontsize=12)
fig2,ax=plt.subplots(1,2,figsize=(15,7),layout='constrained');table=np.array(scores);limit=float(abs(table).max())
im=ax[0].imshow(table,aspect='auto',cmap='coolwarm',vmin=-limit,vmax=limit)
ax[0].set_yticks(range(12),names,fontsize=7);ax[0].set_xticks(range(8),labels,rotation=60,ha='right',fontsize=7)
ax[0].set_title('All12: (actual mean - expectation) / exact pooled3 SD\nDescriptive only; no normality or significance threshold',fontsize=10)
for i in range(12):
    for j in range(8):ax[0].text(j,i,f'{table[i,j]:.2f}',ha='center',va='center',fontsize=7,color='white' if abs(table[i,j])>.6*limit else 'black')
fig2.colorbar(im,ax=ax[0],shrink=.65)
im2=ax[1].imshow(fifth2,cmap='coolwarm',vmin=-1,vmax=1);ax[1].set_xticks(range(8),labels,rotation=60,ha='right',fontsize=7)
ax[1].set_yticks(range(8),labels,fontsize=7);ax[1].set_title('Fifth2 original | exact pooled mean crosscorrelation\nRecording-coordinate gain powers, not physical objects',fontsize=10)
for i in range(8):
    for j in range(8):ax[1].text(j,i,f'{fifth2[i,j]:.2f}',ha='center',va='center',fontsize=7,color='white' if abs(fifth2[i,j])>.6 else 'black')
fig2.colorbar(im2,ax=ax[1],shrink=.65)
fig2.suptitle('Finite gain-power uncertainty | all coordinates, all blocks retained | no source refit or new seeds',fontsize=12)
for name,fig in [('finite_moments.png',figure),('joint_moments.png',fig2)]:
    path=args.out/name;fig.savefig(path,dpi=150);plt.close(fig);r['figures'].append(dict(file=name,sha256=sha(path)))
r.update(not_VarS_or_conditional_quadratic_uncertainty=True,not_normal_scores_or_confidence_intervals=True,new_audio=False,
    next='The existing g2/g4 mean shifts must be interpreted with their exact native finite covariance, not as deterministic gain bugs. These moments alone do not qualify conditional quadratic/output energy uncertainty or justify clipping/refitting. Next qualify the full quadratic-observer uncertainty or a source-supported replacement law, and retain source/state/time and post-refilter limitations before realtime promotion.')
save(args.out/'report.json',r)
for row in r['cases']:
    if row['branch']=='original':print(dict(segment=row['segment'],expected_g4=row['expected'][4:],actual_g4=row['actual_mean'][4:],
        sd_g4=row['pooled3_sd'][4:],descriptive_difference=row['descriptive_standardized_difference'][4:],
        variance_ratio=row['exact_over_independent8blocks_variance_ratio'][4:]),flush=True)
