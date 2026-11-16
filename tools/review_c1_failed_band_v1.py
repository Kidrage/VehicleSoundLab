"""Publish audited failure and same-objective limit, without new audio or fitting."""
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
    a.out.mkdir(parents=True,exist_ok=False)
    r=dict(result='running',sources={},inputs={})
    try:
        shutil.copy2(__file__,a.out/'executed_review.py')
        r['sources']['tools/review_c1_failed_band_v1.py']=sha(__file__)
        source,proof=load(a.study/'report.json'),load(a.audit/'report.json')
        assert proof['verification_passed'] and proof['producer_sha256']==sha(a.study/'report.json')
        packet=a.study/'diagnostic.npz';assert sha(packet)==source['arrays_sha256']
        for path in (a.study/'report.json',a.audit/'report.json',packet):r['inputs'][str(path)]=sha(path)
        with np.load(packet) as f:
            hz=f['virtual_frequency'];reference=f['virtual_reference_Welch_FS2'];error=f['virtual_error_Welch_FS2']
        spectrum=[dict(virtual_Hz=float(hz[k]),reference_L_FS2=float(reference[k,0]),
            reference_R_FS2=float(reference[k,1]),error_L_FS2=float(error[k,0]),error_R_FS2=float(error[k,1]))
            for k in range(len(hz))]
        summary=source['summary'];band_rows=[]
        for family,groups in (('original',summary['original_bands']),('highest_split',summary['highest_band_split'])):
            for k,item in enumerate(groups):
                row=dict(family=family,label=item.get('name',str(k)),bins=item['bins'],NRMSE=item['combined_complex_NRMSE'])
                for key in ('reference_weighted_mass_LR','error_weighted_mass_LR','reference_Welch_FS2_LR','error_Welch_FS2_LR'):
                    for channel,value in zip(('L','R'),item[key]):row[key+'_'+channel]=value
                band_rows.append(row)
        nominal=summary['nominal_original_optimality']
        optimality={k:v for k,v in nominal.items() if isinstance(v,(int,float)) and not isinstance(v,bool)}
        tables={'spectrum.csv':spectrum,'bands.csv':band_rows,'optimality.csv':[optimality]}
        cells=0
        for name,rows in tables.items():
            with (a.out/name).open('w',encoding='utf-8',newline='') as stream:
                writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
            with (a.out/name).open(encoding='utf-8',newline='') as stream:printed=list(csv.DictReader(stream))
            assert len(printed)==len(rows)
            for new,old in zip(printed,rows):
                for key,value in old.items():
                    if isinstance(value,str):assert new[key]==value
                    else:assert float(new[key])==value;cells+=1
        fig,axes=plt.subplots(1,2,figsize=(12,4.7),gridspec_kw={'width_ratios':[1.55,1]},constrained_layout=True)
        for array,label in ((reference,'Reference L+R'),(error,'Error L+R')):
            axes[0].plot(hz/1000,10*np.log10(np.maximum(array.sum(axis=1),1e-300)),label=label,linewidth=1)
        axes[0].axvline(18.432,color='black',linestyle=':',label='Highest carrier centre')
        axes[0].set(xlabel='Virtual-coordinate frequency (kHz)',ylabel='Welch bin contribution (dB FS squared)',
            title='Absolute virtual-coordinate power',xlim=(0,32.768),ylim=(-230,0))
        axes[0].legend(fontsize=8)
        values=[nominal['original_highest_NRMSE'],nominal['exact_same_objective_optimum_NRMSE_lower_bound']]
        axes[1].bar([0,1],values,color=['#3c6e9e','#839db6'],width=.58)
        axes[1].axhline(.02,color='#ae3838',linestyle='--',label='Original strict gate: 0.02')
        axes[1].set_xticks([0,1],['Saved fit','Nominal lower bound\nat same-objective optimum'])
        axes[1].set(ylabel='Highest-band complex NRMSE',ylim=(0,.135),title='More solve accuracy cannot close this gap')
        axes[1].legend(fontsize=8,loc='upper right')
        axes[1].text(.03,.50,'Maximum possible NRMSE change:\n'+format(nominal['maximum_possible_highest_NRMSE_change'],'.3g'),
            transform=axes[1].transAxes,fontsize=9)
        for ax in axes:ax.grid(alpha=.2,axis='y')
        fig.suptitle('Same saved C1 FirstLate | nominal floating-point bound; no audible-cause conclusion',fontsize=11)
        for ext in ('png','svg'):fig.savefig(a.out/('failed_band.'+ext),dpi=150)
        plt.close(fig);ET.parse(a.out/'failed_band.svg')
        r.update(result='c1_failed_band_review_published',CSV_numeric_cells_roundtrip_checked=cells,
            all_published_source_numbers_covered_by_independent_audit=True,SVG_parsed=True,
            nominal_bound_not_interval_certificate=True,new_C1_source_eligible_for_statistics=False,
            no_new_fit_native_reconstruction_audio_C_or_listening=True,
            files={v.name:sha(v) for v in sorted(a.out.iterdir()) if v.is_file()})
        save(a.out/'report.json',r);print(r['result'],cells,flush=True)
    except BaseException as error:r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
