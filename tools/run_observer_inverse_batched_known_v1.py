"""Qualify batched equivalent kernels on all8 controls and3 dense solutions."""
import argparse,os,shutil,sys
from pathlib import Path
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('workspace','known','known-audit','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    for n in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[n]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from observer_forward_v1.batched import BatchedObserver
    from observer_inverse_v1.precondition import infer_preconditioned
    from observer_inverse_v1.fit import real_vector
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
    r=dict(result='running',cases=[],solves=[],sources={},inputs={},material_read=False)
    names=('tools/run_observer_inverse_batched_known_v1.py','tools/observer_forward_v1/operator.py','tools/observer_forward_v1/polyphase.py',
           'tools/observer_forward_v1/batched.py','tools/observer_inverse_v1/precondition.py','tools/observer_inverse_v1/fit.py','tools/observer_inverse_v1/regularizer.py')
    for name in names:
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest);r['sources'][name]=sha(dest)
    try:
        old=load(a.known/'report.json');audit=load(a.known_audit/'report.json')
        assert audit['result']=='independent_observer_inverse_known_passed' and audit['producer_sha256']==sha(a.known/'report.json')
        def consume(path):r['inputs'][str(path)]=sha(path);return path
        consume(a.known/'report.json');consume(a.known_audit/'report.json')
        for desc in old['cases']:
            path=consume(a.known/desc['file']);assert sha(path)==desc['sha256']
            with np.load(path) as z:cap={k:z[k] for k in z.files}
            nodes=cap['nodes'];orders=cap['orders'];observed=cap.get('observed_orders',orders)
            op=BatchedObserver(len(cap['audio']),cap['positions'],orders,observed,nodes.shape[-1])
            wave=op.synthesize(nodes);y=op.observe(wave);we=float(abs(wave-cap['audio']).max());fe=float(abs(y-cap['observed']).max());assert max(we,fe)<2e-12
            extra={};record=dict(name=desc['name'],maximum_wave_error=we,maximum_forward_error=fe)
            if 'test_rows' in cap:
                gradient=op.adjoint(cap['test_rows']);ge=float(abs(gradient-cap['gradient']).max());assert ge<2e-12
                extra.update(test_rows=cap['test_rows'],gradient=gradient);record['maximum_adjoint_error']=ge
            out=a.out/desc['file'];np.savez_compressed(out,nodes=nodes,positions=op.positions,orders=orders,observed_orders=observed,audio=wave,observed=y,**extra)
            record.update(file=out.name,sha256=sha(out));r['cases'].append(record)
        path=consume(a.known/'dense_system.npz');assert sha(path)==old['dense_sha256'];shutil.copy2(path,a.out/'dense_system.npz')
        with np.load(path) as z:c={k:z[k] for k in z.files}
        op=BatchedObserver(int(c['frames']),c['positions'],c['orders'],c['orders'])
        for desc in old['solves']:
            path=consume(a.known/desc['file']);assert sha(path)==desc['sha256']
            with np.load(path) as z:target=z['target'];truth=z['dense_solution'];rhs=z['rhs']
            nodes,info,_=infer_preconditioned(op,target,c['scale']);x=real_vector(nodes/c['scale'][None]);error=float(np.linalg.norm(x-truth)/np.linalg.norm(truth))
            assert info['converged'] and error<2e-7
            out=a.out/desc['file'];np.savez_compressed(out,target=target,nodes=nodes,rhs=rhs,solution=x,dense_solution=truth)
            r['solves'].append(dict(name=desc['name'],file=out.name,sha256=sha(out),relative_dense_solution_error=error,**info))
        r.update(result='observer_inverse_known_ready',equivalent_operator_controls=8,regularized_dense_controls=3,
                 dense_sha256=sha(a.out/'dense_system.npz'),no_real_source_fit=True,batched_equivalent_kernels=True)
        save(a.out/'report.json',r);print(r['result'],flush=True)
    except BaseException as error:r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
