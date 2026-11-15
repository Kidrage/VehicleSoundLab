"""Independent original equations, two gaps and full stopping checks for all12."""
import argparse, os, shutil, sys
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
    from observer_supported_v1.audit_oracle import matrices,metric
    from observer_complete_v1.audit_oracle import full_frame
    from observer_frequency_v1.audit_oracle import frame_adjoint
    repo=Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_audit.py')
    helpers=('tools/observer_supported_v1/audit_oracle.py','tools/observer_complete_v1/audit_oracle.py',
        'tools/observer_frequency_v1/audit_oracle.py','tools/observer_frequency_v1/reduced_oracle.py')
    for j,name in enumerate(helpers):shutil.copy2(repo/name,a.out/f'executed_oracle_{j}.py')
    r=dict(result='running',cases=[],maximum_errors={},executed_source_versions={})
    def check(name,x,y,scale=1.,gate=2e-8):
        x,y=np.asarray(x),np.asarray(y);assert x.shape==y.shape,(name,x.shape,y.shape)
        error=float(np.max(abs(x-y))/scale)
        r['maximum_errors'][name]=max(error,r['maximum_errors'].get(name,0.))
        assert error<gate,(name,error)
    def vec(q):return np.r_[q.real.ravel(),q.imag.ravel()]
    try:
        source=load(a.study/'report.json')
        assert source['result']=='waveform_representer_original12_measured' and len(source['cases'])==12
        for name,digest in source['sources'].items():
            assert sha(a.study/'exact_sources'/name)==digest
            r['executed_source_versions'][name]=dict(executed_sha256=digest,current_sha256=sha(repo/name))
        for name,digest in source['inputs'].items():assert sha(name)==digest
        for case in source['cases']:
            path=a.study/case['file'];assert sha(path)==case['sha256']
            with np.load(path) as z,np.load(case['original_file']) as old:
                if case['kind']=='Hann':
                    A,b,Phi,R,count=matrices(old['positions'],old['orders'],old['scale'],old['audio'])
                    reference=vec(old['original_dense_nodes']/old['scale'][None])
                    profile=metric(old['audio'],64.)
                    products=[]
                    for probe in z['metric_probes'].T:
                        rows,coverage=full_frame(probe[:,None])
                        full=np.zeros_like(rows)
                        full[profile['keep']]=rows[profile['keep']]*profile['amplitude']**2*profile['weights'][None,:,None]**2
                        products.append(probe/profile['sigma']**2+frame_adjoint(full,coverage,len(probe))[:,0])
                    check('finite_metric_probes',np.array(products).T,z['metric_products'],max(1.,abs(z['metric_products']).max()))
                else:
                    A,b,Phi,R=old['A'],old['b'],old['Phi'],old['R']
                    count=len(Phi);reference=old['original']
                    check('algebra_metric_probes',old['H']@z['metric_probes'],z['metric_products'])
                B,target=A[:count],b[:count]
                check('original_Phi',Phi,z['Phi'])
                check('original_R',R,z['R'])
                weighted=z['weighted_Phi'];t=z['weighted_target']
                quadratic=B.T@B;linear=B.T@target;constant=float(target@target)
                check('all_source_quadratic_terms',weighted.T@weighted,quadratic,max(1.,abs(quadratic).max()))
                check('all_source_linear_terms',weighted.T@t,linear,max(1.,abs(linear).max()))
                check('target_constant_term',float(t@t),constant,max(1.,constant))
                check('full_QR_identity',z['Q']@z['F'],z['X'],max(1.,abs(z['X']).max()))
                check('full_QR_orthogonal',z['Q'].T@z['Q'],np.eye(z['Q'].shape[1]),gate=2e-12)
                assert z['Q'].shape[1]==min(Phi.shape)
                L=np.linalg.cholesky(R);T=linalg.solve_triangular(L.T,np.eye(len(R)))
                G=np.vstack((B@T,np.eye(len(R))));rhs=np.r_[target,np.zeros(len(R))]
                x=z['q'];original_z=L.T@x
                original_residual=G@original_z-rhs;original_normal=G.T@original_residual
                direct_ratio=float(np.linalg.norm(original_normal)/max(np.linalg.norm(G)*np.linalg.norm(original_residual),1e-300))
                relative=float(np.linalg.norm(x-reference)/np.linalg.norm(reference))
                check('dense_relative_error',relative,case['dense_relative_error'])
                dense=linalg.lstsq(A,b,lapack_driver='gelsd')[0]
                check('original_dense_solution',x,dense,max(1.,np.linalg.norm(dense)))
                e=A@x-b;gradient=float(np.linalg.norm(A.T@e)/np.linalg.norm(A.T@b))
                check('original_gradient',gradient,case['original_gradient'])
                primal=float(e@e);residual=B@x-target;certs={}
                for tag in ('residual','representer'):
                    cert=case[tag+'_certificate']
                    if tag=='residual':
                        factor=cert['residual_dual_scale'];restored=linalg.solve(R,B.T@residual,assume_a='pos')
                        delta=x+factor*restored
                        gap=float((1-factor)**2*(residual@residual)+delta@R@delta)
                    else:
                        u=z['u'];delta=x-linalg.solve(R,B.T@u,assume_a='pos')
                        gap=float((residual+u)@(residual+u)+delta@R@delta)
                    check(tag+'_original_gap',gap,cert['gap_upper_bound'])
                    passed=bool(gap<=1e-6*primal+1e-10)
                    assert passed==cert['additional_gap_gate_passed']
                    certs[tag]=dict(gap=gap,passed=passed)
                original_pass=bool(relative<2e-7 and gradient<2e-7 and all(c['passed'] for c in certs.values()))
                assert original_pass==case['original_equations_and_gap_passed']
                raw=z['X'].T@(z['X']@z['z']-z['t'])+z['z']
                denom=np.sqrt(np.sum(z['X']**2)+len(R))*np.sqrt(np.sum((z['X']@z['z']-z['t'])**2)+np.sum(z['z']**2))
                root_ratio=float(np.linalg.norm(raw)/max(denom,1e-300))
                check('root_direct_normal',raw,z['direct_transformed_normal'])
                assert (root_ratio<=1e-11)==case['solver']['original_direct_whitened_normal_passed']
                strict=bool(original_pass and direct_ratio<=1e-11)
                record=dict(kind=case['kind'],label=case['label'],dense_relative_error=relative,
                    original_gradient=gradient,certificates=certs,original_equations_and_gaps_passed=original_pass,
                    root_direct_normal_relative=root_ratio,root_direct_normal_passed=bool(root_ratio<=1e-11),
                    independent_original_direct_normal_relative=direct_ratio,
                    independent_original_direct_normal_passed=bool(direct_ratio<=1e-11),
                    qualified_with_original_direct_stopping=strict)
                if 'wave_model_residual' in z:
                    wave=z['wave_model_residual'].reshape(z['audio'].shape)
                    if case['kind']=='Hann':
                        # Apply the FROZEN original weights/scales, never refit
                        # a metric to the model residual itself.
                        rows,_=full_frame(wave)
                        weighted_rows=rows[profile['keep']]*profile['amplitude']*profile['weights'][None,:,None]
                        model_data=np.r_[wave.ravel()/profile['sigma'],vec(weighted_rows)]
                    else:
                        model_data=np.linalg.cholesky(old['H']).T@wave.ravel()
                    model=np.r_[model_data,original_z]
                    modeled_normal=G.T@model
                    modeled_ratio=float(np.linalg.norm(modeled_normal)/max(np.linalg.norm(G)*np.linalg.norm(model),1e-300))
                    discrepancy=float(np.linalg.norm(original_residual-model)/np.linalg.norm(rhs))
                    check('original_modeled_residual',model,z['original_model_residual'],max(1.,np.linalg.norm(rhs)))
                    check('original_modeled_complete_normal',modeled_normal,z['original_model_normal'],max(1.,np.linalg.norm(G)*np.linalg.norm(rhs)))
                    qualified=bool(original_pass and modeled_ratio<=1e-11 and discrepancy<=1e-11)
                    assert qualified==case['qualified']
                    record.update(qualified=qualified,original_stable_normal_relative=modeled_ratio,
                        original_backward_discrepancy=discrepancy)
                else:record['qualified']=strict
                r['cases'].append(record)
                print('AUDITED',case['label'],'original',original_pass,'direct',direct_ratio,'qualified',record['qualified'],flush=True)
        r.update(result='independent_waveform_representer_original12_measured',
            all_original_equations_and_gaps_passed=all(c['original_equations_and_gaps_passed'] for c in r['cases']),
            all_qualified=all(c['qualified'] for c in r['cases']),pass_count=sum(c['qualified'] for c in r['cases']),
            producer_sha256=sha(a.study/'report.json'),auditor_sha256=sha(__file__),
            oracles_sha256={n:sha(repo/n) for n in helpers},full_or_source_or_runtime_qualified=False)
        save(a.out/'report.json',r);print(r['result'],r['pass_count'],flush=True)
    except BaseException as error:
        r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
