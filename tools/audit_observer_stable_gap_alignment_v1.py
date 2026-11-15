"""Relate terminal model/direct normals to both original-space gap identities."""
import argparse, os, shutil, sys
from pathlib import Path
from research_archive_v1 import load, save, sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','study','audit','identity','out'):
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy import linalg
    from observer_supported_v1.full_oracle import FullOracle,vec
    repo=Path(__file__).resolve().parents[1]
    a.out.mkdir(exist_ok=False)
    shutil.copy2(__file__,a.out/'executed_audit.py')
    r=dict(result='running',inputs={},sources={},maximum_absolute_errors={})
    try:
        # Known subspace controls precede any full-case read. The first
        # column is a 3-4-5 rotation, the second is an independent axis.
        test_basis=np.array([[.6,0],[.8,0],[0,1],[0,0]])
        test_outside=np.array([-.8,.6,0,0])
        controls=[]
        for label,coeff,weight in (('inside',[2.,-3.],0.),('outside',[0.,0.],4.),
                ('mixed',[2.,-3.],4.),('small',[2**-30,-2**-31],2**-29),('zero',[0.,0.],0.)):
            expected=np.asarray(coeff)
            g=test_basis@expected+weight*test_outside
            coordinates=test_basis.T@g
            outside=g-test_basis@coordinates
            error=max(float(np.max(abs(coordinates-expected))),float(np.max(abs(outside-weight*test_outside))))
            assert error<2e-14
            total=float(g@g);parts=float(coordinates@coordinates+outside@outside)
            assert abs(total-parts)<2e-14*max(1.,total)
            controls.append(dict(label=label,maximum_absolute_error=error,total_squared=total,parts_squared=parts))
        source,audit,identity=(load(path/'report.json') for path in (a.study,a.audit,a.identity))
        assert source['result']=='observer_stable_full_known_measured'
        assert audit['result']=='independent_observer_stable_full_passed'
        assert audit['producer_sha256']==sha(a.study/'report.json')
        assert identity['result']=='independent_observer_stationarity_gap_identity_passed'
        assert len(identity['controls'])==6 and identity['new_solves']==0
        for path in (a.study/'report.json',a.study/'capture.npz',a.audit/'report.json',a.identity/'report.json'):
            r['inputs'][str(path)]=sha(path)
        assert r['inputs'][str(a.study/'capture.npz')]==source['capture_sha256']
        helpers=('tools/observer_supported_v1/full_oracle.py','tools/observer_supported_v1/audit_oracle.py',
            'tools/observer_frequency_v1/reduced_oracle.py','tools/observer_frequency_v1/audit_oracle.py','tools/observer_complete_v1/audit_oracle.py')
        for j,name in enumerate(helpers):
            shutil.copy2(repo/name,a.out/f'executed_oracle_{j}.py');r['sources'][name]=sha(repo/name)
        def check(name,x,y):
            error=float(np.max(abs(np.asarray(x)-np.asarray(y))))
            r['maximum_absolute_errors'][name]=error
            assert error<2e-8,(name,error)
        with np.load(a.study/'capture.npz') as z:
            oracle=FullOracle(z['audio'],z['positions'],z['orders'],z['scale'])
            shape=z['fitted'].shape;n=shape[0];L=np.linalg.cholesky(oracle.R)
            def white(v):return linalg.solve_triangular(L,v.reshape(n,-1),lower=True).reshape(shape)
            def backward(v):return vec(white(oracle.nodes(oracle.data_adjoint(v[:oracle.data_size])))+oracle.nodes(v[oracle.data_size:]))
            direct,modeled=(backward(z[key]) for key in ('direct_residual','stable_residual'))
            check('direct_complete_adjoint',direct,z['direct_normal'])
            check('modeled_complete_adjoint',modeled,z['stable_normal'])
            delta=z['direct_residual']-z['stable_residual']
            delta_normal=backward(delta)
            check('normal_difference_linearity',direct-modeled,delta_normal)
            q_from_z=linalg.solve_triangular(L.T,oracle.nodes(z['z']).reshape(n,-1),lower=False).reshape(shape)
            direct_data=oracle.data_forward(vec(q_from_z))-oracle.target()
            check('direct_residual_at_saved_z',direct_data,z['direct_residual'][:oracle.data_size])
            assert np.array_equal(z['direct_residual'][oracle.data_size:],z['z'])
            q=z['fitted']/z['scale'][None]
            e=oracle.data_forward(vec(q))-oracle.target()
            p=oracle.nodes(oracle.data_adjoint(e))
            original_normal=white(p)+(L.T@q.reshape(n,-1)).reshape(shape)
            displacement=q+linalg.solve(oracle.R,p.reshape(n,-1),assume_a='pos').reshape(shape)
            gap_at_negative_residual=oracle.penalty(displacement)
            norm_squared=float(np.sum(abs(original_normal)**2))
            check('gap_at_negative_residual_identity',gap_at_negative_residual,norm_squared)
            u=z['u'];saved_defect=e+u
            saved_normal=(L.T@q.reshape(n,-1)).reshape(shape)-white(oracle.nodes(oracle.data_adjoint(u)))
            saved_gap=float(saved_defect@saved_defect)+float(np.sum(abs(saved_normal)**2))
            check('original_saved_dual_gap',saved_gap,source['representer_certificate']['gap_upper_bound'])
            gap_gate=1e-6*source['representer_certificate']['primal']+1e-10
            assert (saved_gap<=gap_gate)==source['representer_certificate']['additional_gap_gate_passed']
            dn,mn,nn=(float(np.linalg.norm(v)) for v in (direct,modeled,delta_normal))
            assert max(0.,mn-nn)-2e-8<=dn<=mn+nn+2e-8
            path=a.study/'basis/V.bin'
            digest=sha(path)
            assert digest=={Path(k).as_posix():v for k,v in source['basis_files'].items()}['basis/V.bin']
            r['inputs'][str(path)]=digest
            V=np.memmap(path,dtype='float64',mode='r',shape=tuple(source['solver']['basis_shapes']['V']),order='F')
            decompositions={}
            coefficients={}
            for name,g in (('direct',direct),('modeled',modeled),('difference',delta_normal)):
                coordinates=V.T@g
                outside=g-V@coordinates
                total=float(g@g);inside=float(coordinates@coordinates);remaining=float(outside@outside)
                error=abs(total-inside-remaining)/max(total,1e-300)
                assert error<2e-10,(name,error)
                decompositions[name]=dict(complete_squared=total,inside_squared=inside,outside_squared=remaining,
                    outside_energy_fraction=remaining/max(total,1e-300),relative_Pythagoras_error=error)
                coefficients[name+'_in_V']=coordinates
            V._mmap.close()
            np.savez_compressed(a.out/'normals.npz',direct=direct,modeled=modeled,delta_normal=delta_normal,
                fitted_original_normal=original_normal,saved_dual_normal=saved_normal,saved_dual_residual_defect=saved_defect,**coefficients)
            r.update(result='independent_observer_stable_gap_alignment_passed',direct_normal_norm=dn,
                modeled_normal_norm=mn,normal_difference_norm=nn,normal_difference_relative_to_direct=nn/max(dn,1e-300),
                direct_normal_squared=dn*dn,modeled_normal_squared=mn*mn,
                fitted_original_normal_squared=norm_squared,gap_at_negative_residual=gap_at_negative_residual,
                original_saved_dual_gap=saved_gap,original_saved_gap_gate=gap_gate,
                original_saved_gap_passed=bool(saved_gap<=gap_gate),
                model_normal_squared_would_pass_gap=bool(mn*mn<=gap_gate),
                saved_dual_residual_defect_norm=float(np.linalg.norm(saved_defect)),
                fitted_node_roundtrip_normal_difference=float(np.linalg.norm(vec(original_normal)-direct)),
                subspace_known_controls=controls,Krylov_subspace_normal_decomposition=decompositions,
                normals_sha256=sha(a.out/'normals.npz'),solver_qualified_unchanged=audit['solver_qualified'],
                no_new_solves=True,no_material_or_runtime_or_hearing_change=True,
                triangle_check_is_floating_point_not_interval_bound=True,auditor_sha256=sha(__file__))
        save(a.out/'report.json',r)
        print(r['result'],'model/direct/difference',r['modeled_normal_norm'],r['direct_normal_norm'],r['normal_difference_norm'],flush=True)
    except BaseException as error:
        r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':
    main()
