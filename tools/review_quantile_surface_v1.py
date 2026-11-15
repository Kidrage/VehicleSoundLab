"""Publish every quantile-law result, including circular-moment regressions."""
import argparse,os,shutil,sys
from pathlib import Path
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('workspace','study','audit','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    for n in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[n]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from quantile_surface_v1.metrics import collect,summarize,VARIANTS,NEW,FIELDS
    repo=Path(__file__).resolve().parents[1]
    audit=load(a.audit/'report.json');assert audit['result']=='independent_quantile_surface_real_passed'
    assert audit['producer_sha256']==sha(a.study/'report.json')
    for name in ('phase_stream_control_v1','conditional_phase_time_v1'):
        assert sha(a.workspace/'baselines'/name/'manifest.json')==load(repo/f'research/{name}_summary.json')['manifest_sha256']
    a.out.mkdir(parents=True,exist_ok=False);inputs={}
    sources=('tools/review_quantile_surface_v1.py','tools/quantile_surface_v1/metrics.py')
    for name in sources:
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest)
    rows,moments,old_summary=collect(a.workspace,a.study,inputs);summary=summarize(rows,moments)
    # Previously audited aggregate values must survive the extension literally.
    for name,value in old_summary['variants'].items():assert summary['variants'][name]==value
    for name,value in old_summary['paired'].items():assert summary['paired'][name]==value
    save(a.out/'figure_inputs.json',rows);save(a.out/'moment_inputs.json',moments);save(a.out/'summary.json',summary)
    labels=('Fixed','Relative','Independent\nmarginal','CDF parent','CDF density','CDF gradient','Q parent','Q density','Q gradient')
    colors=('#888888','#2f80ac','#ce6d33','#af9b38','#8b5ba4','#39845d','#a83e48','#5064ad','#26a093')
    plt.rcParams.update({'font.size':10})
    fig,axes=plt.subplots(1,3,figsize=(19,6.5),layout='constrained')
    for ax,(key,title) in zip(axes,(('broad_power_error_dB','Band power MAE (dB)'),('broad_coherence_error','Complex L/R error'),('broad_CV_error','Band power CV error'))):
        for j,(name,c) in enumerate(zip(VARIANTS,colors)):
            y=[np.mean(abs(np.asarray(r[key]))) for r in rows if r['variant']==name]
            ax.scatter(j+np.linspace(-.15,.15,18),y,color=c,s=17,alpha=.65);ax.plot([j-.24,j+.24],[np.mean(y)]*2,color=c,lw=3)
        ax.set_xticks(range(9),labels,rotation=45,ha='right');ax.set_ylabel(title);ax.grid(axis='y',alpha=.2)
    fig.suptitle('New row-quantile interpolation: all 6 frozen sources x 3 saved streams\nAll162 outcomes; same amplitudes/common phase/U, original observer; not listening scores',fontsize=13)
    one=a.out/'quantile_observer.png';fig.savefig(one,dpi=145);plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(19,6.5),layout='constrained')
    for name,color in zip(VARIANTS[3:],colors[3:]):
        key=name+'_minus_independent_marginal';values=[summary['paired'][key]['broad_signed_change_'+f]['mean'] for f in FIELDS]
        axes[0].plot(range(4),values,'o-',color=color,label=labels[VARIANTS.index(name)])
        x=np.ravel([r['maximum_relative_phase_step'] for r in rows if r['variant']==name]);axes[1].plot(range(5),np.quantile(x,[0,.25,.5,.75,1]),'o-',color=color)
    axes[0].axhline(0,color='#555555',lw=.7);axes[0].set_yscale('symlog',linthresh=.01);axes[0].margins(y=.18)
    axes[0].set_xticks(range(4),['Low carriers','Other carriers','Signed cross','Total'],rotation=18);axes[0].set_ylabel('Change / source band-channel power')
    axes[0].set_title('Signed budget vs independent marginal')
    axes[1].set_xticks(range(5),['Min','Q1','Median','Q3','Max']);axes[1].set_ylabel('Per-partial maximum rad / coordinate sample');axes[1].set_title('Original phase branch; no extra unwrap')
    for name in NEW:
        x=np.sort(np.concatenate([np.asarray(r['loss']).ravel() for r in moments if r['variant']==name]));axes[2].plot(x,np.linspace(0,1,len(x)),color=colors[VARIANTS.index(name)],label=labels[VARIANTS.index(name)])
    axes[2].set_xlabel('Absolute circular-moment change');axes[2].set_ylabel('Unweighted midpoint fraction');axes[2].set_title('Changed distributions explicitly retained')
    for ax in axes:ax.grid(alpha=.2)
    handles,text=axes[0].get_legend_handles_labels();fig.legend(handles,text,loc='outside lower center',ncol=6)
    fig.suptitle('Temporal smoothness, signed spectral transfer and conditional-moment cost\nNormalized-coordinate diagnostics; midpoint geometry is not a material probability distribution',fontsize=13)
    two=a.out/'quantile_tradeoffs.png';fig.savefig(two,dpi=145);plt.close(fig)
    save(a.out/'report.json',dict(result='quantile_surface_review_ready',sources={n:sha(repo/n) for n in sources},inputs=inputs,
        producer_sha256=sha(a.study/'report.json'),audit_sha256=sha(a.audit/'report.json'),
        summary_sha256=sha(a.out/'summary.json'),figure_inputs_sha256=sha(a.out/'figure_inputs.json'),moment_inputs_sha256=sha(a.out/'moment_inputs.json'),
        images={q.name:sha(q) for q in (one,two)}))
    print(one);print(two)


if __name__=='__main__':main()
