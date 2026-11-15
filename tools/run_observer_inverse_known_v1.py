"""Qualify equivalent FFT operator and regularized solves before source fits."""
import argparse,os,shutil,sys
from pathlib import Path
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('workspace','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    for n in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[n]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy import linalg
    from observer_forward_v1.operator import EnvelopeObserver
    from observer_forward_v1.polyphase import PolyphaseObserver
    from observer_inverse_v1.fit import infer,RegularizedObserver,real_vector,complex_array
    repo=Path(__file__).resolve().parents[1];parent=a.workspace/'baselines/observer_forward_known_v1'
    assert sha(parent/'manifest.json')==load(repo/'research/observer_forward_known_v1_summary.json')['manifest_sha256']
    entries={r['path']:r['sha256'] for r in load(parent/'manifest.json')['files']}
    a.out.mkdir(parents=True,exist_ok=False)
    r=dict(result='running',cases=[],solves=[],sources={},inputs={},material_read=False)
    names=('tools/run_observer_inverse_known_v1.py','tools/observer_forward_v1/operator.py','tools/observer_forward_v1/polyphase.py',
           'tools/observer_inverse_v1/fit.py','tools/observer_inverse_v1/regularizer.py')
    for name in names:
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest);r['sources'][name]=sha(dest)
    def frozen(name):
        path=parent/name;assert sha(path)==entries[name];r['inputs'][str(path)]=entries[name];return path
    try:
        old=load(frozen('evidence/known1/report.json'));dense=None
        for desc in old['cases']:
            with np.load(frozen('evidence/known1/'+desc['file'])) as z:cap={k:z[k] for k in z.files}
            nodes=cap['nodes'];op=PolyphaseObserver(int(cap['frames']),cap['positions'],cap['orders'],cap['observed_orders'],nodes.shape[-1])
            wave=op.synthesize(nodes);y=op.forward(nodes)
            we=float(abs(wave-cap['audio']).max());fe=float(abs(y-cap['observed']).max());assert max(we,fe)<2e-12
            record=dict(name=desc['name'],maximum_wave_error=we,maximum_forward_error=fe)
            extra={}
            if 'test_rows' in cap:
                grad=op.adjoint(cap['test_rows']);ge=float(abs(grad-cap['gradient']).max());assert ge<2e-12
                extra.update(gradient=grad,test_rows=cap['test_rows']);record['maximum_adjoint_error']=ge
            path=a.out/(desc['name']+'.npz');np.savez_compressed(path,nodes=nodes,positions=op.positions,orders=op.orders,observed_orders=op.observed,audio=wave,observed=y,**extra)
            record.update(file=path.name,sha256=sha(path));r['cases'].append(record)
            if desc['name'] in ('constant','amplitude_ramp','neighbor_and_image_leakage'):
                fitted=PolyphaseObserver(op.frames,op.positions,op.orders,op.orders,op.channels);target=cap['observed'][:,op.orders-1]
                scale=np.array([[1.],[.3],[.05]]);system=RegularizedObserver(fitted,scale)
                if dense is None:
                    # Independent dense basis uses original direct-OSC operator.
                    reference=EnvelopeObserver(op.frames,op.positions,op.orders,op.orders,op.channels);columns=[]
                    for j in range(system.nsize):
                        vector=np.zeros(system.nsize);vector[j]=1;q=complex_array(vector,reference.shape)
                        columns.append(real_vector(reference.forward(q*scale[None])/scale[None]))
                    dense_forward=np.array(columns).T
                    dk=np.kron(system.D.toarray(),np.eye(len(op.orders)*op.channels));dreal=linalg.block_diag(dk,dk)
                    dense=np.vstack((dense_forward,np.sqrt(system.alpha)*dreal,np.sqrt(system.beta)*np.eye(system.nsize)))
                    np.savez_compressed(a.out/'dense_system.npz',matrix=dense,forward=dense_forward,scale=scale,positions=op.positions,orders=op.orders,frames=op.frames)
                fitted_nodes,info=infer(fitted,target,scale);b=system.rhs(target);truth=np.linalg.lstsq(dense,b,rcond=None)[0]
                x=real_vector(fitted_nodes/scale[None]);error=float(np.linalg.norm(x-truth)/max(np.linalg.norm(truth),1e-24))
                assert info['converged'] and error<2e-7,(desc['name'],info,error)
                path=a.out/('solve_'+desc['name']+'.npz');np.savez_compressed(path,target=target,nodes=fitted_nodes,rhs=b,solution=x,dense_solution=truth)
                r['solves'].append(dict(name=desc['name'],file=path.name,sha256=sha(path),relative_dense_solution_error=error,**info))
        frames=5120;positions=np.r_[np.arange(0,frames-1,256),frames-1];orders=np.arange(1,289);rng=np.random.default_rng(71347)
        nodes=(rng.normal(size=(len(positions),288,2))+1j*rng.normal(size=(len(positions),288,2)))*.001
        op=PolyphaseObserver(frames,positions,orders,orders);reference=EnvelopeObserver(frames,positions,orders,orders)
        wave=op.synthesize(nodes);y=op.observe(wave);q=rng.normal(size=y.shape)+1j*rng.normal(size=y.shape)
        grad=op.adjoint(q);we=float(abs(wave-reference.synthesize(nodes)).max());fe=float(abs(y-reference.forward(nodes)).max());ge=float(abs(grad-reference.adjoint(q)).max())
        assert max(we,fe,ge)<2e-12,(we,fe,ge)
        path=a.out/'full288.npz';np.savez_compressed(path,nodes=nodes,positions=positions,orders=orders,audio=wave,observed=y,test_rows=q,gradient=grad)
        r['cases'].append(dict(name='full288',file=path.name,sha256=sha(path),maximum_wave_error=we,maximum_forward_error=fe,maximum_adjoint_error=ge))
        r.update(result='observer_inverse_known_ready',equivalent_operator_controls=8,regularized_dense_controls=3,dense_sha256=sha(a.out/'dense_system.npz'),no_real_source_fit=True)
        save(a.out/'report.json',r);print(r['result'],flush=True)
    except BaseException as error:r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
