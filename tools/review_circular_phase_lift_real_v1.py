"""Publish all frozen-path outcomes after independent waveform/observer audit."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load,save,sha


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','study','audit','out'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
        os.environ[name]='2'
    sys.path.insert(0,str(args.workspace/'tools/python_deps'))
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from circular_phase_lift_v1.metrics import collect,summarize
    repo=Path(__file__).resolve().parents[1]
    producer=load(args.study/'report.json')
    audit=load(args.audit/'report.json')
    assert audit['result']=='independent_circular_phase_lift_real_passed'
    assert audit['producer_sha256']==sha(args.study/'report.json')
    args.out.mkdir(parents=True,exist_ok=False)
    names=['tools/review_circular_phase_lift_real_v1.py','tools/circular_phase_lift_v1/metrics.py']
    for name in names:
        dest=args.out/'exact_sources'/name
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(repo/name,dest)
    rows=collect(producer,args.study,args.workspace/'baselines/conditional_phase_time_v1/evidence/real1',
                 args.workspace/'baselines/carrier_transfer_v1/evidence/real1')
    result=summarize(rows)
    save(args.out/'figure_inputs.json',rows)
    save(args.out/'summary.json',result)
    variants=['fixed','relative','parent','density','variation']
    labels=['Fixed','Relative','Cond. parent','Density opt.','Gradient opt.']
    colors=['#777777','#2f80ac','#bf862d','#8b5ba4','#39845d']
    plt.rcParams.update({'font.size':11})
    fig,axes=plt.subplots(1,3,figsize=(17,6),layout='constrained')
    panels=[('broad_power_error_dB','Band power MAE (dB)'),('broad_coherence_error','Complex L/R error'),('broad_CV_error','Band power CV error')]
    for ax,(key,label) in zip(axes,panels):
        for name,text,color in zip(variants,labels,colors):
            chosen=[r for r in rows if r['variant']==name]
            x=[np.mean(abs(np.asarray(r['raw_'+key]))) for r in chosen]
            y=[np.mean(abs(np.asarray(r['lift_'+key]))) for r in chosen]
            ax.scatter(x,y,s=28,color=color,label=text,alpha=.7)
        lo,hi=0,max(ax.get_xlim()[1],ax.get_ylim()[1])
        ax.plot([lo,hi],[lo,hi],color='#555555',ls='--',lw=1)
        ax.set_xlim(lo,hi);ax.set_ylim(lo,hi)
        ax.set_xlabel('Original path: '+label)
        ax.set_ylabel('Lifted path: '+label)
        ax.grid(alpha=.2)
    handles,text=axes[0].get_legend_handles_labels()
    fig.legend(handles,text,loc='outside lower center',ncol=5)
    fig.suptitle('One frozen-path lift rule: compare actual generated waveforms with their original source\nEach point is one source/seed/variant; below diagonal is lower numerical error, not listening acceptance',fontsize=13)
    one=args.out/'phase_lift_observer.png'
    fig.savefig(one,dpi=145);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(15,6),layout='constrained')
    fields=['low_power','rest_power','signed_low_rest_cross','total_power']
    for i,name in enumerate(('parent','density','variation')):
        selected=[r for r in rows if r['variant']==name]
        values=[np.mean([r['delta_broad_'+field+'_over_reference'] for r in selected]) for field in fields]
        axes[0].plot(range(4),values,'o-',label=labels[i+2],color=colors[i+2])
        chosen=[r for r in rows if r['variant']==name]
        raw=np.ravel([r['lift_maximum_raw_step'] for r in chosen])
        lifted=np.ravel([r['lift_maximum_lifted_step'] for r in chosen])
        axes[1].scatter(raw,lifted,s=5,alpha=.3,color=colors[i+2],label=labels[i+2])
    axes[0].set_xticks(range(4),['<3k carriers','Other carriers','Signed cross','Total'],rotation=15)
    axes[0].set_yscale('symlog',linthresh=.001)
    axes[0].margins(y=.15)
    axes[0].axhline(0,color='#555555',lw=.8)
    axes[0].set_ylabel('Lifted minus raw / original source band power')
    axes[0].set_title('Signed whole-band power change; mean of 144 coordinates')
    axes[0].legend(loc='best')
    axes[1].plot([0,2*np.pi],[0,2*np.pi],'--',color='#555555',lw=1)
    axes[1].axhline(np.pi,color='#888888',ls=':',lw=1)
    axes[1].set_xlabel('Original maximum phase step (rad / coordinate sample)')
    axes[1].set_ylabel('Lifted maximum phase step (rad / coordinate sample)')
    axes[1].set_title('All per-partial maxima; no native-time or physical inference')
    for ax in axes:ax.grid(alpha=.2)
    fig.suptitle('Retain signed carrier interference and all phase paths\nReducing a maximum step or total HF power does not establish natural mechanical sound',fontsize=13)
    two=args.out/'phase_lift_signed_phase.png'
    fig.savefig(two,dpi=145);plt.close(fig)
    save(args.out/'report.json',dict(result='circular_phase_lift_review_ready',sources={name:sha(repo/name) for name in names},
        producer_sha256=sha(args.study/'report.json'),audit_sha256=sha(args.audit/'report.json'),
        figure_inputs_sha256=sha(args.out/'figure_inputs.json'),summary_sha256=sha(args.out/'summary.json'),
        images={p.name:sha(p) for p in (one,two)}))
    print(one);print(two)


if __name__=='__main__':
    main()
