"""Independent direct-DFT equivalence and dense regularized solution audit."""
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
    from observer_forward_v1.audit_oracle import synthesize,observe,adjoint
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
    shutil.copy2(__file__,a.out/'executed_audit.py');shutil.copy2(repo/'tools/observer_forward_v1/audit_oracle.py',a.out/'executed_oracle.py')
    r=dict(result='running',cases=[],solves=[],maximum_wave_error=0.,maximum_DFT_error=0.,maximum_adjoint_error=0.,material_read=False)
    try:
        producer=load(a.study/'report.json');assert producer['result']=='observer_inverse_known_ready'
        for n,digest in producer['sources'].items():assert sha(repo/n)==sha(a.study/'exact_sources'/n)==digest
        for path,digest in producer['inputs'].items():assert sha(path)==digest
        for desc in producer['cases']:
            path=a.study/desc['file'];assert sha(path)==desc['sha256']
            with np.load(path) as z:
                orders=z['orders'];observed=z['observed_orders'] if 'observed_orders' in z else orders;frames=len(z['audio'])
                wave=synthesize(z['nodes'],z['positions'],orders,frames);y=observe(wave,observed)
                we=float(abs(wave-z['audio']).max());de=float(abs(y-z['observed']).max());assert we<2e-12 and de<2e-12,(desc['name'],we,de)
                r['maximum_wave_error']=max(r['maximum_wave_error'],we);r['maximum_DFT_error']=max(r['maximum_DFT_error'],de)
                if 'test_rows' in z:
                    gradient=adjoint(z['test_rows'],z['positions'],orders,observed,frames);ge=float(abs(gradient-z['gradient']).max());assert ge<2e-12
                    r['maximum_adjoint_error']=max(r['maximum_adjoint_error'],ge)
                r['cases'].append(desc['name'])
            save(a.out/'report.json',r);print('AUDITED inverse operator',desc['name'],flush=True)
        assert sha(a.study/'dense_system.npz')==producer['dense_sha256']
        with np.load(a.study/'dense_system.npz') as z:cap={k:z[k] for k in z.files}
        positions,orders,scale=cap['positions'],cap['orders'],cap['scale'];frames=int(cap['frames']);shape=(len(positions),len(orders),2);size=int(np.prod(shape));cols=[]
        for j in range(2*size):
            x=np.zeros(2*size);x[j]=1;nodes=(x[:size]+1j*x[size:]).reshape(shape)*scale[None]
            y=observe(synthesize(nodes,positions,orders,frames),orders)/scale[None];cols.append(np.r_[y.real.ravel(),y.imag.ravel()])
        forward=np.array(cols).T;assert abs(forward-cap['forward']).max()<2e-12
        D=np.zeros((len(positions)-2,len(positions)))
        for j in range(len(D)):
            left=positions[j+1]-positions[j];right=positions[j+2]-positions[j+1]
            for k in range(len(positions)):
                basis=np.zeros(len(positions));basis[k]=1
                D[j,k]=2*256**2/(left+right)*((basis[j+2]-basis[j+1])/right-(basis[j+1]-basis[j])/left)
        assert abs(D@np.ones(len(positions))).max()<1e-12 and abs(D@(positions/256)).max()<1e-12
        dk=np.kron(D,np.eye(len(orders)*2));dr=linalg.block_diag(dk,dk)
        matrix=np.vstack((forward,np.sqrt(1e-3)*dr,np.sqrt(1e-6)*np.eye(2*size)))
        assert abs(matrix-cap['matrix']).max()<2e-12
        for desc in producer['solves']:
            path=a.study/desc['file'];assert sha(path)==desc['sha256']
            with np.load(path) as z:
                y=z['target']/scale[None];rhs=np.r_[y.real.ravel(),y.imag.ravel(),np.zeros(len(matrix)-2*y.size)]
                assert np.array_equal(rhs,z['rhs'])
                truth=np.linalg.lstsq(matrix,rhs,rcond=None)[0];x=z['solution'];err=float(np.linalg.norm(x-truth)/max(np.linalg.norm(truth),1e-24));assert err<2e-7
                residual=matrix@x-rhs;objective=float(residual@residual)
                assert abs(objective-desc['objective'])<2e-9*max(1,objective)
                stationarity=np.linalg.norm(matrix.T@residual)/max(np.linalg.norm(matrix.T@rhs),1e-24)
                assert stationarity<2e-7 and abs(stationarity-desc['relative_stationarity'])<2e-10
                r['solves'].append(dict(name=desc['name'],relative_solution_error=err,stationarity=float(stationarity)))
        assert len(r['cases'])==8 and len(r['solves'])==3
        r.update(result='independent_observer_inverse_known_passed',producer_sha256=sha(a.study/'report.json'),auditor_sha256=sha(__file__),
                 oracle_sha256=sha(repo/'tools/observer_forward_v1/audit_oracle.py'),no_material_inverse_qualified=True)
        save(a.out/'report.json',r);print(r['result'],flush=True)
    except BaseException as error:r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
