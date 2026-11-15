"""Explicit square-root algebra and all-entry finite-frame controls before old12."""
import argparse, os, shutil, sys
from pathlib import Path
from research_archive_v1 import save, sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','out'): p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'): os.environ[name]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from waveform_representer_v1.algebra import solve
    from waveform_representer_v1.metric import finite_gram
    from waveform_representer_v1.fixtures import algebra_fixtures,frame_fixtures
    repo=Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True,exist_ok=False)
    r=dict(result='running',cases=[],frames=[],sources={},material_read=False)
    try:
        for name in ('tools/run_waveform_representer_controls_v1.py','tools/waveform_representer_v1/algebra.py',
                'tools/waveform_representer_v1/metric.py','tools/waveform_representer_v1/fixtures.py',
                'research/observer_stable_full_followup_v1_plan.json'):
            dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(repo/name,dest);r['sources'][name]=sha(dest)
        for label,Phi,W,R,y in algebra_fixtures():
            values,info=solve(Phi,W,R,y)
            path=a.out/(label+'.npz')
            np.savez_compressed(path,Phi=Phi,W=W,R=R,y=y,**values)
            r['cases'].append(dict(label=label,file=path.name,sha256=sha(path),info=info))
        for label,N,starts,window,coverage,amplitude,weights,sigma in frame_fixtures():
            W=finite_gram(N,starts,window,coverage,amplitude,weights,sigma)
            path=a.out/('frame_'+label+'.npz')
            np.savez_compressed(path,W=W,starts=starts,window=window,coverage=coverage,
                amplitude=amplitude,weights=weights,sigma=sigma)
            r['frames'].append(dict(label=label,file=path.name,sha256=sha(path)))
        r.update(result='waveform_representer_explicit_measured',real_or_old12_or_full_qualified=False)
        save(a.out/'report.json',r);print(r['result'],len(r['cases']),len(r['frames']),flush=True)
    except BaseException as error:
        r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
