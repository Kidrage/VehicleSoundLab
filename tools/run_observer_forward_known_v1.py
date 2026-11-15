"""Execute known forward/adjoint/ambiguity controls before source inference."""
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
    from observer_forward_v1.operator import EnvelopeObserver
    from observer_forward_v1.fixtures import inputs
    from sound_dna.windowed import coefficients
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
    sources=('tools/run_observer_forward_known_v1.py','tools/observer_forward_v1/operator.py','tools/observer_forward_v1/fixtures.py','tools/sound_dna/windowed.py')
    r=dict(result='running',sources={},cases=[],material_read=False,not_runtime_or_native48k=True)
    for name in sources:
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest);r['sources'][name]=sha(dest)
    try:
        for name,cap in inputs():
            nodes=cap.pop('nodes');op=EnvelopeObserver(**{k:v for k,v in cap.items() if k not in ('nodes',)},channels=nodes.shape[-1])
            extra={};desc=dict(name=name)
            if name=='underdetermined_null':
                dimension=2*nodes.size;columns=[];wave_columns=[]
                for j in range(dimension):
                    basis=np.zeros(dimension);basis[j]=1
                    z=(basis[:nodes.size]+1j*basis[nodes.size:]).reshape(nodes.shape);y=op.forward(z)
                    columns.append(np.r_[y.real.ravel(),y.imag.ravel()]);wave_columns.append(op.synthesize(z).ravel())
                matrix=np.array(columns).T;wave_matrix=np.array(wave_columns).T
                _,s,vh=np.linalg.svd(matrix,full_matrices=True);rank=int((s>1e-11).sum());null=vh[rank:]
                j=np.argmax(np.linalg.norm(wave_matrix@null.T,axis=0));v=null[j]
                nodes=(v[:nodes.size]+1j*v[nodes.size:]).reshape(nodes.shape)
                extra.update(real_matrix=matrix,null_real_vector=v,singular_values=s)
                desc.update(real_input_dimension=dimension,real_output_dimension=len(matrix),rank=rank,nullity=dimension-rank)
            wave=op.synthesize(nodes);observed=op.observe(wave)
            assert np.array_equal(wave,op.synthesize(nodes,37))
            if nodes.shape[-1]==2:
                raw=coefficients(wave,int(op.observed.max())).reshape(-1,int(op.observed.max()),2,2)
                original=(raw[...,0]+1j*raw[...,1])[:,op.observed-1]
                err=float(abs(original-observed).max());assert err<2e-12;desc['original_observer_error']=err
            if name=='constant':
                target=np.zeros_like(observed);target[:,op.orders-1]=nodes[0];assert abs(target-observed).max()<2e-12
            if name=='asymmetric_silent_right':assert np.array_equal(wave[:,1],np.zeros(op.frames)) and np.array_equal(observed[:,:,1],np.zeros(observed.shape[:2]))
            if name=='adjoint':
                rng=np.random.default_rng(27184);q=rng.normal(size=observed.shape)+1j*rng.normal(size=observed.shape)
                gradient=op.adjoint(q);left=np.vdot(q,observed).real;right=np.vdot(gradient,nodes).real
                assert abs(left-right)/max(1,abs(left),abs(right))<2e-12
                extra.update(test_rows=q,gradient=gradient);desc['relative_adjoint_error']=float(abs(left-right)/max(1,abs(left),abs(right)))
            if name=='underdetermined_null':
                desc.update(maximum_observed=float(abs(observed).max()),wave_RMS=float(np.sqrt(np.mean(wave**2))))
                assert desc['maximum_observed']<2e-12 and desc['wave_RMS']>1e-3 and desc['nullity']>0
            path=a.out/(name+'.npz');np.savez_compressed(path,**cap,nodes=nodes,audio=wave,observed=observed,**extra)
            desc.update(file=path.name,sha256=sha(path));r['cases'].append(desc)
        assert len(r['cases'])==7;r['result']='observer_forward_known_ready';save(a.out/'report.json',r);print(r['result'],flush=True)
    except BaseException as error:r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
