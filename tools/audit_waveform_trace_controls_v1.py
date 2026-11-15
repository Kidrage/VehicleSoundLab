"""Independent exact trace against all entries of thirteen small original systems."""
import argparse
import os
import shutil
import sys
from pathlib import Path
from research_archive_v1 import load, save, sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','known','shared','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy import linalg
    from observer_supported_v1.full_oracle import FullOracle
    from observer_supported_v1.audit_oracle import matrices
    from waveform_trace_audit_v1 import root_frobenius
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
    shutil.copy2(__file__,a.out/'executed_audit.py')
    names=('tools/waveform_trace_audit_v1.py','tools/observer_supported_v1/full_oracle.py',
        'tools/observer_supported_v1/audit_oracle.py','tools/observer_complete_v1/audit_oracle.py',
        'tools/observer_frequency_v1/reduced_oracle.py','tools/observer_frequency_v1/audit_oracle.py')
    r=dict(result='running',cases=[],inputs={},sources={})
    try:
        for name in names:
            dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(repo/name,dest);r['sources'][name]=sha(dest)
        for folder in (a.known,a.shared):
            report=load(folder/'report.json');r['inputs'][str(folder/'report.json')]=sha(folder/'report.json')
            for case in report['cases']:
                if case['kind']!='Hann':continue
                path=folder/case['file'];assert sha(path)==case['sha256'];r['inputs'][str(path)]=sha(path)
                with np.load(path) as z:
                    oracle=FullOracle(z['audio'],z['positions'],z['orders'],z['scale'])
                    A,b,Phi,R,count=matrices(z['positions'],z['orders'],z['scale'],z['audio'],oracle.profile)
                    inv=linalg.solve_triangular(np.linalg.cholesky(R).T,np.eye(len(R)))
                    expected=float(np.sqrt(np.sum((A[:count]@inv)**2)+len(R)))
                    trace=root_frobenius(oracle)
                    error=abs(trace['root_Frobenius']-expected)/max(expected,1.)
                    assert error<2e-12,(case['label'],error)
                    r['cases'].append(dict(kind=folder.name,label=case['label'],dense_Frobenius=expected,
                        trace=trace,relative_error=error,qualified=True))
        assert len(r['cases'])==13
        r.update(result='independent_waveform_trace_controls_verified',all_qualified=True,
            maximum_relative_error=max(c['relative_error'] for c in r['cases']),auditor_sha256=sha(__file__))
        save(a.out/'report.json',r);print(r['result'],r['maximum_relative_error'],flush=True)
    except BaseException as error:
        r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
