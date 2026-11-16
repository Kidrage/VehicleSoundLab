"""Verify every published CSV value and original overlapping-window provenance."""
import argparse
import csv
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('workspace','study','out'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    import xml.etree.ElementTree as ET
    repo=Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True,exist_ok=False)
    shutil.copy2(__file__,a.out/'executed_audit.py')
    r=dict(result='running')
    try:
        report=load(a.study/'report.json');assert report['result']=='relative_phase_law_review_published'
        for name,digest in report['sources'].items():assert sha(repo/name)==sha(a.study/'exact_sources'/name)==digest
        for name,digest in report['inputs'].items():assert sha(name)==digest
        for name,digest in report['files'].items():assert sha(a.study/name)==digest
        fields=('lag_steps','observed_norm_over_C0','model_norm_over_C0','model_error_over_C0',
            'observed_skew_over_C0','skew_fraction_of_observed_error_squared','shared_error_over_C0',
            'residual_error_over_C0','omitted_cross_error_over_C0')
        cells=0
        with (a.study/'laws.csv').open(encoding='utf-8',newline='') as f:
            rows=list(csv.reader(f));assert len(rows)==31 and len(rows[0])==11
        index=1
        for case in report['cases']:
            for value in case['rows']:
                row=rows[index];index+=1;assert row[0]==case['label']
                expected=[value[k] for k in fields]+[case['metadata']['shared_feature_variance_fraction']]
                assert len(row[1:])==len(expected)
                for text,number in zip(row[1:],expected):assert float(text)==number;cells+=1
        with (a.study/'groups.csv').open(encoding='utf-8',newline='') as f:
            rows=list(csv.DictReader(f));assert len(rows)==480
        index=0
        for case in report['cases']:
            for value in case['groups']:
                row=rows[index];index+=1
                assert (row['case'],row['left'],row['right'])==(case['label'],value['left'],value['right'])
                for key in ('lag_steps','observed_RMS_per_entry','model_error_RMS_per_entry'):
                    assert float(row[key])==value[key];cells+=1
        # Independently recover window starts/centres from frozen source arrays.
        base=a.workspace/'baselines/coefficient_geometry_v1/evidence/real1'
        for row in report['provenance']['cases']:
            with np.load(base/row['label']/'source.npz') as f:positions=f['positions']
            count=len(positions);starts=list(range(0,count-4096+1,256))
            case=next(v for v in report['cases'] if v['label']==row['label'])
            assert len(starts)==row['coefficient_rows']==case['metadata']['rows']
            assert row['window_overlap_fraction']==15/16 and row['maximum_disjoint_analysis_windows']==count//4096
            centres=[float(positions[s+2048]) for s in starts]
            delta=[centres[j+1]-centres[j] for j in range(len(centres)-1)]
            spans=[float(positions[s+4095])-float(positions[s]) for s in starts]
            assert (min(delta),max(delta),min(spans),max(spans))==(
                row['observed_center_step_seconds_min'],row['observed_center_step_seconds_max'],
                row['observed_window_support_seconds_min'],row['observed_window_support_seconds_max'])
        for name in ('law_preservation.svg','law_feature_groups.svg'):ET.parse(a.study/name)
        r.update(result='independent_relative_phase_law_publication_verified',verification_passed=True,
            producer_sha256=sha(a.study/'report.json'),CSV_numeric_cells_bitwise_checked=cells,
            provenance_cases_independently_checked=6,SVG_parsed=True,
            no_audible_or_physical_cause_claim=True,no_training_or_C_or_source_change=True)
        save(a.out/'report.json',r);print(r['result'],cells,flush=True)
    except BaseException as error:r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
