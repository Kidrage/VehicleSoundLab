"""Publish audited existing-law preservation metrics and frozen window provenance."""
import argparse
import csv
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load,save,sha


FIELDS=('lag_steps','observed_norm_over_C0','model_norm_over_C0','model_error_over_C0',
    'observed_skew_over_C0','skew_fraction_of_observed_error_squared','shared_error_over_C0',
    'residual_error_over_C0','omitted_cross_error_over_C0')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('workspace','study','audit','out'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from relative_phase_law_v1.provenance import trace
    repo=Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True,exist_ok=False)
    r=dict(result='running',sources={},inputs={})
    try:
        for name in ('tools/review_relative_phase_law_v1.py','tools/audit_relative_phase_law_review_v1.py',
            'tools/relative_phase_law_v1/provenance.py','tools/research_archive_v1.py'):
            dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(repo/name,dest);r['sources'][name]=sha(dest)
        source,proof=load(a.study/'report.json'),load(a.audit/'report.json')
        assert source['result']=='six_saved_relative_phase_laws_measured_without_training'
        assert proof['verification_passed'] and proof['producer_sha256']==sha(a.study/'report.json')
        for path in (a.study/'report.json',a.audit/'report.json'):r['inputs'][str(path)]=sha(path)
        r['provenance']=trace(a.workspace,repo,source['cases'])
        r['inputs'].update(r['provenance']['inputs'])
        with (a.out/'laws.csv').open('w',encoding='utf-8',newline='') as f:
            writer=csv.writer(f);writer.writerow(('case',)+FIELDS+('shared_feature_variance_fraction',))
            for case in source['cases']:
                for row in case['rows']:writer.writerow([case['label']]+[row[k] for k in FIELDS]+[case['metadata']['shared_feature_variance_fraction']])
        with (a.out/'groups.csv').open('w',encoding='utf-8',newline='') as f:
            writer=csv.writer(f);writer.writerow(('case','lag_steps','left','right','observed_RMS_per_entry','model_error_RMS_per_entry'))
            for case in source['cases']:
                for row in case['groups']:writer.writerow([case['label']]+[row[k] for k in ('lag_steps','left','right','observed_RMS_per_entry','model_error_RMS_per_entry')])
        fig,axes=plt.subplots(1,2,figsize=(13,5),constrained_layout=True)
        for case in source['cases']:
            label=case['label'].replace('F3 Fifth ','')
            rows=case['rows'];lags=[v['lag_steps'] for v in rows]
            axes[0].plot(lags,[v['model_error_over_C0'] for v in rows],'o-',label=label)
            axes[1].plot(lags[1:],[100*v['skew_fraction_of_observed_error_squared'] for v in rows[1:]],'o-',label=label)
        axes[0].set_ylabel('Feature covariance error / empirical C0 Frobenius norm')
        axes[0].set_title('Static variance accuracy does not preserve time structure')
        axes[0].legend(fontsize=8)
        axes[1].set_ylabel('Observed covariance error in antisymmetric part (%)')
        axes[1].set_title('Unrepresentable by this symmetric stationary model')
        axes[1].set_ylim(0,105)
        for ax in axes:ax.set_xlabel('Lag in coefficient-row steps');ax.set_xticks((0,1,2,4,8));ax.grid(alpha=.2)
        counts=[case['metadata']['rows'] for case in source['cases']]
        fig.suptitle('Six saved profiles | normal-rank features, not audio errors | '+str(min(counts))+'-'+str(max(counts))+' overlapping rows')
        for ext in ('png','svg'):fig.savefig(a.out/('law_preservation.'+ext),dpi=150)
        plt.close(fig)
        target=next(v for v in source['cases'] if v['label']=='F3 Fifth First Late')
        names=('amplitude_L','amplitude_R','common_phase','relative_phase')
        mats=[]
        for lag in (0,1):
            rows=[v for v in target['groups'] if v['lag_steps']==lag]
            mats.append(np.array([[next(v['model_error_RMS_per_entry'] for v in rows
                if v['left']==left and v['right']==right) for right in names] for left in names]))
        vmax=max(float(v.max()) for v in mats)
        fig,axes=plt.subplots(1,2,figsize=(12,5.5),constrained_layout=True)
        for ax,mat,lag in zip(axes,mats,(0,1)):
            im=ax.imshow(mat,vmin=0,vmax=vmax,cmap='viridis')
            ax.set_xticks(range(4),('Amp L','Amp R','Common phase','Relative phase'),rotation=30,ha='right')
            ax.set_yticks(range(4),('Amp L','Amp R','Common phase','Relative phase'))
            ax.set_title('Lag '+str(lag)+' | RMS per feature-pair entry')
            for i in range(4):
                for j in range(4):ax.text(j,i,format(mat[i,j],'.3f'),ha='center',va='center',color='white' if mat[i,j]<vmax*.55 else 'black')
        fig.colorbar(im,ax=axes,label='Normal-rank covariance error (unweighted by acoustic power)',shrink=.8)
        fig.suptitle('F3 Fifth First Late | feature block errors | no physical-source separation')
        for ext in ('png','svg'):fig.savefig(a.out/('law_feature_groups.'+ext),dpi=150)
        plt.close(fig)
        r.update(result='relative_phase_law_review_published',cases=source['cases'],
            no_new_sound_or_audible_cause_claim=True,new_C1_source_eligible_for_statistics=False,
            no_refit_new_training_C_driver_room_hearing_or_default_change=True,
            next='Known observation-pipeline controls separating overlapping Hann windows/clock/feature transforms from actual source temporal structure, before fitting coupled dynamics.',
            files={p.name:sha(p) for p in sorted(a.out.iterdir()) if p.is_file()})
        save(a.out/'report.json',r)
        print('LAW_REVIEW_PUBLISHED',len(source['cases']),r['provenance']['cases'][0]['maximum_disjoint_analysis_windows'],flush=True)
    except BaseException as error:
        r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
