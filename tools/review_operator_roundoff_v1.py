"""Publish audited numerical errors in explicit absolute and relative units."""
import argparse
import csv
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
    import xml.etree.ElementTree as ET
    a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_review.py')
    r=dict(result='running',sources={'tools/review_operator_roundoff_v1.py':sha(__file__)},inputs={})
    try:
        source=load(a.study/'report.json');proof=load(a.audit/'report.json')
        assert proof['verification_passed'] and proof['producer_sha256']==sha(a.study/'report.json')
        for path in (a.study/'report.json',a.audit/'report.json'):r['inputs'][str(path)]=sha(path)
        group_rows=[];gradient_rows=[]
        for case in source['cases']:
            name=case['name'];path=a.study/name/'roundoff.npz';assert sha(path)==case['packet_sha256'];r['inputs'][str(path)]=sha(path)
            original=next(Path(p) for p in source['inputs'] if Path(p).parent.name==name and Path(p).name=='operators.npz')
            assert sha(original)==source['inputs'][str(original)];r['inputs'][str(original)]=sha(original)
            with np.load(path) as f:saved={key:f[key] for key in f.files}
            with np.load(original) as f:z={key:f[key] for key in f.files}
            for g in range(7):
                reference=z['target_'+str(g)];peak=float(abs(reference).max())
                error=float(abs(saved['group_'+str(g)+'_total']).max())
                comp_error=float(abs(saved['group_'+str(g)+'_compensated']-reference).max())
                group_rows.append(dict(case=name,group=g,reference_peak=peak,error_peak=error,
                    peak_relative_error=error/peak if peak else 0.,compensated_error_peak=comp_error,
                    source_component_peak=float(abs(saved['group_'+str(g)+'_source']).max()),
                    column_component_peak=float(abs(saved['group_'+str(g)+'_column']).max())))
            grad=saved['gradient_compensated'];den=float(abs(grad).max())
            fft_error=float(abs(z['gradient']-grad).max());dense_error=float(abs(saved['gradient_dense_naive']-grad).max())
            gradient_rows.append(dict(case=name,reference_peak=den,FFT_path_error_peak=fft_error,
                dense_reduction_error_peak=dense_error,FFT_path_relative_error=fft_error/den if den else 0.,
                dense_reduction_relative_error=dense_error/den if den else 0.))
        cells=0
        for name,rows in (('groups.csv',group_rows),('gradients.csv',gradient_rows)):
            with (a.out/name).open('w',encoding='utf-8',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
            with (a.out/name).open(encoding='utf-8',newline='') as f:printed=list(csv.DictReader(f))
            assert len(printed)==len(rows)
            for old,new in zip(rows,printed):
                assert new['case']==old['case']
                for key,value in old.items():
                    if key!='case':assert float(new[key])==value;cells+=1
        fig,axes=plt.subplots(1,2,figsize=(12,4.8),constrained_layout=True)
        names=[v['case'] for v in gradient_rows if v['reference_peak']>0]
        for name in names:
            values=[v for v in group_rows if v['case']==name and v['group']>0]
            axes[0].scatter([v['reference_peak'] for v in values],[v['error_peak'] for v in values],label=name.replace('small_',''),s=28)
        x=np.logspace(-3,2,100);axes[0].plot(x,2e-11*x,color='black',linestyle='--',label='Unchanged check: relative 2e-11')
        axes[0].set(xscale='log',yscale='log',xlabel='Target group peak (weighted coordinate units)',
            ylabel='Absolute path difference (same weighted units)',title='Weak outputs amplify relative discrepancies')
        axes[0].legend(fontsize=7)
        values=[v for v in gradient_rows if v['reference_peak']>0];x=np.arange(len(values))
        axes[1].bar(x-.18,[v['FFT_path_relative_error'] for v in values],width=.36,label='FFT path vs exact rounded-matrix reduction')
        axes[1].bar(x+.18,[v['dense_reduction_relative_error'] for v in values],width=.36,label='Dense BLAS vs exact rounded-matrix reduction')
        axes[1].axhline(2e-11,color='black',linestyle='--',label='Original numerical check')
        axes[1].set_xticks(x,[v['case'].replace('small_','').replace('_','\n') for v in values])
        axes[1].set(yscale='log',ylabel='Maximum relative gradient difference',title='Compensated summation is not the main missing fix',ylim=(1e-16,2e-10))
        axes[1].legend(fontsize=7,loc='lower left')
        for ax in axes:ax.grid(alpha=.2,axis='y')
        fig.suptitle('Saved known inputs | numerical consistency only; no vehicle or audible-cause evidence',fontsize=11)
        for ext in ('png','svg'):fig.savefig(a.out/('roundoff.'+ext),dpi=150)
        plt.close(fig);ET.parse(a.out/'roundoff.svg')
        r.update(result='saved_known_roundoff_review_published',CSV_numeric_cells_roundtrip_checked=cells,
            SVG_parsed=True,all_inputs_previously_independently_audited=True,
            original_failed_checks_and_whole_operator_qualification_FALSE_unchanged=True,
            files={v.name:sha(v) for v in sorted(a.out.iterdir()) if v.is_file()})
        save(a.out/'report.json',r);print(r['result'],cells,flush=True)
    except BaseException as error:r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
