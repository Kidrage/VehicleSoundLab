"""Audit every compensated row/gradient via independent exact integer products."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load,save,sha


def independent_variants(z):
    import numpy as np
    from observer_complete_v1.synthesis import WaveSynthesis
    from constrained_source_operator_v1.oracle import table
    frames=int(z['frames']);h=len(z['orders']);m=len(z['positions']);half=m*h*2
    old=WaveSynthesis(frames,z['positions'],z['orders'],2)
    basis=np.zeros((frames,m))
    for j,(lo,hi,phase,hat) in enumerate(old.operator.support):basis[lo:hi,j]=hat
    trig=table(z['orders'])[np.arange(frames)%1024]
    matrices=[np.zeros((frames*2,2*half)) for _ in range(2)]
    for k,order in enumerate(z['orders']):
        for imaginary in (False,True):
            bin=np.zeros((513,1),complex);bin[order,0]=1j if imaginary else 1.
            cycle=np.fft.irfft(bin,n=1024,axis=0)[:,0]*512
            carrier=cycle[np.arange(frames)%1024]
            scalar=-trig[:,k].imag if imaginary else trig[:,k].real
            for j in range(m):
                for channel in (0,1):
                    index=(j*h+k)*2+channel+int(imaginary)*half
                    matrices[0][channel::2,index]=basis[:,j]*scalar*z['scale'][k,0]
                    matrices[1][channel::2,index]=basis[:,j]*carrier*z['scale'][k,0]
    return matrices


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','study','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from constrained_source_operator_v1 import oracle
    from operator_roundoff_v1.exact_dyadic import matvec
    a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_audit.py')
    r=dict(result='running',cases=[])
    try:
        repo=Path(__file__).resolve().parents[1];source=load(a.study/'report.json')
        assert source['result']=='saved_small_operator_roundoff_decomposed' and source['known_before_saved_packet_use']
        for name,digest in source['sources'].items():assert sha(repo/name)==sha(a.study/'exact_sources'/name)==digest
        for path,digest in source['inputs'].items():assert sha(path)==digest
        assert len(source['known']['cases'])==12 and source['known']['passed'] and len(source['cases'])==4
        for case in source['cases']:
            name=case['name'];comparisons={};counts=dict(exact_output_values=0,exact_products=0);maximum_ulp=0.
            r['active_case']=dict(name=name,comparisons=comparisons)
            def check(label,left,right):
                left,right=np.asarray(left),np.asarray(right);assert left.shape==right.shape
                error=float(np.max(abs(left-right)))/max(float(np.max(abs(right))),1e-300)
                comparisons[label]=error
                if not np.isfinite(error) or error>2e-11:raise ValueError((name,label,error))
            def exact(label,value,matrix,vector):
                nonlocal maximum_ulp
                expected=matvec(matrix,vector);given=np.asarray(value).ravel()
                assert given.shape==expected.shape
                ulp=np.abs(np.spacing(expected));distance=np.abs(given-expected)/ulp
                maximum_ulp=max(maximum_ulp,float(np.max(distance)))
                assert np.isfinite(distance).all() and np.max(distance)<=1.,(name,label,float(np.max(distance)))
                comparisons[label]=float(np.max(distance));counts['exact_output_values']+=len(expected)
                counts['exact_products']+=matrix.size
                return expected.reshape(np.asarray(value).shape)
            path=next(Path(p) for p in source['inputs'] if Path(p).parent.name==name and Path(p).name=='operators.npz')
            with np.load(path) as f:z={key:f[key] for key in f.files}
            packet=a.study/name/'roundoff.npz';assert sha(packet)==case['packet_sha256']
            with np.load(packet) as f:saved={key:f[key] for key in f.files}
            phi,b,groups,prior=oracle.dense(z);x=z['x'];frames=int(z['frames'])
            exact('source_compensated_all_rows',saved['dense_source_compensated'],phi,x)
            first,second=independent_variants(z)
            exact('declared_hat_compensated_all_rows',saved['declared_hat_source_compensated'],first,x)
            exact('fft_carrier_compensated_all_rows',saved['fft_carrier_source_compensated'],second,x)
            naive=(phi@x).reshape(frames,2);check('source_naive_all_rows',saved['dense_source_naive'],naive)
            observed=oracle.target(z,naive);observed_delta=oracle.target(z,naive-z['wave'])
            for g in range(7):
                dense=groups[g]@x;reference=z['target_'+str(g)]
                exact('group_'+str(g)+'_compensated_all_rows',saved['group_'+str(g)+'_compensated'],groups[g],x)
                total=dense-reference;source_part=observed[g]-reference;column=dense-observed[g]
                for field,value in (('dense',dense),('total',total),('source',source_part),('column',column),('observation',source_part-observed_delta[g])):
                    check('group_'+str(g)+'_'+field,saved['group_'+str(g)+'_'+field],value)
                row=case['groups'][g];check('group_'+str(g)+'_absolute_peak',row['total']['error_peak'],np.max(abs(total)))
                check('group_'+str(g)+'_reference_peak',row['total']['reference_peak'],np.max(abs(reference)))
                check('group_'+str(g)+'_signed_identity',row['signed_decomposition_identity_error_peak'],np.max(abs(total-(source_part+column))))
            residual=oracle.full(z,z['wave'])-oracle.full(z,z['audio']);check('objective_residual_all_rows',saved['objective_residual'],residual)
            matrix=np.column_stack((b.T,prior));rhs=np.r_[residual,x]
            gradient=exact('objective_gradient_every_coefficient',saved['gradient_compensated'],matrix,rhs)
            check('dense_naive_gradient',saved['gradient_dense_naive'],b.T@residual+prior@x)
            error=z['gradient']-saved['gradient_compensated'];g=case['gradient']
            check('gradient_absolute_peak',g['FFT_vs_compensated']['error_peak'],np.max(abs(error)))
            check('absolute_product_sum',g['absolute_product_sum_max'],np.max(abs(matrix)@abs(rhs)))
            check('backward_diagnostic',g['normalized_backward_discrepancy'],np.linalg.norm(error)/max(np.linalg.norm(b)*np.linalg.norm(residual)+np.linalg.norm(prior)*np.linalg.norm(x),1e-300))
            r['cases'].append(dict(name=name,comparisons=comparisons,**counts,maximum_ULP_error=maximum_ulp,
                all_compensated_source_target_gradient_outputs_audited=True))
            save(a.out/'report.json',r);print('EXACT_DYADIC_AUDIT',name,counts,maximum_ulp,flush=True)
        r.pop('active_case',None)
        r.update(result='saved_known_roundoff_and_compensated_reductions_verified',verification_passed=True,
            producer_sha256=sha(a.study/'report.json'),original_19_failed_operator_checks_not_relabelled=True,
            whole_operator_or_constrained_solver_qualification=False,new_C1_source_eligible_for_statistics=False,
            exact_reference_is_rounded_FP64_matrices_not_exact_continuous_OSC=True)
        save(a.out/'report.json',r);print(r['result'],flush=True)
    except BaseException as error:r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
