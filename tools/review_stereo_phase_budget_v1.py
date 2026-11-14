"""Publish signed stereo-dependence and observer-window scientific figures."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('workspace','study','audit','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();repo=Path(__file__).resolve().parents[1]
    for n in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[n]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    a.out.mkdir(parents=True,exist_ok=False)
    report=dict(result='running',sources={},inputs={})
    try:
        study=load(a.study/'report.json');audit=load(a.audit/'report.json')
        assert study['result']=='six_source_stereo_budget_and_window_evidence_ready'
        assert audit['result']=='independent_stereo_budget_audit_passed' and audit['producer_sha256']==sha(a.study/'report.json')
        for p in (a.study/'report.json',a.audit/'report.json'):report['inputs'][str(p)]=sha(p)
        fig,axes=plt.subplots(1,2,figsize=(13,5.8))
        items=study['regression_cases'];x=np.arange(len(items));labels=[]
        bottom=np.zeros(len(items));negative=np.zeros(len(items))
        colors=['#6483a5','#d5b158','#b76b63','#6c957a']
        names=[('amplitude_product','Mean amplitude product'),('phase_marginal','Phase marginal'),
               ('association','Amplitude / phase association'),('denominator','Energy normalization')]
        for (key,title),color in zip(names,colors):
            value=np.array([v['signed_projection'][key] for v in items])
            base=np.where(value>=0,bottom,negative)
            axes[0].bar(x,value,.65,bottom=base,label=title,color=color)
            bottom+=np.maximum(value,0);negative+=np.minimum(value,0)
        for item in items:
            label=item['label'].replace('F3 Fifth First ','1 ').replace('F3 Fifth Second ','2 ')
            band=['3–6','6–8','8–10','10–14'][item['band']]
            labels.append(label+'\n'+band+' kHz')
        axes[0].axhline(1,color='#333',lw=.8,ls='--')
        axes[0].set(xticks=x,xticklabels=labels,ylabel='Signed projection onto total complex error',
                    ylim=(-.12,1.08),title='Five regressions versus fixed phase')
        handles,left_labels=axes[0].get_legend_handles_labels()
        fig.legend(handles,left_labels,loc='upper center',bbox_to_anchor=(.27,.93),ncol=2,fontsize=8)
        for offset,key,title,color in [(-.18,'average','Current 12 factors + diagonal','#6483a5'),
                                       (.18,'population_average','Full population Gaussian counterfactual','#b76b63')]:
            values=[]
            for row in study['cases']:
                e=np.array(row[key]['error']);values.append(np.linalg.norm(e,axis=1).mean())
            axes[1].bar(np.arange(6)+offset,values,.35,label=title,color=color)
        axes[1].set(xticks=np.arange(6),xticklabels=['1 early','1 mid','1 late','2 early','2 mid','2 late'],
                    ylabel='Mean absolute complex coherence error',title='Full covariance barely changes the remaining error')
        handles,right_labels=axes[1].get_legend_handles_labels()
        fig.legend(handles,right_labels,loc='upper center',bbox_to_anchor=(.75,.93),fontsize=8)
        for ax in axes:ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
        fig.suptitle('Amplitude / relative-phase association dominates five stereo errors',y=.995,fontsize=13)
        fig.text(.5,.01,'Left terms are signed algebraic projections, NOT source-energy percentages. Right counterfactual is NOT a new preset or timbre result.',ha='center',fontsize=8)
        fig.subplots_adjust(left=.065,right=.985,top=.77,bottom=.21,wspace=.24)
        fig.savefig(a.out/'phase_budget.png',dpi=150);plt.close(fig)
        fig,axes=plt.subplots(3,2,figsize=(12,10),sharex=True,sharey=True)
        lags=np.arange(1,9)
        for row,ax in zip(study['cases'],axes.ravel()):
            source=np.array(row['window']['source_lag1_8'])
            population=np.array(row['window']['population_lag1_8']).mean(axis=0)
            finite=np.array(row['window']['finite_demeaned_lag1_8']).mean(axis=0)
            ax.fill_between(lags,source.min(axis=1),source.max(axis=1),color='#6483a5',alpha=.15,label='Observed L/R/band range')
            ax.plot(lags,source.mean(axis=1),'o-',color='#6483a5',ms=3,label='Observed mean')
            ax.plot(lags,population,'k--',label='White observer: population')
            ax.plot(lags,finite,'o-',color='#b76b63',ms=3,label='White observer: finite-row moments')
            ax.set(title=row['label'].replace('F3 Fifth ',''),xticks=lags,ylim=(-.55,1.05),
                   xlabel='Observation hop (quarter acoustic cycle)',ylabel='Power lag product / variance')
            ax.grid(alpha=.2)
        handles,labels=axes[0,0].get_legend_handles_labels()
        fig.legend(handles,labels,loc='upper center',ncol=2,bbox_to_anchor=(.5,.962),fontsize=9)
        fig.suptitle('Dense Hann overlap creates high correlation even with no physical slow modulation',y=.995,fontsize=13)
        fig.text(.5,.012,'Periodic Hann4096, hop256 in normalized cycle coordinates; real white Gaussian null includes all covariance / pseudocovariance order pairs.\nFinite-row line is a ratio of expected demeaned moments, NOT the expectation of an estimated correlation. It is not a fitted engine model.',ha='center',fontsize=8)
        fig.tight_layout(rect=[0,.065,1,.9]);fig.savefig(a.out/'window_null.png',dpi=150);plt.close(fig)
        sources=['tools/review_stereo_phase_budget_v1.py']
        for n in sources:
            out=a.out/'exact_sources'/n;out.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/n,out);report['sources'][n]=sha(out)
        report.update(result='stereo_budget_figures_ready',images={n:sha(a.out/n) for n in ['phase_budget.png','window_null.png']},
                      heard=False,new_audio=False,parent_hearing_unchanged=True)
        save(a.out/'report.json',report);print(report['result'])
    except BaseException as exc:
        report.update(result='failed',error=repr(exc));save(a.out/'report.json',report);raise


if __name__=='__main__':main()
