"""Independent SciPy frames and literal frequency masks audit all partitions."""
import argparse,os,shutil,sys
from pathlib import Path
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('workspace','study','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    for n in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[n]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from observer_complete_v1.audit_oracle import full_frame
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
    shutil.copy2(__file__,a.out/'executed_audit.py');oracle='tools/observer_complete_v1/audit_oracle.py'
    shutil.copy2(repo/oracle,a.out/'executed_oracle.py');r=dict(result='running',cases=[],maximum_error=0.)
    try:
        source=load(a.study/'report.json');assert source['result'] in ('observer_boundary_known_ready','observer_boundary_real_ready')
        for n,d in source['sources'].items():assert sha(repo/n)==sha(a.study/'exact_sources'/n)==d
        for n,d in source['inputs'].items():assert sha(n)==d
        for case in source['cases']:
            path=a.study/case['file'];assert sha(path)==case['sha256']
            with np.load(path) as z:
                audio=z['audio'];rows,_=full_frame(audio);freq=np.arange(2049)*case['root_hz']/4
                starts=np.array(list(range(-3840,len(audio),256)))
                parts=[starts<0,(starts>=0)&(starts+4096<=len(audio)),starts+4096>len(audio)]
                edges=[0,3000,6000,8000,10000,14000,21600,np.inf]
                masks=[(freq>=edges[i])&(freq<edges[i+1]) for i in range(7)]
                values=np.array([[np.sum(abs(rows[p][:,m])**2,axis=(0,1)) for m in masks] for p in parts])
                reference=np.maximum(values.sum(axis=(0,2)),1e-24)
                def check(x,y,norm=1.):
                    err=float(np.max(abs(x-y)/norm));assert err<2e-9,err;r['maximum_error']=max(r['maximum_error'],err)
                check(values,z['reference_energy'],reference[None,:,None])
                fraction=(values[0].sum(axis=1)+values[2].sum(axis=1))/reference
                check(fraction,z['reference_endcap_fraction']);check(fraction,np.array(case['endcap_fraction_by_band']))
                power=values.sum(axis=(0,2))/audio.size;power=np.r_[power[:5],power[5:].sum()]
                floor=float(np.mean(audio**2))*1e-8;weights=1/np.sqrt(np.maximum(power,floor))
                ids=np.searchsorted([3000,6000,8000,10000,14000],freq,side='right');weights=weights[ids]
                check(power,z['metric_band_power'],np.maximum(power,1e-24))
                assert np.array_equal(power<floor,z['metric_floor_active'])
                assert [int(p.sum()) for p in parts]==case['part_rows']
                for tag in case['candidate_tags']:
                    rendered,_=full_frame(z[tag+'_audio']);diff=rendered-rows
                    for weighted in (False,True):
                        x=diff*weights[None,:,None] if weighted else diff
                        value=np.array([[np.sum(abs(x[p][:,m])**2,axis=(0,1)) for m in masks] for p in parts])
                        key=tag+('_weighted_residual_energy' if weighted else '_residual_energy')
                        norm=np.maximum(value.sum(axis=(0,2)),1e-24)
                        check(value,z[key],norm[None,:,None])
                r['cases'].append(dict(label=case['label'],endcap_fraction_by_band=fraction.tolist()))
        r.update(result='independent_observer_boundary_real_passed' if source['material_read'] else 'independent_observer_boundary_known_passed',
            producer_sha256=sha(a.study/'report.json'),auditor_sha256=sha(__file__),oracle_sha256=sha(repo/oracle))
        save(a.out/'report.json',r);print(r['result'],flush=True)
    except BaseException as error:
        r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
