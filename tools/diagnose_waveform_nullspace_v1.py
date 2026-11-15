"""High-precision reduced equations and Householder identity-block diagnostics."""
import argparse
import math
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
    from decimal import Decimal,localcontext
    from audit_waveform_representer_controls_v1 import exact_solution
    repo=Path(__file__).resolve().parents[1]
    plan=load(repo/'research/waveform_nullspace_diagnostic_v1_plan.json')
    a.out.mkdir(parents=True,exist_ok=False)
    shutil.copy2(__file__,a.out/'executed_diagnosis.py')
    shutil.copy2(repo/'tools/audit_waveform_representer_controls_v1.py',a.out/'executed_decimal_oracle.py')
    source=load(a.study/'report.json')
    assert source['result']=='waveform_representer_original12_measured'
    def transform(matrix,rhs):
        (reflectors,tau),F=linalg.qr(matrix,mode='raw')
        reflectors=reflectors[:,:len(tau)]
        ormqr=linalg.get_lapack_funcs('ormqr',(reflectors,))
        _,work,flag=ormqr('L','T',reflectors,tau,rhs,lwork=-1)
        assert flag==0
        value,_,flag=ormqr('L','T',reflectors,tau,rhs,lwork=int(work[0]))
        assert flag==0
        return F,value
    result=dict(result='running',cases=[],inputs={str(a.study/'report.json'):sha(a.study/'report.json')},
        sources={n:sha(repo/n) for n in ('tools/diagnose_waveform_nullspace_v1.py',
            'tools/audit_waveform_representer_controls_v1.py','research/waveform_nullspace_diagnostic_v1_plan.json')},
        new_fits_or_runtime_or_audio_changes=False)
    try:
        cases={c['label']:c for c in source['cases']}
        for label in plan['fixed_cases']:
            case=cases[label];path=a.study/case['file']
            assert sha(path)==case['sha256'];result['inputs'][str(path)]=sha(path)
            with np.load(path) as z:
                F0=z['F'];k,n=F0.shape
                F,target=transform(z['X'],z['t'][:,None])
                assert np.array_equal(F,F0)
                c=target[:k];D=z['nullspace_generators'];current=z['z'][:,None]
                rhs=np.vstack((c,np.zeros((n,1))))
                _,coordinates=transform(D,rhs)
                # Repeat the executed raw-Householder operation and require
                # exact identity before diagnosing its reduced target.
                coordinates[k:]=0
                (reflectors,tau),_=linalg.qr(D,mode='raw')
                ormqr=linalg.get_lapack_funcs('ormqr',(reflectors,))
                _,work,flag=ormqr('L','N',reflectors,tau,coordinates,lwork=-1)
                assert flag==0
                repeated,_,flag=ormqr('L','N',reflectors,tau,coordinates,lwork=int(work[0]))
                assert flag==0 and np.array_equal(-repeated[:,0],z['reduced_primal_model_residual'])
                exacts=[exact_solution(F,np.eye(k),np.eye(n),c,digits) for digits in (80,110)]
                precision=max(abs(x-y) for r,s in zip(*exacts) for x,y in zip(r,s))
                assert precision<Decimal('1e-60')
                exact=np.array([[float(x) for x in row] for row in exacts[1]])
                # Decimal full reduced gradient at the actual stored z;
                # this does not replace it with the modeled residual.
                with localcontext() as ctx:
                    ctx.prec=110
                    dd=lambda x:Decimal.from_float(float(x))
                    P=[[dd(x) for x in row] for row in F]
                    q=[dd(x) for x in current[:,0]];b=[dd(x) for x in c[:,0]]
                    residual=[sum((v*w for v,w in zip(row,q)),Decimal(0))-y for row,y in zip(P,b)]
                    gradient=[sum((P[i][j]*residual[i] for i in range(k)),Decimal(0))+q[j] for j in range(n)]
                    true_normal=float(sum((x*x for x in gradient),Decimal(0)).sqrt())
                U,T=linalg.qr(D,mode='economic')
                top=U[:k]
                reconstructed=linalg.solve_triangular(T,np.eye(k))
                residual_top=top@T-np.eye(k)
                # sumprod improves accumulation; it is not assumed to be
                # arbitrary precision or an interval bound.
                top_list=top.tolist();columns=T.T.tolist()
                fsum_identity=np.array([[math.sumprod(row,column) for column in columns] for row in top_list])-np.eye(k)
                weights=[case[tag+'_certificate']['gap_upper_bound']/(1e-6*case[tag+'_certificate']['primal']+1e-10)
                         for tag in ('residual','representer')]
                arrays=a.out/(label+'.npz')
                np.savez_compressed(arrays,F=F,c=c,current_z=current,Decimal110_z=exact,
                    U=U,T=T,reconstructed_top=reconstructed,top_identity_error=residual_top,
                    sumprod_top_identity_error=fsum_identity)
                row=dict(label=label,Decimal_precisions=[80,110],Decimal_solution_agreement=str(precision),
                    exact_executed_projection_reproduced=True,
                    current_vs_reduced_Decimal_relative_error=float(np.linalg.norm(current-exact)/np.linalg.norm(exact)),
                    current_reduced_Decimal_gradient_norm=true_normal,
                    current_reduced_Decimal_negative_residual_dual_gap=true_normal**2,
                    identity_top_norm=float(np.linalg.norm(top)),
                    identity_top_vs_triangular_relative_error=float(np.linalg.norm(top-reconstructed)/np.linalg.norm(reconstructed)),
                    top_identity_error=float(np.linalg.norm(residual_top)),
                    sumprod_top_identity_error=float(np.linalg.norm(fsum_identity)),
                    full_U_orthogonality=float(np.linalg.norm(U.T@U-np.eye(k))),
                    original_modeled_normal=case['solver']['original_stable_normal_relative'],
                    original_backward_discrepancy=case['solver']['original_backward_discrepancy'],
                    original_gap_ratios=weights,original_qualified=case['qualified'],
                    file=arrays.name,sha256=sha(arrays))
                result['cases'].append(row);save(a.out/'report.json',result)
                print(row,flush=True)
        result.update(result='waveform_nullspace_reduced_precision_diagnosed',
            all_four_fixed_cases_measured=True,original_failed_labels=[c['label'] for c in result['cases'] if not c['original_qualified']],
            full_scale_or_material_or_C_or_hearing_qualified=False)
        save(a.out/'report.json',result)
    except BaseException as error:
        result.update(result='failed',error=repr(error));save(a.out/'report.json',result);raise


if __name__=='__main__':main()
