"""Independent scalar Hann coverage and sample-by-sample boundary budgets."""
import argparse,math,os,shutil,sys
from pathlib import Path
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','root','study','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_audit.py')
    r=dict(result='running',cases=[],maximum_coverage_error=0.,maximum_budget_relative_error=0.)
    try:
        producer=load(a.study/'report.json');assert producer['result']=='observer_inverse_visibility_ready'
        for path,digest in producer['inputs'].items():assert sha(path)==digest
        # Independently reconstruct the three impulse observations. A zero
        # weighted waveform is zero at EVERY DFT bin, not just selected bins.
        known=[]
        for name,n in (('first_hann_zero',0),('uncovered_tail',4352),('interior',2176)):
            weights=[(.5-.5*math.cos(2*math.pi*(n-s)/4096)) if s<=n<s+4096 else 0.
                     for s in (0,256)]
            known.append((name,max(weights)*2/2048,max(weights)))
        for (name,line,full),desc in zip(known,producer['known']):
            assert name==desc['name']
            assert abs(line-desc['maximum_observer_amplitude'])<2e-15
            assert abs(full-desc['all_frequency_maximum'])<2e-15
            if name!='interior':assert line==full==0
        for case in producer['cases']:
            N=case['frames'];starts=list(range(0,N-4096+1,256))
            w=[.5-.5*math.cos(2*math.pi*j/4096) for j in range(4096)]
            weights=np.zeros(N)
            for s in starts:
                for j,value in enumerate(w):weights[s+j]+=value*value
            unseen=np.array([n for n,value in enumerate(weights) if value==0.],int)
            assert unseen.tolist()==case['unobserved_samples']
            assert N-starts[-1]-4096==case['trailing_unobserved']
            path=a.study/case['file'];assert sha(path)==case['sha256']
            with np.load(path) as z:
                assert np.array_equal(z['starts'],starts) and np.array_equal(z['unobserved'],unseen)
                error=float(abs(z['squared_window_coverage']-weights).max());assert error<2e-14
                r['maximum_coverage_error']=max(r['maximum_coverage_error'],error)
            attempt=a.root/case['attempt'];source=next(c for c in load(attempt/'report.json')['cases'] if c['label']==case['label'])
            folder=attempt/case['label'];assert sha(folder/'source.npz')==source['source_sha256']
            with np.load(folder/'source.npz') as z:reference=z['audio']
            for name,desc in source['variants'].items():
                path=folder/desc['file'];assert sha(path)==desc['sha256']
                with np.load(path) as z:residue=z['audio']-reference
                total=math.fsum(float(x)*float(x) for x in residue.ravel())
                missing=math.fsum(float(residue[n,c])**2 for n in unseen for c in (0,1))
                expected=case['variants'][name]
                for key,value in (('total_error_energy',total),('unobserved_error_energy',missing),
                                  ('unobserved_fraction_of_error',missing/max(total,1e-24))):
                    error=abs(value-expected[key])/max(abs(value),1e-24);assert error<2e-12
                    r['maximum_budget_relative_error']=max(r['maximum_budget_relative_error'],error)
            r['cases'].append(dict(attempt=case['attempt'],label=case['label'],trailing_unobserved=case['trailing_unobserved']))
        r.update(result='independent_observer_inverse_visibility_passed',known_controls=3,
            producer_sha256=sha(a.study/'report.json'),auditor_sha256=sha(__file__))
        save(a.out/'report.json',r);print(r['result'],len(r['cases']),flush=True)
    except BaseException as error:r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
