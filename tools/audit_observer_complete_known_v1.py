"""Independent all-bin SciPy/closed-impulse and dense waveform-system audit."""
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
    from scipy import linalg
    from observer_complete_v1.audit_oracle import synthesize,wave_adjoint,full_frame,curvature,hats
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
    shutil.copy2(__file__,a.out/'executed_audit.py');shutil.copy2(repo/'tools/observer_complete_v1/audit_oracle.py',a.out/'executed_oracle.py')
    r=dict(result='running',frames=[],synthesis=[],solves=[],material_read=False,
        maximum_frame_error=0.,maximum_synthesis_error=0.,maximum_wave_adjoint_error=0.)
    try:
        producer=load(a.study/'report.json');assert producer['result']=='observer_complete_known_ready'
        for name,digest in producer['sources'].items():assert sha(repo/name)==sha(a.study/'exact_sources'/name)==digest
        for desc in producer['frames']:
            path=a.study/desc['file'];assert sha(path)==desc['sha256']
            with np.load(path) as z:
                reference,coverage=full_frame(z['audio'])
                err=float(abs(reference-z['rows']).max());assert err<2e-12
                r['maximum_frame_error']=max(r['maximum_frame_error'],err)
                assert abs(coverage-z['coverage']).max()<2e-14 and (coverage>0).all()
                assert abs(np.vdot(reference,reference).real-np.vdot(z['audio'],z['audio']).real)<2e-10*max(1,np.vdot(z['audio'],z['audio']).real)
                # Independently derive a waveform gradient from each all-bin
                # coefficient basis using full inverse complex DFT conventions.
                weights=np.r_[1.,np.full(2047,np.sqrt(2.)),1.]
                rows=z['test_rows'];gradient=np.zeros_like(z['audio'])
                for j,start in enumerate(z['starts']):
                    positive=rows[j]/weights[:,None]
                    full=np.concatenate((positive,positive[-2:0:-1].conj()),axis=0)
                    # Imaginary DC/Nyquist has zero derivative for real audio.
                    full[[0,2048]]=full[[0,2048]].real
                    window=np.fft.ifft(full,axis=0).real*64
                    first,last=max(0,start),min(len(gradient),start+4096)
                    w=.5-.5*np.cos(2*np.pi*np.arange(first-start,last-start)/4096)
                    gradient[first:last]+=window[first-start:last-start]*w[:,None]/np.sqrt(coverage[first:last,None])
                assert abs(gradient-z['gradient']).max()<2e-12
                if desc['name'] in ('first_impulse','last_impulse'):
                    index=0 if desc['name']=='first_impulse' else len(z['audio'])-1
                    truth=np.zeros_like(reference)
                    for j,start in enumerate(z['starts']):
                        if start<=index<start+4096:
                            offset=index-start;w=.5-.5*np.cos(2*np.pi*offset/4096)
                            truth[j]=np.exp(-2j*np.pi*np.arange(2049)*offset/4096)[:,None]*weights[:,None]*w/64/np.sqrt(coverage[index])*z['audio'][index]
                    assert abs(truth-reference).max()<2e-12 and abs(reference).max()>1e-4
                r['frames'].append(desc['name'])
        for desc in producer['synthesis']:
            path=a.study/desc['file'];assert sha(path)==desc['sha256']
            with np.load(path) as z:
                wave=synthesize(z['nodes'],z['positions'],z['orders'],len(z['audio']))
                gradient=wave_adjoint(z['test_wave'],z['positions'],z['orders'])
                we=float(abs(wave-z['audio']).max());ge=float(abs(gradient-z['gradient']).max())
                assert we<2e-12 and ge<2e-10,(desc['name'],we,ge)
                r['maximum_synthesis_error']=max(r['maximum_synthesis_error'],we)
                r['maximum_wave_adjoint_error']=max(r['maximum_wave_adjoint_error'],ge)
                r['synthesis'].append(desc['name'])
        assert sha(a.study/'dense_system.npz')==producer['dense_sha256']
        with np.load(a.study/'dense_system.npz') as z:cap={k:z[k] for k in z.files}
        positions,orders,scale=cap['positions'],cap['orders'],cap['scale'];N=int(cap['frames']);C=2
        M,H=len(positions),len(orders);size=M*H*C;B=np.zeros((N*C,2*size))
        basis=hats(positions,N);phase=2*np.pi*np.arange(N)[:,None]*orders[None,:]/1024
        for m in range(M):
            for h in range(H):
                for c in range(C):
                    j=(m*H+h)*C+c
                    B[c::C,j]=basis[m]*np.cos(phase[:,h])*scale[h,0]
                    B[c::C,size+j]=-basis[m]*np.sin(phase[:,h])*scale[h,0]
        D=curvature(positions);dk=np.kron(D,np.eye(H*C));dr=linalg.block_diag(dk,dk)
        A=np.vstack((B/float(cap['wave_scale']),np.sqrt(.001)*dr,np.sqrt(.000001)*np.eye(2*size)))
        assert abs(A-cap['matrix']).max()<2e-12
        K=.001*D.T@D+.000001*np.eye(M)
        for desc in producer['solves']:
            path=a.study/desc['file'];assert sha(path)==desc['sha256']
            with np.load(path) as z:
                target=z['target'];b=np.r_[target.ravel()/float(cap['wave_scale']),np.zeros(len(A)-target.size)]
                assert np.array_equal(b,z['rhs'])
                truth=np.linalg.lstsq(A,b,rcond=None)[0];x=z['solution']
                error=float(np.linalg.norm(x-truth)/max(np.linalg.norm(truth),1e-24));assert error<2e-7
                residual=A@x-b;objective=float(residual@residual)
                stationarity=float(np.linalg.norm(A.T@residual)/max(np.linalg.norm(A.T@b),1e-24))
                assert stationarity<2e-7 and abs(stationarity-desc['relative_stationarity'])<2e-10
                assert abs(objective-desc['objective'])<2e-9*max(1,objective)
                T=z['time'];assert abs(T.T@K@T-np.eye(M)).max()<2e-9
                P=np.zeros_like(z['right'])
                for m in range(M):
                    for h in range(H):
                        for c in range(C):
                            j=(m*H+h)*C+c
                            for i in range(M):
                                k=(i*H+h)*C+c
                                P[k,j]=T[i,m]*z['real_scale'][m,h,0]
                                P[size+k,size+j]=T[i,m]*z['imag_scale'][m,h,0]
                assert abs(P-z['right']).max()<2e-10 and np.linalg.svd(P,compute_uv=False).min()>0
                assert abs(np.sum((A@P)**2,axis=0)-1).max()<2e-9
                r['solves'].append(dict(name=desc['name'],relative_solution_error=error,relative_stationarity=stationarity))
        assert len(r['frames'])==7 and len(r['synthesis'])==4 and len(r['solves'])==3
        r.update(result='independent_observer_complete_known_passed',producer_sha256=sha(a.study/'report.json'),
            auditor_sha256=sha(__file__),oracle_sha256=sha(repo/'tools/observer_complete_v1/audit_oracle.py'))
        save(a.out/'report.json',r);print(r['result'],flush=True)
    except BaseException as error:r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
