"""Plot native HF slopes, unqualified residual dependence and stereo ILD."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','study','audit','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'):os.environ[name]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_review.py')
    m,audit=load(a.study/'report.json'),load(a.audit/'report.json')
    assert audit['result']=='independent_joint_envelope_audit_passed'
    assert audit['producer_report_sha256']==sha(a.study/'report.json')
    fig,axes=plt.subplots(2,3,figsize=(15,9),layout='constrained');observations=[]
    bandlabels=['3-6k','6-8k','8-10k','10-14k']
    ticklabels=[b+c for b in ['3-6','6-8','8-10','10-14'] for c in ['L','R']]
    for i,row in enumerate(m['real']):
        d=np.load(a.study/row['label']/'arrays.npz');t=d['times'];x=d['log_power_dB'][:,8:].reshape(-1,4,2)
        slope=d['trend_coefficients'][1,8:].reshape(4,2)
        cov=d['affine_residual_covariance'][8:,8:]
        correlation=cov/np.sqrt(np.diag(cov)[:,None]*np.diag(cov)[None,:])
        eigen=np.linalg.eigvalsh(cov);first_fraction=float(eigen[-1]/eigen.sum())
        for b in range(4):
            # Display channel-mean dB (geometric power mean), not sum power.
            mean=x[:,b].mean(axis=1);axes[i,0].plot(t,mean-mean.mean(),label=bandlabels[b])
            axes[i,2].plot(t,d['ILD_dB'][:,4+b],label=bandlabels[b])
        axes[i,0].set(title=row['label']+': centered mean-channel dB',xlabel='Original-time offset / s',ylabel='dB relative each band mean')
        axes[i,0].legend(fontsize=8);axes[i,0].grid(alpha=.2)
        im=axes[i,1].imshow(correlation,vmin=-1,vmax=1,cmap='RdBu_r')
        axes[i,1].set(title=f'After affine trend: correlation (PC1 {first_fraction:.1%})',xticks=range(8),xticklabels=ticklabels,yticks=range(8),yticklabels=ticklabels)
        axes[i,1].tick_params(axis='x',rotation=45)
        for j in range(8):
            for k in range(8):axes[i,1].text(k,j,f'{correlation[j,k]:.2f}',ha='center',va='center',fontsize=7,bbox=dict(facecolor='white',alpha=.6,edgecolor='none',pad=.1))
        fig.colorbar(im,ax=axes[i,1],shrink=.8)
        axes[i,2].set(title='Observed L minus R band level',xlabel='Original-time offset / s',ylabel='ILD / dB')
        axes[i,2].legend(fontsize=8);axes[i,2].grid(alpha=.2)
        P=d['P'][:,4:].mean(axis=0)
        rho=P[:,0,1]/np.sqrt(P[:,0,0].real*P[:,1,1].real)
        observations.append(dict(label=row['label'],HF_slope_dB_per_second=slope.tolist(),
                                 HF_affine_residual_std_dB=np.sqrt(np.diag(cov)).reshape(4,2).tolist(),
                                 HF_residual_LR_correlation=[float(correlation[2*b,2*b+1]) for b in range(4)],
                                 HF_covariance_PC1_fraction=first_fraction,
                                 HF_ILD_std_dB=d['ILD_dB'][:,4:].std(axis=0).tolist(),
                                 HF_mean_spectral_coherence_abs=abs(rho).tolist(),
                                 HF_mean_spectral_coherence_real_imag=np.stack([rho.real,rho.imag],axis=-1).tolist()))
    fig.suptitle('Longer native HF observations: retain trend, cross-band dependence and L/R difference\nAffine residual is descriptive, not isolated mechanical noise or a stationary synthesis law. Two contexts from one video.')
    fig.savefig(a.out/'joint_native_envelopes.png',dpi=150);plt.close(fig)
    # Known common vs differential modulation makes the intended distinction
    # visible without assigning a physical source to real residuals.
    fig,axes=plt.subplots(1,2,figsize=(12,4),layout='constrained')
    for ax,label in zip(axes,['known_shared_AM4Hz','known_differential_AM']):
        d=np.load(a.study/label/'arrays.npz');x=d['log_power_dB'][:,8:]
        ax.plot(d['times'],x-x.mean(axis=0),linewidth=.8)
        ax.set(title=label,xlabel='Time / s',ylabel='Per-channel band dB minus mean');ax.grid(alpha=.2)
    fig.suptitle('Known deterministic controls: common envelope and distinct band / channel envelopes')
    fig.savefig(a.out/'known_joint_envelopes.png',dpi=150);plt.close(fig)
    save(a.out/'observations.json',dict(schema='vsl.native-HF-joint-observations/1',runtime_preset=False,stochastic_law_qualified=False,cases=observations))
    save(a.out/'report.json',dict(result='native_joint_envelope_observations_published',
         producer_report_sha256=sha(a.study/'report.json'),audit_report_sha256=sha(a.audit/'report.json'),
         observations_sha256=sha(a.out/'observations.json'),observations=observations,
         images={n:sha(a.out/n) for n in ['joint_native_envelopes.png','known_joint_envelopes.png']},
         runtime_changed=False,new_audio=False))
    print(dict(result='native_joint_envelope_observations_published',cases=observations))


if __name__=='__main__':main()
