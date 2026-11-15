"""Known waveform blind spots first, then all source-boundary error budgets."""
import argparse,os,shutil,sys
from pathlib import Path
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','root','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--attempts',nargs='+',default=['real1','real2','real3'])
    a=p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from observer_forward_v1.polyphase import PolyphaseObserver
    from observer_inverse_v1.visibility import coverage
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
    sources=('tools/run_observer_inverse_visibility_v1.py','tools/observer_inverse_v1/visibility.py')
    for name in sources:
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest)
    r=dict(result='running',known=[],cases=[],inputs={},sources={n:sha(repo/n) for n in sources})
    try:
        frames=4353;orders=np.arange(1,289)
        op=PolyphaseObserver(frames,np.array([0,1024,2048,3072,4352]),orders,orders)
        for name,n in (('first_hann_zero',0),('uncovered_tail',4352),('interior',2176)):
            audio=np.zeros((frames,2));audio[n,0]=1.;audio[n,1]=-.3
            actual=op.observe(audio)
            truth=np.zeros_like(actual)
            for j,start in enumerate(op.starts):
                if start<=n<start+4096:
                    w=.5-.5*np.cos(2*np.pi*(n-start)/4096)
                    truth[j]=2*w/2048*np.exp(-2j*np.pi*orders*n/1024)[:,None]*np.array([1.,-.3])
            err=float(abs(actual-truth).max());assert err<2e-15
            full=np.array([np.fft.rfft(audio[s:s+4096]*op.window[:,None],axis=0) for s in op.starts])
            if name!='interior':assert np.array_equal(full,np.zeros_like(full)) and np.array_equal(actual,np.zeros_like(actual))
            else:assert abs(actual).max()>1e-4
            r['known'].append(dict(name=name,maximum_direct_formula_error=err,
                maximum_observer_amplitude=float(abs(actual).max()),all_frequency_maximum=float(abs(full).max())))
        save(a.out/'report.json',r)
        for attempt in a.attempts:
            report=load(a.root/attempt/'report.json');assert report['result']=='observer_inverse_all6_measured'
            r['inputs'][str(a.root/attempt/'report.json')]=sha(a.root/attempt/'report.json')
            for case in report['cases']:
                folder=a.root/attempt/case['label']
                assert sha(folder/'source.npz')==case['source_sha256']
                with np.load(folder/'source.npz') as z:reference=z['audio']
                cov=coverage(len(reference));unseen=cov['unobserved']
                row=dict(attempt=attempt,label=case['label'],frames=len(reference),
                    rows=len(cov['starts']),trailing_unobserved=cov['trailing_unobserved'],
                    unobserved_samples=unseen.tolist(),variants={})
                for name,desc in case['variants'].items():
                    path=folder/desc['file'];assert sha(path)==desc['sha256']
                    with np.load(path) as z:residue=z['audio']-reference
                    total=float(np.sum(residue**2));missing=float(np.sum(residue[unseen]**2))
                    row['variants'][name]=dict(unobserved_error_energy=missing,total_error_energy=total,
                        unobserved_fraction_of_error=missing/max(total,1e-24))
                path=a.out/(attempt+'_'+case['label']+'.npz');np.savez_compressed(path,**cov)
                row.update(file=path.name,sha256=sha(path));r['cases'].append(row)
        r.update(result='observer_inverse_visibility_ready',known_controls=3,
            waveform_null_due_to_uncovered_samples_only=True,not_physical_or_complete_latent_identifiability=True)
        save(a.out/'report.json',r);print(r['result'],len(r['cases']),flush=True)
    except BaseException as error:r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
