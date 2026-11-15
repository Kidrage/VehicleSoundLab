"""Declared inverse-action and original-seven correction controls, no recordings."""
import argparse
import os
import shutil
import sys
from pathlib import Path
from research_archive_v1 import save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('workspace','out'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--inverse-backend',choices=('copy','native'),default='copy')
    a=p.parse_args()
    for n in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[n]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy import linalg
    from waveform_representer_v1.fixtures import algebra_fixtures
    from waveform_correction_v1.fixtures import inverse_fixtures
    from waveform_correction_v1.inverse import NormalInverse
    if a.inverse_backend=='native':
        from waveform_correction_v1.native_inverse import NativeNormalInverse as NormalInverse
    from waveform_correction_v1.correct import refine
    from waveform_stream_v1.householder import Householder
    from waveform_stream_v1.solver import solve
    from waveform_banded_v1.metric import BandedMetric
    from waveform_structured_v1.resources import ArrayLedger
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
    r=dict(result='running',inverse_cases=[],original_cases=[],sources={},material_read=False,inverse_backend=a.inverse_backend)
    names={'tools/run_waveform_correction_controls_v1.py','tools/waveform_representer_v1/fixtures.py',
        'research/waveform_original_correction_v1_plan.json','tools/waveform_structured_v1/resources.py'}
    if a.inverse_backend=='native':names.add('research/waveform_correction_storage_v1_plan.json')
    for folder in ('waveform_correction_v1','waveform_stream_v1','waveform_banded_v1'):
        names.update(p.relative_to(repo).as_posix() for p in (repo/'tools'/folder).glob('*.py'))
    class Prior:
        def __init__(self,R):self.K=R;self.L=np.linalg.cholesky(R);self.size=len(R)
        def inverse(self,x):return linalg.solve_triangular(self.L,x,lower=True)
        def inverse_transpose(self,x):return linalg.solve_triangular(self.L,x,trans='T',lower=True)
    try:
        for n in sorted(names):
            path=a.out/'exact_sources'/n;path.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(repo/n,path);r['sources'][n]=sha(path)
        for label,X,rhs in inverse_fixtures():
            ledger=ArrayLedger();qr=Householder(np.array(X,order='F'),ledger,'control.X_QR')
            inverse=NormalInverse(qr.raw,ledger,block=3)
            got=inverse.apply(rhs);reverse=inverse.apply(rhs[:,len(X[0]):len(X[0])+2])
            path=a.out/('inverse_'+label+'.npz')
            np.savez_compressed(path,X=X,rhs=rhs,got=got,reverse=reverse,x_raw=qr.raw,x_tau=qr.tau,**inverse.arrays())
            r['inverse_cases'].append(dict(label=label,file=path.name,sha256=sha(path),factor=inverse.info(),resources=ledger.report()))
            print('INVERSE CONTROL',label,flush=True)
        rng=np.random.default_rng(471083)
        for label,Phi,W,R,y in algebra_fixtures():
            prior=Prior(R);ledger=ArrayLedger()
            base,info=solve(lambda x:Phi@x,lambda x:Phi.T@x,prior,BandedMetric.control_from_dense(W),y,ledger,block=3)
            inverse=NormalInverse(base['x_raw'],ledger,block=3)
            delta=np.zeros_like(base['z']) if label=='zero' else rng.normal(size=base['z'].shape)*.01
            corrected=refine(lambda x:Phi@x,lambda x:Phi.T@x,prior,lambda e:W@e,base,inverse,initial_delta=delta)
            path=a.out/('original_'+label+'.npz')
            np.savez_compressed(path,Phi=Phi,W=W,R=R,y=y,base_z=base['z'],base_wave=base['wave_model_residual'],
                initial_delta=delta,x_raw=base['x_raw'],x_tau=base['x_tau'],**corrected,**inverse.arrays())
            r['original_cases'].append(dict(label=label,file=path.name,sha256=sha(path),base_solver=info,
                factor=inverse.info(),resources=ledger.report(),fixed_correction_steps=2))
            print('ORIGINAL CORRECTION CONTROL',label,flush=True)
        assert len(r['inverse_cases'])==8 and len(r['original_cases'])==7
        r.update(result='waveform_original_correction_controls_measured',no_source_full_or_runtime_qualification=True)
        save(a.out/'report.json',r)
    except BaseException as error:
        r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
