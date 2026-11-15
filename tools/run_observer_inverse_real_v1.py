"""All6 source inverses with native/warp provenance and same-window budgets."""
import argparse,os,shutil,sys
from pathlib import Path
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('workspace','known','known-audit','out'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--precondition-known',type=Path);p.add_argument('--precondition-audit',type=Path)
    a=p.parse_args()
    for n in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[n]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from observer_forward_v1.polyphase import PolyphaseObserver
    from observer_inverse_v1.fit import infer,RegularizedObserver,real_vector
    from observer_inverse_v1.diagnostics import interpolate_rows,capture
    from conditional_phase_time_v1.observer import analyze
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
    r=dict(result='running',pid=os.getpid(),cases=[],sources={},inputs={},in_sample_only=True)
    print('SOURCE_INVERSE_PID',os.getpid(),flush=True)
    try:
        ka=load(a.known_audit/'report.json');assert ka['result']=='independent_observer_inverse_known_passed'
        assert ka['producer_sha256']==sha(a.known/'report.json') and ka['auditor_sha256']==sha(repo/'tools/audit_observer_inverse_known_v1.py')
        for n,d in load(a.known/'report.json')['sources'].items():assert sha(repo/n)==sha(a.known/'exact_sources'/n)==d
        r.update(known_sha256=sha(a.known/'report.json'),known_audit_sha256=sha(a.known_audit/'report.json'))
        if a.precondition_known:
            assert a.precondition_audit
            pc=load(a.precondition_known/'report.json');pa=load(a.precondition_audit/'report.json')
            assert pc['result']=='observer_inverse_precondition_known_ready' and pa['result']=='independent_observer_inverse_precondition_known_passed'
            assert pa['producer_sha256']==sha(a.precondition_known/'report.json') and pa['auditor_sha256']==sha(repo/'tools/audit_observer_inverse_precondition_known_v1.py')
            for n,d in pc['sources'].items():assert sha(repo/n)==sha(a.precondition_known/'exact_sources'/n)==d
            r.update(precondition_known_sha256=sha(a.precondition_known/'report.json'),precondition_audit_sha256=sha(a.precondition_audit/'report.json'))
        names=('research/observer_inverse_v1_plan.json','tools/run_observer_inverse_real_v1.py','tools/observer_inverse_v1/fit.py','tools/observer_inverse_v1/regularizer.py',
            'tools/observer_inverse_v1/diagnostics.py','tools/observer_forward_v1/operator.py','tools/observer_forward_v1/polyphase.py',
            'tools/conditional_phase_time_v1/observer.py','tools/carrier_transfer_v1/spectral.py','tools/carrier_transfer_v1/groups.py','tools/sound_dna/windowed.py')
        if a.precondition_known:names+=('tools/observer_inverse_v1/precondition.py',)
        for n in names:
            dest=a.out/'exact_sources'/n;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/n,dest);r['sources'][n]=sha(dest)
        parent=a.workspace/'baselines/conditional_phase_time_v1';geometry=a.workspace/'baselines/coefficient_geometry_v1'
        maps={}
        for root in (parent,geometry):
            assert sha(root/'manifest.json')==load(repo/f'research/{root.name}_summary.json')['manifest_sha256']
            maps[root]={d['path']:d['sha256'] for d in load(root/'manifest.json')['files']}
        def frozen(root,name):
            path=root/name;assert sha(path)==maps[root][name];r['inputs'][str(path)]=maps[root][name];return path
        old=load(frozen(parent,'evidence/real1/report.json'));gc=load(frozen(geometry,'evidence/real1/report.json'))
        geo={x['label']:x for x in gc['cases']};plan=load(repo/names[0]);bands=[(0,3000),(3000,6000),(6000,8000),(8000,10000),(10000,14000),(14000,21600)];edges=[0,3000,6000,8000,10000,14000,1e9]
        r.update(bands=bands,carrier_edges=edges);save(a.out/'report.json',r)
        for oldrow in old['cases']:
            label,root=oldrow['label'],oldrow['root_hz'];folder=a.out/label;folder.mkdir()
            with np.load(frozen(parent,f'evidence/real1/{label}/source.npz')) as z:audio=z['audio'];target=z['coefficients'];original=z['source_rows']
            with np.load(frozen(geometry,f'evidence/real1/{label}/source.npz')) as z:
                assert np.array_equal(audio,z['rebuilt']) and np.array_equal(audio.astype('float32').astype(float),z['normalized_FLOAT'])
                native=z['native'];coordinates=z['positions']
                assert len(coordinates)==len(audio) and np.all(np.diff(coordinates)>0)
            frames=len(audio);positions=np.rint(np.linspace(0,frames-1,int(np.ceil((frames-1)/256))+1)).astype(int)
            op=PolyphaseObserver(frames,positions,np.arange(1,289),np.arange(1,289));assert len(op.starts)==len(target)
            source=analyze(audio,288,root,bands);assert abs(source['coefficients']-target).max()<2e-12
            np.savez_compressed(folder/'source.npz',audio=audio,native=native,coordinates=coordinates,positions=positions,original_rows=original,**source)
            amplitude=np.sqrt(np.mean(abs(target)**2,axis=(0,2)));floor=amplitude.max()*1e-6;scale=np.maximum(amplitude,floor)[:,None]
            np.savez_compressed(folder/'scale.npz',scale=scale,unfloored_RMS=amplitude,absolute_floor=floor)
            baseline=interpolate_rows(op,target);system=RegularizedObserver(op,scale)
            b=system.rhs(target);old_res=system@real_vector(baseline/scale[None])-b;old_objective=float(old_res@old_res)
            print('FIT START',label,'unknowns',system.nsize,flush=True)
            right=None
            if a.precondition_known:
                from observer_inverse_v1.precondition import infer_preconditioned
                nodes,desc,right=infer_preconditioned(op,target,scale,maxiter=plan['solver']['maxiter'])
                np.savez_compressed(folder/'precondition.npz',time=right.time,real_scale=right.real_scale,imag_scale=right.imag_scale)
            else:nodes,desc=infer(op,target,scale,maxiter=plan['solver']['maxiter'])
            assert desc['objective']<=old_objective*(1+1e-10)
            row=dict(label=label,root_hz=root,frames=frames,source_rows=len(target),nodes=len(positions),floored_orders=int((amplitude<floor).sum()),
                source_sha256=sha(folder/'source.npz'),scale_sha256=sha(folder/'scale.npz'),native_frames=len(native),source_start=geo[label]['source_start'],
                source_cutoff_hz=geo[label]['cutoff_hz'],baseline_objective=old_objective,solve=desc,variants={})
            if right is not None:row['precondition_sha256']=sha(folder/'precondition.npz')
            for name,latent in (('interpolated_observations',baseline),('inverse',nodes)):
                values=capture(op,latent,root,bands,edges,audio,target);path=folder/(name+'.npz');np.savez_compressed(path,**values)
                row['variants'][name]=dict(file=path.name,sha256=sha(path),wave_NRMSE=float(values['wave_NRMSE']))
            r['cases'].append(row);save(a.out/'report.json',r)
            print('FIT DONE',label,desc['stop'],desc['iterations'],'stationarity',desc['relative_stationarity'],'NRMSE',row['variants']['inverse']['wave_NRMSE'],flush=True)
        assert len(r['cases'])==6
        r.update(result='observer_inverse_all6_measured',all_converged=all(c['solve']['converged'] for c in r['cases']),new_stochastic_source=False,
                 real_RPM_or_native48k_or_runtime_C_or_hearing=False)
        save(a.out/'report.json',r);print(r['result'],'all_converged',r['all_converged'],flush=True)
    except BaseException as error:r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
