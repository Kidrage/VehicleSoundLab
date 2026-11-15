"""Freeze the seam failure AND the half-angle gauge requirement before sources."""
import argparse,os,shutil,sys
from pathlib import Path
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from quantile_surface_v1.seam import fixture
    from quantile_surface_v1.surface import evaluate
    from quantile_surface_v1.moments import conditional_mixture,quantile_blend
    from quantile_surface_v1.prepare import canonical_rows
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
    r=dict(result='running',sources={},material_read=False)
    try:
        prior=a.workspace/'baselines/phase_input_paths_v1'
        assert sha(prior/'manifest.json')==load(repo/'research/phase_input_paths_v1_summary.json')['manifest_sha256']
        known=load(prior/'inputs/quantile_surface_known/known1/report.json')
        ka=load(prior/'inputs/quantile_surface_known/known_audit1/report.json')
        assert ka['result']=='independent_quantile_surface_known_passed' and ka['queries']==9474
        for name,digest in known['sources'].items():assert sha(repo/name)==digest
        names=('tools/run_quantile_surface_seam_v1.py','tools/quantile_surface_v1/seam.py',
               'tools/quantile_surface_v1/moments.py','tools/quantile_surface_v1/surface.py','tools/quantile_surface_v1/prepare.py')
        for name in names:
            dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest);r['sources'][name]=sha(dest)
        data=fixture();k,c,lo,hi=(data[n] for n in ('knots','cdf','low','high'))
        us=np.unique(np.clip(np.r_[np.linspace(0,1,257),c.ravel(),np.nextafter(c.ravel(),0),np.nextafter(c.ravel(),1)],0,1))
        ps=np.array([-.5,0.,.5,1.,1.5]);product,uniform=np.meshgrid(ps,us,indexing='ij')
        product=product.ravel();uniform=uniform.ravel();phase=evaluate(product,uniform,k,c,lo,hi)
        weights=np.linspace(0,1,33)
        old=conditional_mixture(weights,c[0],c[1],lo,hi);new=quantile_blend(weights,c[0],c[1],lo,hi)
        n=np.arange(1024);common=.2*np.sin(n*.01);delta=np.linspace(-3.1,3.1,len(n));carrier=n*.17
        stereo=np.column_stack([np.cos(carrier+common+delta/2),np.cos(carrier+common-delta/2)])
        shifted=np.column_stack([np.cos(carrier+common+np.pi+(delta+2*np.pi)/2),np.cos(carrier+common+np.pi-(delta+2*np.pi)/2)])
        wrong=np.column_stack([np.cos(carrier+common+(delta+2*np.pi)/2),np.cos(carrier+common-(delta+2*np.pi)/2)])
        np.savez_compressed(a.out/'seam.npz',**data,product=product,uniform=uniform,phase=phase,weights=weights,
                            conditional_moment=old,quantile_moment=new,common=common,delta=delta,carrier=carrier,
                            stereo=stereo,gauge_compensated=shifted,held_common=wrong)
        assert abs(new[16]-old[16])>1.9
        assert abs(stereo-shifted).max()<2e-12 and abs(stereo-wrong).max()>1.9
        raw=c.copy();raw[:,0]=[-1e-9,1e-9];raw[:,-1]=[1+1e-9,1-1e-9]
        canonical=canonical_rows(raw);assert np.array_equal(canonical[:,1:-1],raw[:,1:-1])
        endpoint_error=max(abs(quantile_blend(w,canonical[0],canonical[1],lo,hi)-conditional_mixture(w,canonical[0],canonical[1],lo,hi)) for w in (0.,1.))
        raw_error=max(abs(quantile_blend(w,raw[0],raw[1],lo,hi)-conditional_mixture(w,raw[0],raw[1],lo,hi)) for w in (0.,1.))
        assert endpoint_error<2e-12 and raw_error>2e-12
        np.savez_compressed(a.out/'endcap_control.npz',raw=raw,canonical=canonical,low=lo,high=hi)
        r.update(result='quantile_seam_known_ready',file_sha256=sha(a.out/'seam.npz'),queries=len(phase),
                 seam_midpoint_circular_moment_change=float(abs(new[16]-old[16])),
                 gauge_compensated_error_FS=float(abs(stereo-shifted).max()),held_common_error_FS=float(abs(stereo-wrong).max()),
                 prior7_known_preserved=True,new_law_not_circularly_universal=True,
                 endcap_control_sha256=sha(a.out/'endcap_control.npz'),endcap_raw_moment_error=float(raw_error),canonical_endpoint_moment_error=float(endpoint_error))
        save(a.out/'report.json',r);print(r,flush=True)
    except BaseException as e:r.update(result='failed',error=repr(e));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
