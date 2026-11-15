"""Independent scalar mass walk and piecewise hat reconstruction of known Q."""
import argparse
import math
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load,save,sha


def row(u,cumulative,lo,hi):
    for j in range(len(lo)):
        if u<cumulative[j+1] or j==len(lo)-1:
            return lo[j]+(u-cumulative[j])/(cumulative[j+1]-cumulative[j])*(hi[j]-lo[j])
    raise AssertionError()


def phase(p,u,knots,cumulative,lo,hi):
    if len(knots)==1 or p<=knots[0]:return row(u,cumulative[0],lo,hi)
    if p>=knots[-1]:return row(u,cumulative[-1],lo,hi)
    for j in range(len(knots)-1):
        if p<=knots[j+1]:
            w=(p-knots[j])/(knots[j+1]-knots[j])
            return (1-w)*row(u,cumulative[j],lo,hi)+w*row(u,cumulative[j+1],lo,hi)
    raise AssertionError()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','study','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_audit.py')
    study=load(a.study/'report.json');report=dict(result='running',cases=0,queries=0,maximum_phase_error=0.)
    try:
        assert study['result']=='quantile_surface_known_ready' and not study['material_read']
        repo=Path(__file__).resolve().parents[1]
        for name,digest in study['sources'].items():assert sha(repo/name)==sha(a.study/'exact_sources'/name)==digest
        for case in study['cases']:
            path=a.study/case['file'];assert sha(path)==case['sha256']
            with np.load(path) as z:
                expected=np.array([phase(p,u,z['knots'],z['cdf'],z['low'],z['high']) for p,u in zip(z['product'],z['uniform'])])
                error=float(abs(expected-z['phase']).max());assert error<2e-12
                report['maximum_phase_error']=max(report['maximum_phase_error'],error)
                for p0 in np.unique(z['product']):
                    selected=z['product']==p0;order=np.argsort(z['uniform'][selected]);assert np.min(np.diff(z['phase'][selected][order]))>=-2e-12
                report['queries']+=len(expected);report['cases']+=1
        path=a.study/'moving_atom_control.npz';assert sha(path)==study['moving_control_sha256']
        with np.load(path) as z:
            derivative=np.diff(z['candidate'])/np.diff(z['product']);assert abs(derivative-2).max()<2e-12
            old_step=float(abs(np.diff(z['original'])).max());new_step=float(abs(np.diff(z['candidate'])).max())
            assert old_step>1000*new_step
            # Independently form the mixed CDF and walk its cells for Q_old.
            mixed=(z['cdf'][0]+z['cdf'][1])/2
            old=[row(u,mixed,z['low'],z['high']) for u in z['probe_u']]
            new=[phase(.5,u,z['knots'],z['cdf'],z['low'],z['high']) for u in z['probe_u']]
            moments=[]
            for values in (old,new):moments.append(complex(math.fsum(math.cos(t) for t in values),math.fsum(math.sin(t) for t in values))/len(values))
            assert abs(moments[0]-z['old_moment'])<2e-12 and abs(moments[1]-z['new_moment'])<2e-12
            assert abs(moments[0]-moments[1])>.1
            assert abs(old_step-study['maximum_old_P_path_step'])<2e-12 and abs(new_step-study['maximum_new_P_path_step'])<2e-12
            assert abs(abs(moments[0]-moments[1])-study['conditional_moment_change'])<2e-12
        assert report['cases']==7
        report.update(result='independent_quantile_surface_known_passed',producer_sha256=sha(a.study/'report.json'),
                      auditor_sha256=sha(__file__),P_derivative_bound_verified=True,
                      changed_conditional_moment_explicitly_verified=True,real_material_or_native_audio_or_C=False)
        save(a.out/'report.json',report);print(report,flush=True)
    except BaseException as e:
        report.update(result='failed',error=repr(e));save(a.out/'report.json',report);raise


if __name__=='__main__':main()
