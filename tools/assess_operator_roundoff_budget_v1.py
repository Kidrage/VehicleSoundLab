"""Exact-product magnitude budgets for the SAME small rounded-matrix inputs.

The standard gamma bound covers only FP64 dot-product arithmetic on fixed
matrix entries, under normal finite arithmetic. It does not certify FFTs or
the construction of those matrix entries.
"""
import argparse
from fractions import Fraction
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','study','audit','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from constrained_source_operator_v1 import oracle
    from operator_roundoff_v1.exact_dyadic import matvec
    a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_budget.py')
    r=dict(result='running',cases=[],sources={'tools/assess_operator_roundoff_budget_v1.py':sha(__file__)})
    try:
        study=load(a.study/'report.json');audit=load(a.audit/'report.json')
        assert audit['verification_passed'] and audit['producer_sha256']==sha(a.study/'report.json')
        r['inputs']={str(a.study/'report.json'):sha(a.study/'report.json'),str(a.audit/'report.json'):sha(a.audit/'report.json')}
        for case in study['cases']:
            name=case['name'];path=next(Path(p) for p in study['inputs'] if Path(p).parent.name==name and Path(p).name=='operators.npz')
            packet=a.study/name/'roundoff.npz';assert sha(path)==study['inputs'][str(path)] and sha(packet)==case['packet_sha256']
            with np.load(path) as f:z={key:f[key] for key in f.files}
            with np.load(packet) as f:s={key:f[key] for key in f.files}
            _,b,groups,prior=oracle.dense(z);x=z['x'];rows=[]
            def budget(label,matrix,vector,naive,accurate,other):
                # Explicitly establish the safe normal-product range assumed
                # by this dataset's arithmetic-only error model.
                for value in (matrix,vector):
                    absolute=np.abs(value)
                    assert np.isfinite(value).all() and np.all((absolute==0)|((absolute>=2.**-400)&(absolute<=2.**400)))
                n=matrix.shape[1];k=2*n+3;u=Fraction(1,2**53);gamma=k*u/(1-k*u)
                exact_rounded_sums=matvec(np.abs(matrix),np.abs(vector))
                upper=float(np.max(exact_rounded_sums))
                if upper:upper=float(np.nextafter(upper,np.inf))
                product_bound=gamma*Fraction.from_float(upper)
                bound=float(product_bound)
                if bound:bound=float(np.nextafter(bound,np.inf))
                # The independently audited accurate outputs are correctly
                # rounded for this dataset; one ULP safely covers that rounding.
                output_rounding=float(np.max(np.abs(np.spacing(accurate)))) if np.count_nonzero(accurate) else 0.
                total_bound=float(np.nextafter(bound+output_rounding,np.inf)) if bound or output_rounding else 0.
                actual=float(np.max(abs(naive-accurate)));other_error=float(np.max(abs(other-accurate)))
                assert actual<=total_bound,(name,label,actual,total_bound)
                rows.append(dict(group=label,terms=n,gamma_upper=float(np.nextafter(float(gamma),np.inf)),
                    exact_product_absolute_sum_upper=upper,arithmetic_only_absolute_bound=total_bound,
                    observed_dense_reduction_error_peak=actual,other_path_error_peak=other_error,
                    other_path_exceeds_dense_arithmetic_only_budget=bool(other_error>total_bound),
                    no_whole_operator_gate_replacement=True))
            for g in range(7):budget(str(g),groups[g],x,s['group_'+str(g)+'_dense'],s['group_'+str(g)+'_compensated'],z['target_'+str(g)])
            matrix=np.column_stack((b.T,prior));rhs=np.r_[s['objective_residual'],x]
            budget('gradient',matrix,rhs,s['gradient_dense_naive'],s['gradient_compensated'],z['gradient'])
            r['cases'].append(dict(name=name,groups=rows));save(a.out/'report.json',r)
            print('ARITHMETIC_BUDGET',name,sum(v['other_path_exceeds_dense_arithmetic_only_budget'] for v in rows),flush=True)
        r.update(result='saved_known_fixed_matrix_arithmetic_budgets_assessed',
            verification_passed=True,all_dense_reduction_errors_within_derived_budgets=True,
            standard_normal_FP64_dot_arithmetic_assumptions_explicit=True,
            bounds_do_not_cover_matrix_construction_or_FFT_or_sound_fidelity=True,
            original_19_operator_failures_not_relabelled=True,whole_operator_qualification=False,
            new_C1_source_eligible_for_statistics=False)
        save(a.out/'report.json',r);print(r['result'],flush=True)
    except BaseException as error:r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
