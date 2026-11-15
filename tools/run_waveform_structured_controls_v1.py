"""Original seven dense algebra controls plus node-root and finite-DFT controls."""
import argparse
import os
import shutil
import sys
from pathlib import Path
from research_archive_v1 import save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('workspace','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    for n in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[n]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy import linalg
    from waveform_representer_v1.fixtures import algebra_fixtures,frame_fixtures
    from waveform_representer_v1.metric import finite_gram
    from waveform_structured_v1.penalty import TemporalPenalty
    from waveform_structured_v1.resources import ArrayLedger
    from waveform_structured_v1.solver import solve
    from observer_inverse_v1.regularizer import curvature
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
    names=['tools/run_waveform_structured_controls_v1.py','tools/waveform_representer_v1/fixtures.py',
        'tools/waveform_representer_v1/metric.py','tools/observer_inverse_v1/regularizer.py',
        'research/waveform_graph_structured_v1_plan.json']
    names.extend(p.relative_to(repo).as_posix() for p in (repo/'tools/waveform_structured_v1').glob('*.py'))
    r=dict(result='running',cases=[],frames=[],temporal=[],sources={},material_read=False)
    # Original seven fixtures have arbitrary coupled R, so this SMALL CONTROL
    # adapter exercises the unchanged graph algebra only. It is not a fallback
    # for complete source extraction or a claim of a structured arbitrary R.
    class DenseControlPenalty:
        def __init__(self,R):self.K=R;self.L=np.linalg.cholesky(R);self.size=len(R)
        def inverse(self,x):return linalg.solve_triangular(self.L,x,lower=True)
        def inverse_transpose(self,x):return linalg.solve_triangular(self.L.T,x,lower=False)
    try:
        for n in names:
            dest=a.out/'exact_sources'/n;dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(repo/n,dest);r['sources'][n]=sha(dest)
        for label,Phi,W,R,y in algebra_fixtures():
            channels=[];infos=[];ledgers=[]
            for j in range(y.shape[1]):
                ledger=ArrayLedger()
                values,info=solve(lambda x:Phi@x,lambda x:Phi.T@x,DenseControlPenalty(R),
                    np.array(W,order='F'),y[:,j],ledger,block=3)
                channels.append(values);infos.append(info);ledgers.append(ledger.report())
            packed={n:np.column_stack([v[n] for v in channels]) for n in
                ('q','z','t','root_model_residual','wave_model_residual','stable_root_normal','direct_transformed_normal')}
            path=a.out/(label+'.npz')
            np.savez_compressed(path,Phi=Phi,W=W,R=R,y=y,**packed)
            r['cases'].append(dict(label=label,file=path.name,sha256=sha(path),info=infos,resources=ledgers,
                scope='Original arbitrary-R fixture, explicit dense root adapter only in controls'))
        for label,N,starts,window,coverage,amplitude,weights,sigma in frame_fixtures():
            W=finite_gram(N,starts,window,coverage,amplitude,weights,sigma)
            L=linalg.cholesky(np.array(W,order='F'),lower=True,overwrite_a=True)
            path=a.out/('frame_'+label+'.npz')
            np.savez_compressed(path,W=W,L=L,starts=starts,window=window,coverage=coverage,
                amplitude=amplitude,weights=weights,sigma=sigma)
            r['frames'].append(dict(label=label,file=path.name,sha256=sha(path)))
        rng=np.random.default_rng(361507)
        for label,shape in (('mono',(5,3,1)),('stereo',(5,3,2)),('short_stereo',(3,1,2))):
            M,H,C=shape;positions=np.cumsum(np.r_[0.,[200.,256.,512.,300.][:M-1]])
            D=curvature(positions).toarray();prior=TemporalPenalty(shape,D)
            probes=rng.normal(size=(prior.size,3))
            if C==2:
                probe_view=probes[:,1].reshape(2,M,H,C);probe_view[:,:,:,1]=0
            values={n:getattr(prior,n)(probes) for n in ('root','root_transpose','inverse','inverse_transpose','apply')}
            path=a.out/('temporal_'+label+'.npz')
            np.savez_compressed(path,shape=shape,positions=positions,D=D,K=prior.K,L=prior.L,probes=probes,**values)
            r['temporal'].append(dict(label=label,file=path.name,sha256=sha(path)))
        r.update(result='waveform_structured_controls_measured',old_arbitrary_R_not_relabelled_structured=True,
                 source_or_full_or_runtime_qualified=False)
        save(a.out/'report.json',r);print(r['result'],len(r['cases']),len(r['frames']),len(r['temporal']),flush=True)
    except BaseException as error:
        r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
