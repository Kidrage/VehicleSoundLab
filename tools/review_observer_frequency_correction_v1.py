"""All36 outcomes plus solver and independent optimality bounds; no audio page."""
import argparse,os,shutil,sys
from pathlib import Path
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('workspace','original-review','study','study-audit','optimality','optimality-audit','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    for n in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[n]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from observer_frequency_v1.correction_metrics import collect,summarize,VARIANTS
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
    audit=load(a.study_audit/'report.json');assert audit['result']=='independent_observer_frequency_correction_real_passed' and audit['producer_sha256']==sha(a.study/'report.json')
    gap=load(a.optimality/'report.json');ga=load(a.optimality_audit/'report.json')
    assert gap['result']=='observer_frequency_optimality_all6_measured' and ga['result']=='independent_observer_frequency_optimality_real_passed'
    assert ga['producer_sha256']==sha(a.optimality/'report.json')
    rows,solves,inputs=collect(a.original_review,a.study);summary=summarize(rows,solves)
    summary['additional_gap_passed']=gap['gap_passed'];summary['additional_gap_not_original_stop_gate']=True
    for path in (a.study_audit/'report.json',a.optimality/'report.json',a.optimality_audit/'report.json'):inputs[str(path)]=sha(path)
    for n,v in dict(figure_inputs=rows,solve_inputs=solves,gap_inputs=gap['cases'],summary=summary).items():save(a.out/(n+'.json'),v)
    sources=('tools/review_observer_frequency_correction_v1.py','tools/observer_frequency_v1/correction_metrics.py','tools/observer_complete_v1/metrics.py')
    for n in sources:
        dest=a.out/'exact_sources'/n;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/n,dest)
    names=('Interpolation','Old harmonic4k','Old correction','Global wave4k','Shared metric4k','Block correction')
    colors=('#999999','#b97545','#916bb0','#347e9e','#408c50','#bd3459')
    bands=('0-3','3-6','6-8','8-10','10-14','14-21.6')
    fig,axes=plt.subplots(1,3,figsize=(17,6),layout='constrained')
    for tag,label,color in zip(VARIANTS,names,colors):
        rr=[r for r in rows if r['variant']==tag]
        values=(np.mean(abs(np.array([r['broad_power_error_dB'] for r in rr])),axis=(0,2)),
            np.mean([r['broad_coherence_error'] for r in rr],axis=0),np.mean([r['broad_CV_error'] for r in rr],axis=(0,2)))
        for ax,y in zip(axes,values):ax.plot(range(6),y,'o-',label=label,color=color)
    for ax,title in zip(axes,('Band-power MAE (dB)','Complex L/R error','Band-power CV error')):
        ax.set_xticks(range(6),bands,rotation=25);ax.set_xlabel('Band (kHz)');ax.set_ylabel(title);ax.grid(alpha=.2);ax.legend(fontsize=7)
    fig.suptitle('Same weighted objective, saved-solution block correction: all6 local V10 windows\nAll original baselines retained; in-sample inference, not sustained synthesis or a listening score',fontsize=12)
    fig.savefig(a.out/'correction_bands.png',dpi=145);plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(17,6),layout='constrained');x=np.arange(6);short=('1 early','1 mid','1 late','2 early','2 mid','2 late')
    for tag,label,color in (('weighted','Saved4k',colors[4]),('block_refined','Block correction',colors[5])):
        rr=[r for r in rows if r['variant']==tag];axes[0].semilogy(x,[r['wave_NRMSE'] for r in rr],'o-',label=label,color=color)
    for k,label,color in (('initial_relative_stationarity','Saved4k',colors[4]),('relative_stationarity','Block correction',colors[5])):
        axes[1].semilogy(x,[s[k] for s in solves],'o-',label=label,color=color)
    axes[1].axhline(2e-7,ls='--',color='#444444',label='Gradient gate; stop also required')
    for tag,label,color in (('initial','Saved4k',colors[4]),('block_refined','Block correction',colors[5])):
        axes[2].semilogy(x,[c['variants'][tag]['certificate']['relative_gap_upper_bound'] for c in gap['cases']],'o-',label=label,color=color)
    axes[2].axhline(1e-6,ls='--',color='#444444',label='Additional relative-gap gate (+ absolute1e-10)')
    for ax,title in zip(axes,('Whole waveform NRMSE','Original-space relative gradient','Primal/dual gap upper bound / objective')):
        ax.set_xticks(x,short,rotation=25);ax.set_ylabel(title);ax.grid(alpha=.2);ax.legend(fontsize=7)
    fig.suptitle('Lower gradient is insufficient: original LSMR stops and independent convex gap retained\nA gap bound is numerical uncertainty about this regularized optimum, not measured sound error',fontsize=12)
    fig.savefig(a.out/'correction_convergence.png',dpi=145);plt.close(fig)
    r=dict(result='observer_frequency_correction_review_ready',rows=36,solves=6,gap_records=12,inputs=inputs,
        sources={n:sha(repo/n) for n in sources},images={n:sha(a.out/n) for n in ('correction_bands.png','correction_convergence.png')},
        **{n+'_sha256':sha(a.out/(n+'.json')) for n in ('figure_inputs','solve_inputs','gap_inputs','summary')})
    save(a.out/'report.json',r);print(r['result'],flush=True)


if __name__=='__main__':main()
