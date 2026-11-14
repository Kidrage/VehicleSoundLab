"""Localize all finite-realization discrepancies without changing or discarding a generated block."""
import argparse,os,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from research_archive_v1 import load,save,sha

a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_diagnostic.py');shutil.copy2(repo/'research/accel_upper_realization_v1_followup.json',a.out/'followup.json')
before=load(a.input/'report.json');assert before['result']=='all12_continuous_source_realizations_assessed_NOT_voice'
r=dict(result='all12_existing_discrepancies_localized_no_new_generation',input_sha256=sha(a.input/'report.json'),plan_sha256=sha(a.out/'followup.json'),cases=[],figures=[])
fig,axes=plt.subplots(2,3,figsize=(14,8),layout='constrained');coordinates=['4-8 L','4-8 R','8-14 L','8-14 R']
for row in before['cases']:
    assert sha(a.input/row['file'])==row['sha256']
    with np.load(a.input/row['file']) as f:
        expected=f['energy_expected'];source=f['source_target'];values=f['raw_theoretical_normalized'];finite=f['raw_measured_normalized'];delta=values.mean(axis=(0,1))-expected
        cell=tuple(int(v) for v in np.unravel_index(abs(delta).argmax(),delta.shape));lag,i,j=cell
        observed=values[:,:,lag,i,j];other=finite[:,:,lag,i,j];pred=float(expected[cell]);contribution=(observed-pred)/24
        item=dict(segment=row['segment'],branch=row['branch'],fit_available=row['fit_available'],worst_cell=list(cell),lag_ms=(lag-5)*10,coordinates=[coordinates[i],coordinates[j]],
            full_mean_error=delta.tolist(),max_over_lag_error=abs(delta).max(axis=0).tolist(),expected=pred,source_target=float(source[cell]),
            primary_mean=float(observed.mean()),finite_mean=float(other.mean()),signed_mean_error=float(delta[cell]),run_means=observed.mean(axis=1).tolist(),
            all24_primary=observed.tolist(),all24_finite=other.tolist(),all24_mean_error_contributions=contribution.tolist(),
            largest_absolute_single_block_contribution=float(abs(contribution).max()),no_block_removed=True)
        r['cases'].append(item)
        if row['branch']!='original':continue
        col=['F3_fifth1','F3_fifth2','F3_sixth'].index(row['segment']);ax=axes[0,col];image=ax.imshow(abs(delta).max(axis=0),vmin=0,vmax=.08,cmap='magma')
        ax.set_xticks(range(4),coordinates,rotation=25);ax.set_yticks(range(4),coordinates);ax.set_title(row['segment']+' | max over all11 lags')
        for ii in range(4):
            for jj in range(4):ax.text(jj,ii,f'{abs(delta[:,ii,jj]).max():.4f}',ha='center',va='center',fontsize=8,color='white' if abs(delta[:,ii,jj]).max()<.04 else 'black')
        fig.colorbar(image,ax=ax,shrink=.75)
        ax=axes[1,col];x=np.arange(24);ax.plot(x,observed.ravel(),'o-',color='#365eaa',label='Model-power denominator',ms=3);ax.plot(x,other.ravel(),'x--',color='#b28650',label='Finite-power denominator',ms=3)
        ax.axhline(pred,color='#596168',label='Model expectation');ax.axhline(float(source[cell]),color='#247f73',label='Original source target')
        for k in [7.5,15.5]:ax.axvline(k,color='#a2aaae',lw=.6)
        ax.set(title=f'{coordinates[i]} / {coordinates[j]} at {(lag-5)*10:+d}ms',xlabel='All24 blocks, 8 per continuous run',ylabel='Signed energy covariance');ax.grid(alpha=.15)
        if col==0:ax.legend(fontsize=7)
fig.suptitle('Post-observation localization | all16 coordinates and all24 blocks retained\nWorst cell is descriptive selection; no cause, outlier deletion or statistical gate inferred',fontsize=12)
path=a.out/'localization.png';fig.savefig(path,dpi=150);plt.close(fig);r['figures'].append(dict(file=path.name,sha256=sha(path)))
r.update(no_new_generation=True,no_model_change=True,post_observation_selection_explicit=True,next=load(a.out/'followup.json')['next'])
save(a.out/'report.json',r)
for row in r['cases']:
    if row['branch']=='original':print(dict(segment=row['segment'],worst_cell=row['worst_cell'],expected=row['expected'],mean=row['primary_mean'],runs=row['run_means'],largest_contribution=row['largest_absolute_single_block_contribution']),flush=True)
