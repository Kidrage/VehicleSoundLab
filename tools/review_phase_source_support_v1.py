"""Publish the six audited source traces; preserve coefficient and feature units."""
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
    r=dict(result='running',sources={},inputs={},cases=[])
    try:
        repo=Path(__file__).resolve().parents[1]
        name='tools/review_phase_source_support_v1.py';shutil.copy2(__file__,a.out/'executed_review.py');r['sources'][name]=sha(repo/name)
        source,proof=load(a.study/'report.json'),load(a.audit/'report.json')
        assert proof['verification_passed'] and proof['producer_sha256']==sha(a.study/'report.json')
        for path in (a.study/'report.json',a.audit/'report.json'):r['inputs'][str(path)]=sha(path)
        pair_rows=[];harmonic_rows=[]
        for case in source['cases']:
            label=case['label'];meta=case['metadata'];path=a.study/label/'trace.npz'
            assert sha(path)==case['trace_sha256'];r['inputs'][str(path)]=sha(path)
            for pair in case['pairs']:pair_rows.append(dict(case=label,**pair))
            with np.load(path) as f:
                for h in range(288):
                    harmonic_rows.append(dict(case=label,harmonic=h+1,
                        leading_pair_feature_loading=float(f['harmonic_load'][h]),
                        mean_coefficient_power_FS2=float(f['mean_coefficient_power'][h]),
                        variation_coefficient_power_FS2=float(f['variation_coefficient_power'][h]),
                        nominal_frequency_Hz=(h+1)*meta['renderer_root_Hz'],
                        observed_clock_frequency_min_Hz=(h+1)*meta['observed_acoustic_root_Hz_min'],
                        observed_clock_frequency_max_Hz=(h+1)*meta['observed_acoustic_root_Hz_max']))
            r['cases'].append(dict(label=label,**meta))
        tables={'pairs.csv':pair_rows,'harmonics.csv':harmonic_rows}
        cells=0
        for name,rows in tables.items():
            with (a.out/name).open('w',encoding='utf-8',newline='') as stream:
                writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
            with (a.out/name).open(encoding='utf-8',newline='') as stream:read=list(csv.DictReader(stream))
            assert len(read)==len(rows)
            for printed,original in zip(read,rows):
                assert printed['case']==original['case']
                for key,value in original.items():
                    if key!='case':assert float(printed[key])==value;cells+=1
        cases=r['cases'];labels=[c['label'].replace('F3 Fifth ','').replace(' ','\n') for c in cases]
        fig,axes=plt.subplots(1,2,figsize=(13,5),constrained_layout=True)
        x=np.arange(6)
        axes[0].bar(x-.18,[100*c['top8_feature_loading_variation_coefficient_power_fraction'] for c in cases],width=.36,label='Top 8 by leading feature-pair loading')
        axes[0].bar(x+.18,[100*c['top8_variation_coefficient_power_fraction'] for c in cases],width=.36,label='Top 8 by coefficient variation power')
        axes[0].set_yscale('log');axes[0].set_ylim(.01,160);axes[0].set_xticks(x,labels)
        axes[0].set_ylabel('Fraction of observed coefficient variation power (%)')
        axes[0].set_title('Feature loading is not a source-power ranking');axes[0].legend(fontsize=7)
        for case in source['cases']:
            with np.load(a.study/case['label']/'trace.npz') as f:times=f['physical_centers']
            actual=np.diff(times);assumed=case['metadata']['renderer_step_seconds']
            axes[1].plot((times[1:]+times[:-1])/2-times[0],100*(actual/assumed-1),label=case['label'].replace('F3 Fifth ',''))
        axes[1].set(xlabel='Time from first original observation centre (s)',
            ylabel='Observed interval / fixed renderer interval - 1 (%)',
            title='Fixed latent node time differs from source observation time')
        axes[1].legend(fontsize=7)
        for ax in axes:ax.grid(alpha=.2,axis='y')
        fig.suptitle('Six saved F3 contexts | coefficient-line proxies, not broadband energy or audible-cause proof')
        for ext in ('png','svg'):fig.savefig(a.out/('source_support.'+ext),dpi=150)
        plt.close(fig);ET.parse(a.out/'source_support.svg')
        r.update(result='saved_phase_source_support_review_published',CSV_numeric_cells_roundtrip_checked=cells,
            all_source_numbers_covered_by_prior_independent_audit=True,SVG_parsed=True,
            no_training_audio_or_C_change=True,new_C1_source_eligible_for_statistics=False,
            files={p.name:sha(p) for p in sorted(a.out.iterdir()) if p.is_file()})
        save(a.out/'report.json',r);print(r['result'],cells,flush=True)
    except BaseException as error:r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
