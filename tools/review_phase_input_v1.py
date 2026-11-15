"""Publish all anchored path results after independent waveform verification."""
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
    from phase_input_paths_v1.metrics import collect,summarize,DECODERS,COUNTERFACTUALS
    repo=Path(__file__).resolve().parents[1]
    audit=load(a.audit/'report.json');assert audit['result']=='independent_phase_input_real_passed' and audit['producer_sha256']==sha(a.study/'report.json')
    a.out.mkdir(parents=True,exist_ok=False)
    sources=('tools/review_phase_input_v1.py','tools/phase_input_paths_v1/metrics.py')
    for name in sources:
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest)
    rows,budgets=collect(load(a.study/'report.json'),a.study,a.workspace/'baselines/conditional_phase_time_v1/evidence/real1')
    assert len(rows)==216 and len(budgets)==54
    result=summarize(rows,budgets);save(a.out/'figure_inputs.json',dict(rows=rows,budgets=budgets));save(a.out/'summary.json',result)
    colors=('#bf862d','#8b5ba4','#39845d');names=('Parent','Density opt.','Gradient opt.');xlabels=('Both fixed','Only P varies','Only U varies','Both vary')
    plt.rcParams.update({'font.size':10})
    fig,axes=plt.subplots(1,3,figsize=(17,6),layout='constrained')
    for ax,(key,label) in zip(axes,(('broad_power_error_dB','Band power MAE (dB)'),('broad_coherence_error','Complex L/R error'),('broad_CV_error','Band power CV error'))):
        for i,(decoder,name,color) in enumerate(zip(DECODERS,names,colors)):
            means=[]
            for j,cf in enumerate(COUNTERFACTUALS):
                y=[np.mean(abs(np.asarray(r[key]))) for r in rows if r['decoder']==decoder and r['counterfactual']==cf]
                x=j+(i-1)*.16;ax.scatter(np.full(len(y),x)+np.linspace(-.035,.035,len(y)),y,color=color,s=13,alpha=.45);means.append(np.mean(y))
            ax.plot(np.arange(4)+(i-1)*.16,means,'o-',color=color,label=name)
        ax.set_xticks(range(4),xlabels,rotation=18);ax.set_ylabel(label);ax.grid(alpha=.2)
    h,t=axes[0].get_legend_handles_labels();fig.legend(h,t,loc='outside lower center',ncol=3)
    fig.suptitle('Declared anchors P=1, U=0.5: all 6 frozen sources x 3 saved paths x 3 decoders\nOriginal amplitude/common phase in every branch; counterfactuals are not audible presets',fontsize=13)
    one=a.out/'input_paths_observer.png';fig.savefig(one,dpi=145);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(17,6),layout='constrained')
    termlabels=('B self','P self','U self','I self','B x P','B x U','B x I','P x U','P x I','U x I','Total')
    for decoder,name,color in zip(DECODERS,names,colors):
        signed=result['signed_budgets'][decoder]
        values=signed['broad_self_power_mean_over_reference']+signed['broad_signed_pairs_mean_over_reference']+[signed['broad_total_power_mean_over_reference']]
        axes[0].plot(range(11),values,'o-',color=color,label=name)
        values=[result['decoders'][decoder][cf]['maximum_phase_step_quantiles'][2] for cf in COUNTERFACTUALS]
        axes[1].plot(range(4),values,'o-',color=color,label=name)
    axes[0].set_yscale('symlog',linthresh=.01);axes[0].axhline(0,color='#555555',lw=.8);axes[0].margins(y=.16)
    axes[0].set_xticks(range(11),termlabels,rotation=35,ha='right');axes[0].set_ylabel('Mean / original band-channel power')
    axes[0].set_title('All signed wave terms: B + P + U + I = joint')
    axes[1].set_xticks(range(4),xlabels,rotation=18);axes[1].set_ylabel('Median per-partial maximum rad / coordinate sample')
    axes[1].set_title('Temporal phase change, not physical RPM')
    for ax in axes:ax.grid(alpha=.2)
    h,t=axes[0].get_legend_handles_labels();fig.legend(h,t,loc='outside lower center',ncol=3)
    fig.suptitle('Exact wave differences preserve nonlinear interaction and signed interference\nAnchor-dependent finite decomposition; no physical contribution percentages or listening claims',fontsize=13)
    two=a.out/'input_paths_signed_phase.png';fig.savefig(two,dpi=145);plt.close(fig)
    save(a.out/'report.json',dict(result='phase_input_review_ready',sources={name:sha(repo/name) for name in sources},
        producer_sha256=sha(a.study/'report.json'),audit_sha256=sha(a.audit/'report.json'),summary_sha256=sha(a.out/'summary.json'),
        figure_inputs_sha256=sha(a.out/'figure_inputs.json'),images={p.name:sha(p) for p in (one,two)}))
    print(one);print(two)


if __name__=='__main__':main()
