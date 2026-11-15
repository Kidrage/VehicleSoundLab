"""Publish finite paired stream/mapping results only after independent audit."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','study','audit','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from phase_stream_control_v1.metrics import collect,summarize,VARIANTS,FIELDS
    repo=Path(__file__).resolve().parents[1]
    audit=load(a.audit/'report.json');assert audit['result']=='independent_phase_stream_real_passed'
    assert audit['producer_sha256']==sha(a.study/'report.json')
    a.out.mkdir(parents=True,exist_ok=False)
    source_names=('tools/review_phase_stream_v1.py','tools/phase_stream_control_v1/metrics.py')
    for name in source_names:
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest)
    inputs={}
    rows=collect(load(a.study/'report.json'),a.study,a.workspace/'baselines/conditional_phase_time_v1/evidence/real1',
        a.workspace/'baselines/carrier_transfer_v1',inputs)
    assert len(rows)==108
    summary=summarize(rows);save(a.out/'figure_inputs.json',rows);save(a.out/'summary.json',summary)
    labels=('Fixed','Original relative','Independent marginal','Conditional parent','Density opt.','Gradient opt.')
    colors=('#888888','#2f80ac','#ce6d33','#af9b38','#8b5ba4','#39845d')
    plt.rcParams.update({'font.size':10})
    fig,axes=plt.subplots(1,3,figsize=(17,6),layout='constrained')
    for ax,(key,ylabel) in zip(axes,(('broad_power_error_dB','Band power MAE (dB)'),('broad_coherence_error','Complex L/R error'),('broad_CV_error','Band power CV error'))):
        for j,(name,color) in enumerate(zip(VARIANTS,colors)):
            y=[np.mean(abs(np.asarray(r[key]))) for r in rows if r['variant']==name]
            ax.scatter(np.full(len(y),j)+np.linspace(-.14,.14,len(y)),y,color=color,s=22,alpha=.7)
            ax.plot([j-.24,j+.24],[np.mean(y)]*2,color=color,lw=3)
        ax.set_xticks(range(6),labels,rotation=28,ha='right');ax.set_ylabel(ylabel);ax.grid(axis='y',alpha=.2)
    fig.suptitle('Original marginal with saved independent phase stream: all 6 sources x 3 seeds\nSame amplitudes/common phase; normalized-coordinate observer results, not listening scores',fontsize=13)
    one=a.out/'stream_observer.png';fig.savefig(one,dpi=145);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(15,6),layout='constrained')
    comparisons=('independent_marginal_minus_relative','parent_minus_independent_marginal','density_minus_independent_marginal','variation_minus_independent_marginal')
    pair_labels=('Stream change','Parent mapping','Density mapping','Gradient mapping')
    for i,(key,label) in enumerate(zip(comparisons,pair_labels)):
        values=[summary['paired'][key]['broad_signed_change_'+field]['mean'] for field in FIELDS]
        axes[0].plot(range(4),values,'o-',label=label)
    axes[0].axhline(0,color='#555555',lw=.8);axes[0].set_yscale('symlog',linthresh=.01)
    axes[0].set_xticks(range(4),['<3k carriers','Other carriers','Signed cross','Total'],rotation=15)
    axes[0].set_ylabel('Paired change / original source band-channel power');axes[0].margins(y=.18)
    axes[0].set_title('Signed interference retained; not physical energy shares')
    for i,name in enumerate(VARIANTS[1:]):
        x=np.ravel([r['maximum_relative_phase_step'] for r in rows if r['variant']==name])
        q=np.quantile(x,[0,.25,.5,.75,1]);axes[1].plot(range(5),q,'o-',label=labels[i+1])
    axes[1].set_xticks(range(5),['Min','Q1','Median','Q3','Max']);axes[1].set_ylabel('Per-partial maximum rad / coordinate sample')
    axes[1].set_title('No new phase unwrap, rate or strength')
    for ax in axes:ax.grid(alpha=.2)
    handles,text=axes[0].get_legend_handles_labels();fig.legend(handles,text,loc='outside lower left',ncol=2)
    handles,text=axes[1].get_legend_handles_labels();fig.legend(handles,text,loc='outside lower right',ncol=3)
    fig.suptitle('Separate finite stream replacement from conditional decoding\nAll comparisons preserve the exact saved amplitude/common-phase paths',fontsize=13)
    two=a.out/'stream_signed_phase.png';fig.savefig(two,dpi=145);plt.close(fig)
    save(a.out/'report.json',dict(result='phase_stream_review_ready',sources={name:sha(repo/name) for name in source_names},
        inputs=inputs,producer_sha256=sha(a.study/'report.json'),audit_sha256=sha(a.audit/'report.json'),
        summary_sha256=sha(a.out/'summary.json'),figure_inputs_sha256=sha(a.out/'figure_inputs.json'),
        images={p.name:sha(p) for p in (one,two)}))
    print(one);print(two)


if __name__=='__main__':main()
