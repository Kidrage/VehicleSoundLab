"""Known-first matched-marginal decoder equivalence, including endpoint atoms."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import save, sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a=p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy.special import ndtri, ndtr
    from phase_stream_control_v1.fixtures import cases, uniforms
    from phase_stream_control_v1.marginal import cells
    from radial_copula_v1.quantiles import lookup
    from conditional_phase_time_v1.mapping import decode
    repo=Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True,exist_ok=False)
    report=dict(result='running',cases=[],sources={})
    try:
        for name in ('research/phase_stream_control_v1_plan.json','tools/run_phase_stream_known_v1.py',
            'tools/phase_stream_control_v1/fixtures.py','tools/phase_stream_control_v1/marginal.py',
            'tools/radial_copula_v1/quantiles.py','tools/conditional_phase_time_v1/mapping.py'):
            dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(repo/name,dest);report['sources'][name]=sha(dest)
        for name,table in cases().items():
            u=uniforms(len(table));normal=np.broadcast_to(ndtri(u)[:,None],(len(u),table.shape[1])).copy()
            actual_uniform=ndtr(normal)
            knots=np.array([.1,.7,1.3,2.,5.])
            product=np.linspace(-2,8,len(u))
            original=lookup(table,normal)
            decoded=[]; arrays={}
            for j in range(table.shape[1]):
                cdf,lo,hi=cells(table[:,j],knots)
                decoded.append(decode(product,actual_uniform[:,j],knots,cdf,lo,hi))
                arrays.update({f'cdf_{j}':cdf,f'low_{j}':lo,f'high_{j}':hi})
            decoded=np.column_stack(decoded)
            error=float(abs(original-decoded).max())
            assert error<2e-12,(name,error)
            assert np.array_equal(original[[0,-1]],decoded[[0,-1]])
            # Deliberately omit the half-cell tails: this must be distinguishable.
            wrong=np.column_stack([np.interp(actual_uniform[:,j],np.linspace(0,1,len(table)),table[:,j]) for j in range(table.shape[1])])
            negative=float(abs(original-wrong).max())
            if len(table)>1:assert negative>1e-3
            path=a.out/(name+'.npz')
            np.savez_compressed(path,table=table,uniform=actual_uniform,normal=normal,product=product,
                knots=knots,original=original,decoded=decoded,wrong_no_half_tails=wrong,**arrays)
            report['cases'].append(dict(name=name,file=path.name,sha256=sha(path),rows=len(table),
                queries=len(u),maximum_phase_error_radians=error,negative_control_error_radians=negative))
        report['result']='phase_stream_known_ready';save(a.out/'report.json',report)
        print(report['result'],flush=True)
    except BaseException as e:
        report.update(result='failed',error=repr(e));save(a.out/'report.json',report);raise


if __name__=='__main__':main()
