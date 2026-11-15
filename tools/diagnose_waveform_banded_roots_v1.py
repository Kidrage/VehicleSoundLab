"""Compare every original known metric entry and distinct native factorizations.

Dense arrays are known-only diagnosis, never a production storage fallback.
This retains strict 2e-11 old-root differences as failures when they fail.
"""
import argparse
import os
import shutil
import sys
from pathlib import Path
from research_archive_v1 import load, save, sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('workspace','study','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    for n in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[n]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy import linalg
    from observer_supported_v1.metric import SupportedMetric
    from waveform_representer_v1.metric import supported_gram
    from waveform_banded_v1.metric import supported_banded
    from waveform_structured_v1.resources import ArrayLedger
    a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_diagnosis.py')
    repo=Path(__file__).resolve().parents[1]
    r=dict(result='running',cases=[],inputs={},sources={})
    source=load(a.study/'report.json');assert source['backend']=='banded' and source['all_qualified']
    r['inputs'][str(a.study/'report.json')]=sha(a.study/'report.json')
    for name in ('tools/observer_supported_v1/metric.py','tools/waveform_representer_v1/metric.py',
                 'tools/waveform_banded_v1/metric.py','tools/waveform_banded_v1/root.py',
                 'tools/waveform_structured_v1/resources.py'):
        path=a.out/'exact_sources'/name;path.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(repo/name,path);r['sources'][name]=sha(path)
    try:
        for case in source['cases']:
            if case['kind']!='Hann':continue
            file=a.study/case['file'];assert sha(file)==case['sha256'];r['inputs'][str(file)]=sha(file)
            with np.load(file) as z:audio=z['audio'];probes=z['metric_probes']
            metric=SupportedMetric(audio,64.)
            dense=supported_gram(metric,order='F');band=supported_banded(metric)
            N=len(dense);S=band.bands.shape[0];maximum=0.;different=0;outside=0
            for d in range(N):
                expected=np.diag(dense,-d)
                if d<S:
                    actual=band.bands[d,:N-d]
                    maximum=max(maximum,float(abs(expected-actual).max()))
                    different+=int(np.count_nonzero(expected!=actual))
                else:outside+=int(np.count_nonzero(expected))
            assert maximum==0 and different==0 and outside==0
            lower=linalg.cholesky(dense,lower=True,overwrite_a=True,check_finite=False)
            root=band.factor(ArrayLedger())
            maximumL=0.;squaredL=0.;totalL=0.
            for d in range(S):
                expected=np.diag(lower,-d);delta=root.L[d,:N-d]-expected
                maximumL=max(maximumL,float(abs(delta).max()))
                squaredL+=float(delta@delta);totalL+=float(expected@expected)
            def rel(x,y):return float(np.linalg.norm(x-y)/max(np.linalg.norm(y),1e-300))
            actions={}
            for name,got,expected in (
                ('apply',root.apply(probes),lower@probes),
                ('transpose',root.transpose(probes),lower.T@probes),
                ('inverse_transpose',root.solve_transpose(probes),
                 linalg.solve_triangular(lower,probes,trans='T',lower=True))):
                actions[name]=rel(got,expected)
            r['cases'].append(dict(label=case['label'],frames=N,bandwidth=S-1,
                all_lower_entries=N*(N+1)//2,original_lower_metric_bitwise_equal=True,
                exact_structural_zero_entries_outside_band=True,
                dense_vs_band_root_max_absolute_difference=maximumL,
                dense_vs_band_root_relative_Frobenius=float(np.sqrt(squaredL/totalL)),
                four_probe_action_relative_differences=actions,
                original_solution_relative_difference=case['baseline_graph_relative_error'],
                qualified_metric_representation=True))
            del dense,lower,root,band,metric
            save(a.out/'report.json',r)
            print('METRIC BITWISE',case['label'],'rootdelta',r['cases'][-1]['dense_vs_band_root_relative_Frobenius'],flush=True)
        assert len(r['cases'])==8
        r.update(result='waveform_banded_original_metrics_diagnosed',all_original_lower_metrics_bitwise_equal=True,
            different_native_root_rounding_observed=True,
            sole_cause_of_strict_Gram_differences_established=False,
            old_root_2e_11_gate_NOT_relabelled_pass=True,real_or_full_or_runtime_qualified=False)
        save(a.out/'report.json',r)
    except BaseException as error:
        r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
