"""Publish all24 in-sample outcomes and all solver failures with two figures."""
import argparse, os, shutil, sys
from pathlib import Path
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','root','out'):
        p.add_argument('--'+name,type=Path,required=True)
    a = p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
        os.environ[name]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from observer_inverse_v1.metrics import collect,summarize,VARIANTS
    repo=Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True,exist_ok=False)
    sources=('tools/review_observer_inverse_v1.py','tools/observer_inverse_v1/metrics.py')
    for name in sources:
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest)
    for audit_name, study in (('real_audit1','real2'),('real_audit2','real3')):
        audit=load(a.root/audit_name/'report.json')
        assert audit['result']=='independent_observer_inverse_real_passed'
        assert audit['producer_sha256']==sha(a.root/study/'report.json')
    original=load(a.root/'original_real_audit1/report.json')
    assert original['result']=='independent_observer_inverse_original_passed'
    assert original['producer_sha256']==sha(a.root/'real1/report.json')
    weak=load(a.root/'weakbands_audit2/report.json')
    assert weak['result']=='independent_observer_inverse_weakbands_passed' and weak['captures']==54
    rows,solves,inputs=collect(a.root);summary=summarize(rows,solves)
    assert len(rows)==24 and len(solves)==18
    for name in ('original_real_audit1','real_audit1','real_audit2','weakbands_audit2'):
        inputs[str(a.root/name/'report.json')]=sha(a.root/name/'report.json')
    save(a.out/'figure_inputs.json',rows);save(a.out/'solve_inputs.json',solves);save(a.out/'summary.json',summary)
    labels=('Interpolated','Original 4k','Whitened 4k','Correction')
    colors=('#777777','#b7683b','#3483a3','#7858a6')
    x=np.arange(6);short=('1 early','1 mid','1 late','2 early','2 mid','2 late')
    fig,axes=plt.subplots(1,3,figsize=(17,6),layout='constrained')
    for i,attempt in enumerate(('real1','real2','real3')):
        rr=[r for r in solves if r['attempt']==attempt]
        axes[0].semilogy(x,[r['relative_stationarity'] for r in rr],'o-',color=colors[i+1],label=labels[i+1])
    axes[0].axhline(2e-7,color='#555555',ls='--',label='Stationarity gate only')
    axes[0].set_ylabel('Original-space relative gradient');axes[0].set_title('LSMR termination remains a separate gate')
    for name,label,color in zip(VARIANTS,labels,colors):
        rr=[r for r in rows if r['variant']==name]
        axes[1].plot(x,[r['wave_NRMSE'] for r in rr],'o-',color=color,label=label)
        axes[2].plot(x,[r['wave_region_NRMSE'][1] for r in rr],'o-',color=color,label=label)
    axes[1].set_ylabel('Full-waveform NRMSE');axes[1].set_title('Includes weakly observed fragment edges')
    axes[2].set_ylabel('Interior NRMSE');axes[2].set_title('Exclude first/last2048 samples')
    for ax in axes:ax.set_xticks(x,short,rotation=25);ax.grid(alpha=.2);ax.legend(fontsize=8)
    fig.suptitle('Same full finite-Hann inverse objective: all6 frozen V10 sources\nIn-sample reconstruction, not a sustained source or listening score',fontsize=12)
    fig.savefig(a.out/'inverse_convergence.png',dpi=145);plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(17,6),layout='constrained')
    bands=('0-3','3-6','6-8','8-10','10-14','14-21.6')
    for name,label,color in zip(VARIANTS,labels,colors):
        rr=[r for r in rows if r['variant']==name]
        power=np.mean(abs(np.array([r['broad_power_error_dB'] for r in rr])),axis=(0,2))
        stereo=np.mean([r['broad_coherence_error'] for r in rr],axis=0)
        cv=np.mean([r['broad_CV_error'] for r in rr],axis=(0,2))
        for ax,y in zip(axes,(power,stereo,cv)):ax.plot(range(6),y,'o-',color=color,label=label)
    for ax,title in zip(axes,('Band-power MAE (dB)','Complex L/R error','Band-power CV error')):
        ax.set_xticks(range(6),bands,rotation=25);ax.set_xlabel('Band (kHz)');ax.set_ylabel(title);ax.grid(alpha=.2);ax.legend(fontsize=8)
    fig.suptitle('Original-window broadband diagnostics; all sources and regressions retained\nNormalized-coordinate bands; no native48k or physical-source-separation claim',fontsize=12)
    fig.savefig(a.out/'inverse_bands.png',dpi=145);plt.close(fig)
    report=dict(result='observer_inverse_review_ready',rows=24,solves=18,inputs=inputs,
        sources={n:sha(repo/n) for n in sources},
        images={n:sha(a.out/n) for n in ('inverse_convergence.png','inverse_bands.png')},
        figure_inputs_sha256=sha(a.out/'figure_inputs.json'),solve_inputs_sha256=sha(a.out/'solve_inputs.json'),summary_sha256=sha(a.out/'summary.json'))
    save(a.out/'report.json',report);print(report['result'],flush=True)


if __name__=='__main__':
    main()
