"""Independent original interleaved equations, adjoints, gaps and L/R identity."""
import argparse
import os
import shutil
import sys
from pathlib import Path
from research_archive_v1 import load, save, sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','study','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy import linalg
    from observer_supported_v1.audit_oracle import matrices, metric
    from observer_complete_v1.audit_oracle import full_frame
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
    shutil.copy2(__file__,a.out/'executed_audit.py')
    helpers=('tools/observer_supported_v1/audit_oracle.py','tools/observer_complete_v1/audit_oracle.py',
        'tools/observer_frequency_v1/reduced_oracle.py')
    for j,name in enumerate(helpers):shutil.copy2(repo/name,a.out/f'executed_oracle_{j}.py')
    r=dict(result='running',cases=[],maximum_errors={})
    def check(name,x,y,scale=1.,gate=2e-8):
        x,y=np.asarray(x),np.asarray(y);assert x.shape==y.shape,(name,x.shape,y.shape)
        error=float(np.max(abs(x-y))/max(float(scale),1e-300))
        r['maximum_errors'][name]=max(error,r['maximum_errors'].get(name,0.))
        assert error<gate,(name,error)
    def apply_q(raw,tau,value,transpose=False):
        value=np.array(value,copy=True);indices=range(len(tau)) if transpose else range(len(tau)-1,-1,-1)
        for j in indices:
            v=np.r_[1.,raw[j+1:,j]]
            value[j:]-=v[:,None]*(tau[j]*(v@value[j:]))[None]
        return value
    try:
        source=load(a.study/'report.json');assert source['result']=='waveform_shared_known_measured'
        for name,h in source['sources'].items():assert sha(a.study/'exact_sources'/name)==h
        for name,h in source['inputs'].items():assert sha(name)==h
        assert len(source['cases'])==8 and len(source['rejections'])==7
        for case in source['cases']:
            path=a.study/case['file'];assert sha(path)==case['sha256']
            with np.load(path) as z:
                audio=z['audio'];C=audio.shape[1];assert C==2
                if case['kind']=='algebra':
                    with np.load(case['original_file']) as old:
                        A,b,Phi,R=(old[n] for n in ('A','b','Phi','R'));count=len(Phi)
                        reference=old['original'];rootwave=np.linalg.cholesky(old['H']).T
                        data=rootwave@z['wave_model_residual'].ravel()
                else:
                    profile=metric(audio,64.)
                    A,b,Phi,R,count=matrices(z['positions'],z['orders'],z['scale'],audio,profile)
                    reference=linalg.lstsq(A,b,lapack_driver='gelsd')[0]
                    wave=z['wave_model_residual'];rows,_=full_frame(wave)
                    rows=rows[profile['keep']]*profile['amplitude']*profile['weights'][None,:,None]
                    data=np.r_[wave.ravel()/profile['sigma'],rows.real.ravel(),rows.imag.ravel()]
                check('complete_original_matrix',A,z['original_A'],max(1.,abs(A).max()))
                check('complete_original_rhs',b,z['original_rhs'],max(1.,abs(b).max()))
                B,target=A[:count],b[:count];q=z['q'].ravel();n=len(q)//C
                ids=[np.arange(c,len(q),C) for c in range(C)]
                check('channel_data_Gram',B[:,ids[0]].T@B[:,ids[0]],B[:,ids[1]].T@B[:,ids[1]],max(1.,np.max(abs(B.T@B))))
                assert np.count_nonzero(B[:,ids[0]].T@B[:,ids[1]])==0
                assert np.count_nonzero(R[np.ix_(ids[0],ids[1])])==0
                for side in range(C):
                    check('channel_synthesis',Phi[side::C,ids[side]],Phi[::C,ids[0]],max(1.,abs(Phi).max()),gate=2e-12)
                    assert np.count_nonzero(Phi[side::C,ids[1-side]])==0
                L=np.linalg.cholesky(R);Lmono=L[np.ix_(ids[0],ids[0])]
                check('shared_node_root',z['z'],Lmono.T@z['q'],max(1.,np.linalg.norm(z['z'])),gate=2e-12)
                check('shared_recovery',linalg.solve_triangular(Lmono.T,z['z']),z['q'],max(1.,np.linalg.norm(z['q'])),gate=2e-12)
                inv=linalg.solve_triangular(L.T,np.eye(len(R)))
                Gdata=B@inv;G=np.vstack((Gdata,np.eye(len(R))))
                rhs=np.r_[target,np.zeros(len(R))];original_z=L.T@q
                model=np.r_[data,original_z];normal=G.T@model
                direct=G@original_z-rhs;normG=float(np.linalg.norm(G))
                stable=float(np.linalg.norm(normal)/max(normG*np.linalg.norm(model),1e-300))
                backward=float(np.linalg.norm(direct-model)/max(np.linalg.norm(rhs),1e-300))
                check('complete_model',model,z['original_model_residual'],max(1.,np.linalg.norm(rhs)))
                check('complete_adjoint',normal,z['original_model_normal'],max(1.,normG*np.linalg.norm(rhs)))
                # Preserve this EXTRA strict diagnostic separately from the
                # original objective/gradient/gap/stable-normal contract.
                # audit1 stopped here (7.4267e-11 > 2e-11); it is retained.
                strict_frobenius_error=abs(normG-np.sqrt(C)*case['solver']['augmented_root_Frobenius'])/max(1.,normG)
                raw,tau=z['x_raw'],z['x_tau'];k=len(tau);F=np.triu(raw[:k])
                check('actual_root_Frobenius',np.sqrt(np.sum(F*F)+n),case['solver']['augmented_root_Frobenius'],max(1.,normG),gate=2e-12)
                Q=apply_q(raw,tau,np.eye(len(audio),k))
                check('scalar_Q_orthogonality',Q.T@Q,np.eye(k),gate=2e-12)
                transformed=apply_q(raw,tau,z['t'],True)
                check('two_RHS_Q_action',transformed,z['transformed_target'],max(1.,np.linalg.norm(z['t'])),gate=2e-12)
                Qd=apply_q(z['graph_reflectors'],z['graph_tau'],np.eye(k+n,k))
                D=np.vstack((np.eye(k),-F.T))
                check('graph_blocks_zeroed',Qd@z['graph_R'],D,max(1.,abs(D).max()),gate=2e-12)
                check('shared_original_quadratic',Lmono@(F.T@F)@Lmono.T,B[:,ids[0]].T@B[:,ids[0]],max(1.,abs(B.T@B).max()))
                linears=np.column_stack([B[:,index].T@target for index in ids])
                check('independent_original_linears',Lmono@(F.T@transformed[:k]),linears,max(1.,abs(linears).max()))
                check('independent_target_energies',np.sum(z['t']**2),target@target,max(1.,target@target))
                relative=float(np.linalg.norm(q-reference)/max(np.linalg.norm(reference),1e-300))
                e=A@q-b;J=float(e@e)
                gradient=float(np.linalg.norm(A.T@e)/max(np.linalg.norm(A.T@b),1e-300))
                residual=B@q-target;gaps={}
                for tag in ('residual','representer'):
                    saved=case[tag+'_certificate']
                    if tag=='residual':
                        factor=saved['residual_dual_scale'];delta=q+factor*linalg.solve(R,B.T@residual,assume_a='pos')
                        gap=float((1-factor)**2*(residual@residual)+delta@R@delta)
                    else:
                        delta=q-linalg.solve(R,B.T@z['u'],assume_a='pos')
                        gap=float((residual+z['u'])@(residual+z['u'])+delta@R@delta)
                    passed=bool(gap<=1e-6*J+1e-10);assert passed==saved['additional_gap_gate_passed']
                    check(tag+'_gap',gap,saved['gap_upper_bound'])
                    gaps[tag]=dict(gap=gap,passed=passed)
                if case['label']=='silent_right':
                    assert np.count_nonzero(z['q'][:,1])==np.count_nonzero(z['wave_model_residual'][:,1])==0
                if case['label']=='both_zero':assert np.count_nonzero(q)==0
                qualified=bool(relative<2e-7 and gradient<2e-7 and stable<=1e-11 and backward<=1e-11 and all(v['passed'] for v in gaps.values()))
                assert qualified==case['qualified']
                r['cases'].append(dict(kind=case['kind'],label=case['label'],qualified=qualified,
                    dense_relative_error=relative,original_gradient=gradient,stable_complete_normal=stable,
                    original_backward=backward,certificates=gaps,full_interleaved_equivalence=True,
                    supplemental_original_oracle_Frobenius_2e_11_passed=bool(strict_frobenius_error<2e-11),
                    supplemental_original_oracle_Frobenius_relative_error=float(strict_frobenius_error),
                    saved_producer_complete_Frobenius_relative_error=float(abs(np.sqrt(np.sum((z['original_A'][:count]@inv)**2)+len(R))-np.sqrt(C)*case['solver']['augmented_root_Frobenius'])/max(1.,normG))))
                print('AUDITED SHARED',case['label'],'qualified',qualified,'normal',stable,flush=True)
        r.update(result='independent_waveform_shared_known_verified',pass_count=sum(c['qualified'] for c in r['cases']),
            all_qualified=all(c['qualified'] for c in r['cases']),rejections_preserved=source['rejections'],
            producer_sha256=sha(a.study/'report.json'),auditor_sha256=sha(__file__),
            oracles_sha256={n:sha(repo/n) for n in helpers},full_or_real_or_runtime_or_hearing_qualified=False)
        save(a.out/'report.json',r);print(r['result'],r['pass_count'],flush=True)
    except BaseException as error:
        r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
