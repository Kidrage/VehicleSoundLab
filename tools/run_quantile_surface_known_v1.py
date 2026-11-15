"""Known-first qualification of direct row-quantile interpolation only."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import save, sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from quantile_surface_v1.surface import evaluate
    from quantile_surface_v1.fixtures import cases
    from conditional_phase_time_v1.mapping import decode
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
    sources=('tools/run_quantile_surface_known_v1.py','tools/quantile_surface_v1/surface.py',
             'tools/quantile_surface_v1/fixtures.py','tools/conditional_phase_time_v1/mapping.py')
    report=dict(result='running',cases=[],sources={},material_read=False,new_RNG=False,
                new_phase_law_not_equivalent_optimization=True)
    for name in sources:
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest);report['sources'][name]=sha(dest)
    try:
        for case in cases():
            knots,cdf,low,high=(case[k] for k in ('knots','cdf','low','high'))
            us=np.unique(np.r_[np.linspace(0,1,257),cdf.ravel(),np.nextafter(cdf.ravel(),0),np.nextafter(cdf.ravel(),1)])
            us=np.clip(us,0,1)
            ps=np.r_[knots[0]-1,knots,(knots[:-1]+knots[1:])/2,knots[-1]+1]
            product,uniform=np.meshgrid(ps,us,indexing='ij');product=product.ravel();uniform=uniform.ravel()
            value=evaluate(product,uniform,knots,cdf,low,high)
            path=a.out/(case['name']+'.npz')
            np.savez_compressed(path,knots=knots,cdf=cdf,low=low,high=high,product=product,uniform=uniform,phase=value)
            report['cases'].append(dict(name=case['name'],file=path.name,sha256=sha(path),queries=len(value)))
        moving=next(c for c in cases() if c['name']=='moving_atom_mass')
        product=np.linspace(0,1,4097);uniform=np.full_like(product,.5)
        args=(moving['knots'],moving['cdf'],moving['low'],moving['high'])
        original=decode(product,uniform,*args);candidate=evaluate(product,uniform,*args)
        # Deliberately expose changed conditional moments at the middle knot
        # interval. The smoother P path MUST NOT be sold as the same density.
        u=(np.arange(65536)+.5)/65536;p0=np.full_like(u,.5)
        old_moment=np.mean(np.exp(1j*decode(p0,u,*args)))
        new_moment=np.mean(np.exp(1j*evaluate(p0,u,*args)))
        np.savez_compressed(a.out/'moving_atom_control.npz',product=product,uniform=uniform,
                            original=original,candidate=candidate,probe_u=u,
                            old_moment=np.array(old_moment),new_moment=np.array(new_moment),**{k:moving[k] for k in ('knots','cdf','low','high')})
        report.update(result='quantile_surface_known_ready',controls=len(report['cases']),
            maximum_old_P_path_step=float(abs(np.diff(original)).max()),
            maximum_new_P_path_step=float(abs(np.diff(candidate)).max()),
            conditional_moment_change=float(abs(old_moment-new_moment)),
            moving_control_sha256=sha(a.out/'moving_atom_control.npz'),
            fixed_u_P_bound='abs(Q_right(u)-Q_left(u))/knot_width; no tiny-probability divisor',
            U_slope_or_joint_moments_or_sound_not_qualified=True)
        save(a.out/'report.json',report);print(report,flush=True)
    except BaseException as e:
        report.update(result='failed',error=repr(e));save(a.out/'report.json',report);raise


if __name__=='__main__':main()
