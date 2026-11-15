"""Independent scalar inverse/atom probabilities and conditional edge audit."""
import argparse
import bisect
import math
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','study','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    repo=Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_audit.py')
    report=dict(result='running',cases=0,queries=0,maximum_phase_error_radians=0.)
    try:
        old=load(a.study/'report.json');assert old['result']=='phase_stream_known_ready'
        for name,digest in old['sources'].items():assert sha(repo/name)==sha(a.study/'exact_sources'/name)==digest
        for row in old['cases']:
            path=a.study/row['file'];assert sha(path)==row['sha256']
            with np.load(path) as z:
                table=z['table'];m,d=table.shape
                for j in range(d):
                    values=table[:,j].tolist(); nodes=[0.]+[(i+.5)/m for i in range(m)]+[1.]
                    targets=[values[0]]+values+[values[-1]]
                    cdf,low,high=z[f'cdf_{j}'],z[f'low_{j}'],z[f'high_{j}']
                    assert np.array_equal(cdf,np.tile(nodes,(len(z['knots']),1)))
                    assert np.array_equal(low,targets[:-1]) and np.array_equal(high,targets[1:])
                    assert math.isclose(cdf[0,1],.5/m) and math.isclose(1-cdf[0,-2],.5/m)
                    for i,u in enumerate(z['uniform'][:,j]):
                        # Analytic piecewise-linear quantile with constant tails.
                        at=min(max(bisect.bisect_right(nodes,float(u))-1,0),len(nodes)-2)
                        f=(u-nodes[at])/(nodes[at+1]-nodes[at])
                        truth=targets[at]+f*(targets[at+1]-targets[at])
                        for field in ('original','decoded'):
                            error=abs(float(z[field][i,j])-truth)
                            report['maximum_phase_error_radians']=max(report['maximum_phase_error_radians'],error)
                            assert error<2e-12,(row['name'],field,error)
                        report['queries']+=1
                assert abs(z['original']-z['wrong_no_half_tails']).max()==row['negative_control_error_radians']
                assert abs(z['original']-z['decoded']).max()==row['maximum_phase_error_radians']
            report['cases']+=1
        assert report['cases']==8
        report.update(result='independent_phase_stream_known_passed',producer_sha256=sha(a.study/'report.json'),
            auditor_sha256=sha(__file__),source_audio_read=False)
        save(a.out/'report.json',report);print(report,flush=True)
    except BaseException as e:
        report.update(result='failed',error=repr(e));save(a.out/'report.json',report);raise


if __name__=='__main__':main()
