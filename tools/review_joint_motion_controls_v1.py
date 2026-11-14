"""Compare motion and texture ablations without treating their difference as noise."""
import argparse
import math
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','known','known-audit','real','real-audit','out'):
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
        os.environ[name]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    known,real=load(a.known/'report.json'),load(a.real/'report.json')
    ka,ra=load(a.known_audit/'report.json'),load(a.real_audit/'report.json')
    assert ka['result']==ra['result']=='independent_motion_observation_audit_passed'
    assert ka['producer_report_sha256']==sha(a.known/'report.json')
    assert ra['producer_report_sha256']==sha(a.real/'report.json')
    a.out.mkdir(parents=True,exist_ok=False)
    shutil.copy2(__file__,a.out/'executed_review.py')
    fig,axes=plt.subplots(2,3,figsize=(14,8),layout='constrained')
    x=np.arange(3);modulations=['none','common','differential']
    for j,family in enumerate(['safe','edge','dense']):
        for k,motion in enumerate(['static','rising']):
            rows=[next(r for r in known['cases'] if r.get('family')==family and r['motion']==motion and r['modulation']==mod) for mod in modulations]
            rms=[math.sqrt(r['HF_covariance_trace_dB2']/8) for r in rows]
            pc1=[r['HF_PC1_fraction'] for r in rows]
            pos=x+(k-.5)*.32
            axes[0,j].bar(pos,rms,.32,label=motion)
            for q,value in enumerate(pc1):
                if value is not None:
                    axes[1,j].bar(pos[q],value,.32,color=['C0','C1'][k])
                else:
                    axes[1,j].text(pos[q],.04,'floor',rotation=90,ha='center',fontsize=8)
        axes[0,j].set(title=family,ylabel='RMS of 8 HF residual standard deviations / dB',yscale='log',ylim=(1e-12,10),xticks=x,xticklabels=modulations)
        axes[0,j].axhline(math.sqrt(1e-10/8),color='gray',ls='--',lw=.8,label='PC1 reporting floor')
        axes[0,j].legend(fontsize=8)
        axes[1,j].set(ylabel='PC1 / covariance trace',ylim=(0,1.08),xticks=x,xticklabels=modulations)
        for ax in axes[:,j]:ax.grid(alpha=.2)
    fig.suptitle('Known carriers: no AM / shared AM / differential AM, stationary versus rising\nBoundary crossing alone can yield high PC1. Always inspect absolute variation; a PC1 fraction is not a naturalness score.')
    fig.savefig(a.out/'known_motion_AM.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(2,3,figsize=(15,8),layout='constrained')
    pairs=[];maximum_identity=0.;maximum_scalar=0.
    for g,group in enumerate(['first','second']):
        for q,trajectory in enumerate(['static_mid','local_rise']):
            rows=[r for r in real['cases'] if r['group']==group and r['trajectory']==trajectory]
            baseline=next(r for r in rows if r['detail']==0)
            full=[r for r in rows if r['detail']==1]
            ordered=[baseline]+full
            positions=np.arange(4)+(q-.5)*.34
            rms=[math.sqrt(r['HF_covariance_trace_dB2']/8) for r in ordered]
            axes[g,0].bar(positions,rms,.34,label=trajectory)
            axes[g,1].plot(range(4),[r['HF_PC1_fraction'] for r in ordered],marker='o',label=trajectory)
            bp=a.real/baseline['label']/'arrays.npz'
            assert sha(bp)==baseline['arrays_sha256']
            base=np.load(bp)
            M=base['affine_residual_dB'][:,8:]
            for j,row in enumerate(full):
                path=a.real/row['label']/'arrays.npz'
                assert sha(path)==row['arrays_sha256']
                d=np.load(path)
                assert sha(a.real/row['label']/'C_source.csv')==sha(a.real/baseline['label']/'C_source.csv')
                F=d['affine_residual_dB'][:,8:]
                R=F-M
                C_M=M.T@M/len(M);C_R=R.T@R/len(R);X=M.T@R/len(R)
                C_F=F.T@F/len(F);signed=X+X.T
                error=float(abs(C_F-C_M-C_R-signed).max())
                assert error<1e-10
                maximum_identity=max(maximum_identity,error)
                for values,target in [(M,C_M),(R,C_R),(F,C_F)]:
                    scalar=np.array([[math.fsum(float(a*b) for a,b in zip(left,right))/len(values) for right in values.T] for left in values.T])
                    maximum_scalar=max(maximum_scalar,float(abs(scalar-target).max()))
                trace=[float(np.trace(v)) for v in [C_M,C_R,signed]]
                slot=q*3+j
                for k,(label,value) in enumerate(zip(['Mean-only','Log full/mean effect','Signed interaction'],trace)):
                    axes[g,2].bar(slot+(k-1)*.24,value,.24,color=['C0','C1','C2'][k],label=label if slot==0 else None)
                folder=a.out/row['label'];folder.mkdir()
                np.savez_compressed(folder/'log_covariance_budget.npz',mean_residual=M,full_residual=F,
                    log_ratio_residual=R,C_mean=C_M,C_log_ratio=C_R,C_full=C_F,cross_mean_ratio=X,signed_cross=signed)
                pairs.append(dict(label=row['label'],group=group,trajectory=trajectory,seed=row['seed'],
                    baseline=baseline['label'],counterfactual_not_physical_layer=True,
                    same_C_clock_phase_branch_CSV=True,HF_mean_only_trace_dB2=trace[0],
                    HF_log_ratio_trace_dB2=trace[1],HF_signed_interaction_trace_dB2=trace[2],
                    HF_full_trace_dB2=float(np.trace(C_F)),
                    literal_signed_interaction_eigenvalues_dB2=np.linalg.eigvalsh(signed).tolist(),
                    arrays_sha256=sha(folder/'log_covariance_budget.npz')))
        axes[g,0].set(title=f'{group}: absolute variation',ylabel='RMS of HF residual std / dB',xticks=range(4),xticklabels=['Mean-only','Texture seed1','23117','61927'])
        axes[g,0].legend(fontsize=8)
        axes[g,1].set(title='PC1: interpret with absolute variation',ylabel='PC1 / covariance trace',ylim=(0,1),xticks=range(4),xticklabels=['Mean-only','Texture seed1','23117','61927'])
        axes[g,1].legend(fontsize=8)
        axes[g,2].axhline(0,color='black',lw=.7)
        axes[g,2].set(title='Literal log-covariance budget',ylabel='8-dimensional covariance trace / dB squared',xticks=range(6),xticklabels=['static1','23117','61927','rise1','23117','61927'])
        axes[g,2].legend(fontsize=7)
        for ax in axes[g]:ax.grid(alpha=.2);ax.tick_params(axis='x',rotation=20)
    fig.suptitle('Frozen original C source: separate F3 banks, same clock/phase for paired texture on/off\nSource-only controlled ablation, not a reproduction of native driving. The log-ratio effect is not independent physical noise.')
    fig.savefig(a.out/'C_motion_texture_budget.png',dpi=150);plt.close(fig)
    assert maximum_scalar<1e-10
    save(a.out/'pairs.json',dict(schema='vsl.motion-texture-paired-budget/1',pairs=pairs,
        maximum_log_covariance_identity_error=maximum_identity,maximum_scalar_covariance_error=maximum_scalar,
        runtime_preset=False,source_phase_origin_identified=False))
    save(a.out/'report.json',dict(result='motion_texture_ablation_observations_published',
        known_report_sha256=sha(a.known/'report.json'),known_audit_report_sha256=sha(a.known_audit/'report.json'),
        real_report_sha256=sha(a.real/'report.json'),real_audit_report_sha256=sha(a.real_audit/'report.json'),
        pairs_sha256=sha(a.out/'pairs.json'),pairs=12,
        images={n:sha(a.out/n) for n in ['known_motion_AM.png','C_motion_texture_budget.png']},
        maximum_log_covariance_identity_error=maximum_identity,maximum_scalar_covariance_error=maximum_scalar,
        heard=False,runtime_or_model_changed=False))
    print(dict(result='motion_texture_ablation_observations_published',pairs=len(pairs),
               identity_error=maximum_identity,scalar_error=maximum_scalar))


if __name__=='__main__':main()
