"""Independent original12 equations, packed roots and scalar Householder actions."""
import argparse
import os
import shutil
import sys
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
    from observer_supported_v1.audit_oracle import matrices,metric
    from observer_complete_v1.audit_oracle import full_frame
    from observer_frequency_v1.audit_oracle import frame_adjoint
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
    shutil.copy2(__file__,a.out/'executed_audit.py')
    helpers=('tools/observer_supported_v1/audit_oracle.py','tools/observer_complete_v1/audit_oracle.py',
             'tools/observer_frequency_v1/audit_oracle.py','tools/observer_frequency_v1/reduced_oracle.py')
    for j,n in enumerate(helpers):shutil.copy2(repo/n,a.out/f'executed_oracle_{j}.py')
    r=dict(result='running',cases=[],maximum_errors={})
    def check(n,x,y,scale=1.,gate=2e-8):
        x,y=np.asarray(x),np.asarray(y);assert x.shape==y.shape,(n,x.shape,y.shape)
        error=float(np.max(abs(x-y))/scale);r['maximum_errors'][n]=max(error,r['maximum_errors'].get(n,0.))
        assert error<gate,(n,error)
    def vec(z):return np.r_[z.real.ravel(),z.imag.ravel()]
    def apply_q(reflectors,tau,value,transpose=False):
        value=np.array(value,copy=True);vector=value.ndim==1
        value=value[:,None] if vector else value
        indices=range(len(tau)) if transpose else range(len(tau)-1,-1,-1)
        for j in indices:
            v=np.r_[1.,reflectors[j+1:,j]]
            value[j:]-=v[:,None]*(tau[j]*(v@value[j:]))[None]
        return value[:,0] if vector else value
    try:
        source=load(a.study/'report.json');assert source['result']=='waveform_structured_original12_measured'
        assert len(source['cases'])==12
        for n,h in source['sources'].items():assert sha(a.study/'exact_sources'/n)==h
        for n,h in source['inputs'].items():assert sha(n)==h
        for case in source['cases']:
            path=a.study/case['file'];assert sha(path)==case['sha256']
            with np.load(path) as z,np.load(case['original_file']) as old:
                if case['kind']=='Hann':
                    A,b,Phi,R,count=matrices(old['positions'],old['orders'],old['scale'],old['audio'])
                    profile=metric(old['audio'],64.);reference=vec(old['original_dense_nodes']/old['scale'][None])
                    products=[]
                    for probe in z['metric_probes'].T:
                        rows,cover=full_frame(probe[:,None]);full=np.zeros_like(rows)
                        full[profile['keep']]=rows[profile['keep']]*profile['amplitude']**2*profile['weights'][None,:,None]**2
                        products.append(probe/profile['sigma']**2+frame_adjoint(full,cover,len(probe))[:,0])
                    check('finite_metric_probes',np.array(products).T,z['metric_products'],max(1.,abs(z['metric_products']).max()))
                else:
                    A,b,Phi,R=old['A'],old['b'],old['Phi'],old['R'];count=len(Phi);reference=old['original']
                    check('algebra_metric_probes',old['H']@z['metric_probes'],z['metric_products'])
                L=np.linalg.cholesky(R);inverse=linalg.solve_triangular(L.T,np.eye(len(R)))
                B,target=A[:count],b[:count];Gdata=B@inverse
                G=np.vstack((Gdata,np.eye(len(R))));rhs=np.r_[target,np.zeros(len(R))]
                p=z['node_probes']
                for n,expected in (('root',L@p),('root_transpose',L.T@p),('inverse',linalg.solve_triangular(L,p,lower=True)),
                    ('inverse_transpose',linalg.solve_triangular(L.T,p,lower=False)),('apply',R@p)):
                    check('original_packed_'+n,z['node_'+n],expected,max(1.,np.linalg.norm(expected)),gate=2e-12)
                M,H,C=len(z['positions']),len(z['orders']),z['audio'].shape[1]
                indices=np.arange(M)*H*C
                check('original_temporal_K',R[np.ix_(indices,indices)],z['temporal_K'],gate=2e-12)
                check('temporal_root_identity',z['temporal_L']@z['temporal_L'].T,z['temporal_K'],gate=2e-12)
                # Reconstruction is a SMALL known-case audit oracle only;
                # the stream producer never materializes rectangular R.
                F=z['F'] if 'F' in z else np.triu(z['x_raw'][:len(z['x_tau'])])
                k=len(F);m=z['x_reflectors'].shape[0]
                Q=apply_q(z['x_reflectors'],z['x_tau'],np.eye(m,k))
                check('scalar_householder_orthogonality',Q.T@Q,np.eye(k),gate=2e-12)
                transformed=apply_q(z['x_reflectors'],z['x_tau'],z['t'],True)
                check('scalar_target_transform',transformed,z['transformed_target'],max(1.,np.linalg.norm(z['t'])),gate=2e-12)
                # Use the original2e-8 unwhitened-equation audit contract.
                # A new2e-11 whitened comparison failed in audit1; the frozen
                # old graph has the SAME discrepancy, while new-vs-old is
                # about1e-14. Retain that stricter failure as a diagnostic,
                # rather than changing or mislabelling its pass condition.
                solver_L=linalg.block_diag(np.kron(z['temporal_L'],np.eye(H*C)),np.kron(z['temporal_L'],np.eye(H*C)))
                quad=B.T@B;linear=B.T@target
                check('all_original_quadratic_terms',solver_L@(F.T@F)@solver_L.T,quad,max(1.,abs(quad).max()))
                check('all_original_linear_terms',solver_L@(F.T@transformed[:k]),linear,max(1.,abs(linear).max()))
                check('original_constant_term',z['t']@z['t'],target@target,max(1.,target@target))
                original_white=Gdata.T@Gdata
                strict_white_error=float(np.max(abs(F.T@F-original_white))/max(1.,abs(original_white).max()))
                with np.load(case['baseline_file']) as baseline:
                    baseline_white=baseline['F'].T@baseline['F']
                    baseline_white_error=float(np.max(abs(baseline_white-original_white))/max(1.,abs(original_white).max()))
                    check('unchanged_whitened_graph_Gram',F.T@F,baseline_white,max(1.,abs(baseline_white).max()),gate=2e-11)
                    check('unchanged_whitened_graph_linear',F.T@transformed[:k],baseline['X'].T@baseline['t'],max(1.,abs(baseline['X'].T@baseline['t']).max()),gate=2e-11)
                normG=float(np.sqrt(np.sum(Gdata*Gdata)+len(R)))
                check('root_QR_Frobenius',np.sqrt(np.sum(F*F)+len(R)),case['solver']['augmented_root_Frobenius'],max(1.,normG),gate=2e-12)
                T=z['graph_R'];Qd=apply_q(z['graph_reflectors'],z['graph_tau'],np.eye(k+len(R),k))
                D=np.vstack((np.eye(k),-F.T))
                check('graph_QR_identity',Qd@T,D,max(1.,abs(D).max()),gate=2e-12)
                check('graph_Q_orthogonality',Qd.T@Qd,np.eye(k),gate=2e-12)
                check('triangular_graph_coordinates',T.T@z['graph_coordinates'],transformed[:k],max(1.,np.linalg.norm(z['t'])),gate=2e-12)
                reduced=-apply_q(z['graph_reflectors'],z['graph_tau'],np.r_[z['graph_coordinates'],np.zeros(len(R))])
                reduced[:k]=-linalg.solve_triangular(T,z['graph_coordinates'])
                check('full_graph_residual',reduced,z['reduced_model_residual'],max(1.,np.linalg.norm(z['t'])),gate=2e-12)
                coords=-transformed.copy();coords[:k]=reduced[:k]
                check('full_model_Q_mapping',apply_q(z['x_reflectors'],z['x_tau'],coords),z['root_model_residual'],max(1.,np.linalg.norm(z['t'])),gate=2e-12)
                x=z['q'];original_z=L.T@x
                check('original_node_recovery',solver_L.T@x,z['z'],max(1.,np.linalg.norm(original_z)),gate=2e-12)
                direct=G@original_z-rhs
                direct_ratio=float(np.linalg.norm(G.T@direct)/max(normG*np.linalg.norm(direct),1e-300))
                wave=z['wave_model_residual'].reshape(z['audio'].shape)
                if case['kind']=='Hann':
                    rows,_=full_frame(wave);rows=rows[profile['keep']]*profile['amplitude']*profile['weights'][None,:,None]
                    data=np.r_[wave.ravel()/profile['sigma'],vec(rows)]
                else:data=np.linalg.cholesky(old['H']).T@wave.ravel()
                model=np.r_[data,original_z];normal=G.T@model
                stable_ratio=float(np.linalg.norm(normal)/max(normG*np.linalg.norm(model),1e-300))
                backward=float(np.linalg.norm(direct-model)/np.linalg.norm(rhs))
                check('complete_original_model',model,z['original_model_residual'],max(1.,np.linalg.norm(rhs)))
                check('complete_original_normal',normal,z['original_model_normal'],max(1.,normG*np.linalg.norm(rhs)))
                relative=float(np.linalg.norm(x-reference)/np.linalg.norm(reference))
                e=A@x-b;gradient=float(np.linalg.norm(A.T@e)/np.linalg.norm(A.T@b));J=float(e@e)
                residual=B@x-target;gaps={}
                for tag in ('residual','representer'):
                    c=case[tag+'_certificate']
                    if tag=='residual':
                        factor=c['residual_dual_scale'];delta=x+factor*linalg.solve(R,B.T@residual,assume_a='pos')
                        gap=float((1-factor)**2*(residual@residual)+delta@R@delta)
                    else:
                        delta=x-linalg.solve(R,B.T@z['u'],assume_a='pos')
                        gap=float((residual+z['u'])@(residual+z['u'])+delta@R@delta)
                    passed=bool(gap<=1e-6*J+1e-10);assert passed==c['additional_gap_gate_passed']
                    check(tag+'_gap',gap,c['gap_upper_bound'])
                    gaps[tag]=dict(gap=gap,passed=passed)
                original=bool(relative<2e-7 and gradient<2e-7 and all(v['passed'] for v in gaps.values()))
                qualified=bool(original and stable_ratio<=1e-11 and backward<=1e-11 and case['solver']['stable_root_guard_passed'])
                assert qualified==case['qualified'] and original==case['original_equations_and_gap_passed']
                with np.load(case['baseline_file']) as baseline:
                    delta=float(np.linalg.norm(x-baseline['q'])/np.linalg.norm(baseline['q']))
                    assert delta==case['baseline_graph_relative_error']
                r['cases'].append(dict(kind=case['kind'],label=case['label'],dense_relative_error=relative,
                    baseline_graph_relative_error=delta,original_gradient=gradient,certificates=gaps,
                    original_equations_and_gaps_passed=original,original_stable_normal_relative=stable_ratio,
                    original_backward_discrepancy=backward,original_direct_normal_relative=direct_ratio,
                    all_packed_root_maps_and_implicit_Q_verified=True,qualified=qualified,
                    original_unwhitened_equation_audit_gate=2e-8,
                    stricter_whitened_2e_11_diagnostic_passed=bool(strict_white_error<2e-11),
                    stricter_whitened_diagnostic_error=strict_white_error,
                    frozen_baseline_whitened_diagnostic_error=baseline_white_error))
                print('AUDITED',case['label'],'qualified',qualified,'normal',stable_ratio,'direct',direct_ratio,flush=True)
        r.update(result='independent_waveform_structured_original12_verified',pass_count=sum(c['qualified'] for c in r['cases']),
            all_qualified=all(c['qualified'] for c in r['cases']),producer_sha256=sha(a.study/'report.json'),
            auditor_sha256=sha(__file__),oracles_sha256={n:sha(repo/n) for n in helpers},
            source_or_full_or_runtime_or_hearing_qualified=False)
        save(a.out/'report.json',r);print(r['result'],r['pass_count'],flush=True)
    except BaseException as error:
        r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
