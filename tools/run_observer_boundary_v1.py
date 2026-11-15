"""Known-first finite-frame boundary diagnosis, no fitting or new sound source."""
import argparse,os,shutil,sys
from pathlib import Path
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('workspace','out'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--study',type=Path);p.add_argument('--known-audit',type=Path);a=p.parse_args()
    for n in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[n]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from observer_frequency_v1.boundary import analyze
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
    r=dict(result='running',cases=[],sources={},inputs={},material_read=a.study is not None)
    names=('tools/run_observer_boundary_v1.py','tools/observer_frequency_v1/boundary.py','tools/observer_frequency_v1/metric.py','tools/observer_complete_v1/frame.py')
    for n in names:
        dest=a.out/'exact_sources'/n;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/n,dest);r['sources'][n]=sha(dest)
    try:
        cases=[]
        if a.study is None:
            n=np.arange(14335);low=np.cos(2*np.pi*7*n/1024)
            high=1e-5*np.cos(2*np.pi*257*n/1024+.3)
            for label,x in (('pure_low',low),('weak_high',low+high)):
                audio=np.column_stack((x,.7*x));cases.append((label,64.,audio,{}))
        else:
            assert a.known_audit is not None
            audit=load(a.known_audit/'report.json');assert audit['result']=='independent_observer_boundary_known_passed'
            r['inputs'][str(a.known_audit/'report.json')]=sha(a.known_audit/'report.json')
            record=load(a.study/'report.json');assert record['result']=='observer_frequency_correction_all6_measured'
            r['inputs'][str(a.study/'report.json')]=sha(a.study/'report.json')
            for case in record['cases']:
                folder=a.study/case['label'];waves={}
                with np.load(folder/'source.npz') as z:audio=z['audio']
                r['inputs'][str(folder/'source.npz')]=sha(folder/'source.npz')
                for tag,name in (('initial','initial.npz'),('block_refined',case['file'])):
                    path=folder/name;r['inputs'][str(path)]=sha(path)
                    with np.load(path) as z:waves[tag]=z['audio']
                cases.append((case['label'],case['root_hz'],audio,waves))
        for i,(label,root,audio,candidates) in enumerate(cases):
            result=analyze(audio,root,candidates);path=a.out/f'case{i}.npz'
            np.savez_compressed(path,audio=audio,**{k+'_audio':v for k,v in candidates.items()},**result)
            if label=='pure_low':
                energy=result['reference_energy']
                assert energy[1,5].sum()<1e-20*energy.sum() and result['reference_endcap_fraction'][5]>.999999
            row=dict(label=label,root_hz=root,file=path.name,sha256=sha(path),candidate_tags=list(candidates),
                endcap_fraction_by_band=result['reference_endcap_fraction'].tolist(),
                metric_floor_active=result['metric_floor_active'].tolist(),part_rows=result['part_rows'].tolist())
            r['cases'].append(row);print('BOUNDARY',label,row['endcap_fraction_by_band'],flush=True)
        r.update(result='observer_boundary_real_ready' if a.study else 'observer_boundary_known_ready',no_source_or_runtime_change=True)
        save(a.out/'report.json',r)
    except BaseException as error:
        r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
