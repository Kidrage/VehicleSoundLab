"""Verify all seven known controls without importing their operator."""
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
    from observer_forward_v1.audit_oracle import synthesize,observe,adjoint
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
    shutil.copy2(__file__,a.out/'executed_audit.py');shutil.copy2(repo/'tools/observer_forward_v1/audit_oracle.py',a.out/'executed_oracle.py')
    r=dict(result='running',cases=[],maximum_wave_error_FS=0.,maximum_DFT_error_FS=0.,maximum_adjoint_error=0.,material_read=False)
    try:
        producer=load(a.study/'report.json');assert producer['result']=='observer_forward_known_ready' and not producer['material_read']
        for name,digest in producer['sources'].items():assert sha(repo/name)==sha(a.study/'exact_sources'/name)==digest
        names=set()
        for desc in producer['cases']:
            name=desc['name'];assert name not in names;names.add(name);path=a.study/desc['file'];assert sha(path)==desc['sha256']
            with np.load(path) as z:
                nodes,positions,orders,observed=z['nodes'],z['positions'],z['orders'],z['observed_orders'];frames=int(z['frames'])
                wave=synthesize(nodes,positions,orders,frames);measure=observe(wave,observed)
                we=float(abs(wave-z['audio']).max());de=float(abs(measure-z['observed']).max());assert we<2e-12 and de<2e-12,(name,we,de)
                r['maximum_wave_error_FS']=max(r['maximum_wave_error_FS'],we);r['maximum_DFT_error_FS']=max(r['maximum_DFT_error_FS'],de)
                if name=='constant':
                    expected=np.zeros_like(measure)
                    for h,k in enumerate(orders):expected[:,np.flatnonzero(observed==k)[0]]=nodes[0,h]
                    assert abs(measure-expected).max()<2e-12
                if name=='asymmetric_silent_right':assert np.array_equal(wave[:,1],np.zeros(frames)) and np.array_equal(measure[:,:,1],np.zeros(measure.shape[:2]))
                if name=='adjoint':
                    gradient=adjoint(z['test_rows'],positions,orders,observed,frames);error=float(abs(gradient-z['gradient']).max());assert error<2e-12
                    r['maximum_adjoint_error']=error
                    left=np.vdot(z['test_rows'],measure).real;right=np.vdot(gradient,nodes).real
                    assert abs(left-right)/max(1,abs(left),abs(right))<2e-12
                if name=='underdetermined_null':
                    cols=[]
                    for j in range(2*nodes.size):
                        vector=np.zeros(2*nodes.size);vector[j]=1
                        basis=(vector[:nodes.size]+1j*vector[nodes.size:]).reshape(nodes.shape)
                        y=observe(synthesize(basis,positions,orders,frames),observed);cols.append(np.r_[y.real.ravel(),y.imag.ravel()])
                    matrix=np.array(cols).T;assert abs(matrix-z['real_matrix']).max()<2e-12
                    rank=int((np.linalg.svd(matrix,compute_uv=False)>1e-11).sum())
                    assert rank==desc['rank'] and 2*nodes.size-rank==desc['nullity']>0
                    assert abs(matrix@z['null_real_vector']).max()<2e-12 and abs(measure).max()<2e-12
                    rms=float(np.sqrt(np.mean(wave**2)));assert abs(rms-desc['wave_RMS'])<2e-12 and rms>1e-3
                    r['null_control']=dict(rank=rank,nullity=desc['nullity'],wave_RMS=rms,maximum_observed=float(abs(measure).max()))
                r['cases'].append(name)
        assert names=={'constant','amplitude_ramp','complex_rotation','neighbor_and_image_leakage','asymmetric_silent_right','adjoint','underdetermined_null'}
        r.update(result='independent_observer_forward_known_passed',all7_verified=True,producer_sha256=sha(a.study/'report.json'),
            auditor_sha256=sha(__file__),oracle_sha256=sha(repo/'tools/observer_forward_v1/audit_oracle.py'),
            forward_correctness_not_inverse_uniqueness_or_timbre=True)
        save(a.out/'report.json',r);print(r,flush=True)
    except BaseException as error:r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
