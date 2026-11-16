"""Recompute publication numbers directly from the saved arrays."""
import argparse
import csv
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','study','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import math
    import numpy as np
    import xml.etree.ElementTree as ET
    a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_audit.py')
    r=dict(result='running')
    try:
        report=load(a.study/'report.json');assert report['result']=='native_observation_review_published'
        repo=Path(__file__).resolve().parents[1]
        for name,digest in report['sources'].items():assert sha(repo/name)==sha(a.study/'exact_sources'/name)==digest
        for name,digest in report['inputs'].items():assert sha(name)==digest
        for name,digest in report['files'].items():assert sha(a.study/name)==digest
        inputs={Path(name).stem:Path(name) for name in report['inputs'] if name.endswith('.npz')}
        with (a.study/'observations.csv').open(encoding='utf-8',newline='') as stream:rows=list(csv.DictReader(stream))
        assert len(rows)==len(report['rows'])==81
        count=0;maximum=0.
        def feature(z):return np.column_stack((z[:,0].real,z[:,0].imag,z[:,1].real,z[:,1].imag))
        def centre(z):
            x=feature(z);return x-np.array([math.fsum(col)/len(x) for col in x.T])
        def rms(z):
            x=centre(z);return math.sqrt(math.fsum(float(v)*float(v) for v in x.flat)/len(x))
        def skew(z):
            x=centre(z);c=np.array([[math.fsum(x[t+8,i]*x[t,j] for t in range(len(x)-8))/(len(x)-8) for j in range(4)] for i in range(4)])
            return float(np.linalg.norm((c-c.T)/2)/.07**2)
        for published,saved in zip(rows,report['rows']):
            case,variant,c=published['case'],published['variant'],int(published['cycles'])
            assert (case,variant,c)==(saved['case'],saved['variant'],saved['cycles'])
            with np.load(inputs[case]) as f:
                z=f[f'{variant}_cycles{c}'][:,63];truth=f[f'truth_{variant}_cycles{c}']
                error=feature(z-truth);bridge=feature(f[f'native_cycles{c}'][:,63]-f[f'query_cycles{c}'][:,63])
                expected=dict(cycles=c,rows=len(z),observed_variation_RMS_FS=rms(z),truth_variation_RMS_FS=rms(truth),
                    envelope_RMSE_FS=math.sqrt(math.fsum(float(v)*float(v) for v in error.flat)/len(z)),
                    native_query_coefficient_RMSE_FS=math.sqrt(math.fsum(float(v)*float(v) for v in bridge.flat)/len(z)),
                    observed_lag8_skew_over_scale_squared=skew(z),truth_lag8_skew_over_scale_squared=skew(truth),
                    prefix40_variation_RMS_FS=rms(z[:40]),hop1024_variation_RMS_FS=rms(z[::4]))
                for name,value in expected.items():
                    assert float(published[name])==saved[name]
                    scale=1. if name.endswith('squared') or name in ('cycles','rows') else .07
                    difference=abs(float(published[name])-value)/scale
                    assert difference<2e-11,(case,variant,c,name,difference)
                    maximum=max(maximum,difference);count+=1
        ET.parse(a.study/'observation_controls.svg')
        r.update(result='independent_native_observation_publication_verified',verification_passed=True,
            producer_sha256=sha(a.study/'report.json'),numeric_cells_independently_recomputed=count,
            maximum_scaled_comparison_error=maximum,SVG_parsed=True)
        save(a.out/'report.json',r);print(r['result'],count,maximum,flush=True)
    except BaseException as error:r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
