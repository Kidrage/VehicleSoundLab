"""Plot all audited slope and fixed-path outcomes; no audible promotion."""
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
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    source=load(a.study/'report.json');audit=load(a.audit/'report.json')
    assert source['result']=='six_source_conditional_slope_evidence_ready'
    assert audit['result']=='independent_conditional_slope_audit_passed' and audit['producer_sha256']==sha(a.study/'report.json')
    a.out.mkdir(parents=True,exist_ok=False);dest=a.out/'exact_sources/tools';dest.mkdir(parents=True)
    shutil.copy2(__file__,dest/Path(__file__).name)
    rows=[h for r in source['cases'] for h in r['harmonics']];quantile=np.linspace(0,1,129)
    paired={}
    for key in source['summary']:
        paired[key]={}
        for after,before in [('density','parent'),('variation','parent'),('variation','density')]:
            delta=np.array([h['stages'][after][key]-h['stages'][before][key] for h in rows])
            paired[key][after+'_vs_'+before]=dict(less=int(np.sum(delta<0)),equal=int(np.sum(delta==0)),greater=int(np.sum(delta>0)))
    keys=['inverse_uniform_slope_bound','inverse_product_slope_bound','path_maximum_step_radians']
    values={key:{stage:np.quantile([h['stages'][stage][key] for h in rows],quantile).tolist()
                 for stage in ['parent','density','variation']} for key in keys}
    save(a.out/'figure_inputs.json',dict(quantiles=quantile.tolist(),values=values,count=len(rows),
        meaning='All frozen harmonic models; input paths are unitless tests, not observed engine motion or audio.'))
    plt.rcParams.update({'font.size':10,'axes.titlesize':12})
    fig,axes=plt.subplots(1,3,figsize=(17,5.2),layout='constrained')
    titles=['Inverse-uniform slope bound','Direct inverse-P slope bound','Maximum step on the same test path']
    ylabels=['rad / unit uniform','rad / normalized P','radians per unitless path step']
    for ax,key,title,ylabel in zip(axes,keys,titles,ylabels):
        for stage,label,color in [('parent','Parent sparse probe','#a64b22'),('density','Density optimized','#2266a0'),('variation','Density + CDF-gradient optimized','#218b5a')]:
            ax.plot(100*quantile,values[key][stage],label=label,color=color,lw=1.4)
        ax.set(xlabel='Harmonic-model percentile (%)',ylabel=ylabel,title=title)
        ax.set_yscale('symlog',linthresh=.001) if key=='inverse_product_slope_bound' else ax.set_yscale('log')
        ax.grid(alpha=.2)
    handles,labels=axes[0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='lower center',bbox_to_anchor=(.5,-.12),ncol=3,fontsize=9)
    fig.suptitle('Conditional phase: bounded maps at the same target do not establish a natural engine time law',fontsize=14)
    path=a.out/'conditional_phase_slopes.png';fig.savefig(path,dpi=150,bbox_inches='tight');plt.close(fig)
    save(a.out/'report.json',dict(result='conditional_slope_figure_ready',
        sources={'tools/review_conditional_phase_slope_v1.py':sha(__file__)},
        inputs={str(a.study/'report.json'):sha(a.study/'report.json'),str(a.audit/'report.json'):sha(a.audit/'report.json')},
        figure_inputs_sha256=sha(a.out/'figure_inputs.json'),images={path.name:sha(path)},
        strict_floating_point_comparison_counts=paired,
        comparison_counts_are_not_perceptual_thresholds=True))
    print(path)


if __name__=='__main__':main()
