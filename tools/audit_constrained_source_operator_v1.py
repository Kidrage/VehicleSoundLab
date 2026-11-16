"""Independent complete known forward/adjoint/dense and original-metric audit."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','study','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from constrained_source_operator_v1 import oracle
    from locked_source_guard_v1.measurement import declared,fidelity
    r=dict(result='running',cases=[]);a.out.mkdir(parents=True,exist_ok=False)
    shutil.copy2(__file__,a.out/'executed_audit.py')
    try:
        report=load(a.study/'report.json');assert report['result']=='complete_known_matrixfree_source_operators_executed'
        repo=Path(__file__).resolve().parents[1]
        for name,digest in report['sources'].items():assert sha(repo/name)==sha(a.study/'exact_sources'/name)==digest
        assert len(report['cases'])==5
        for case in report['cases']:
            comparisons={};elements=0
            current=dict(name=case['name'],comparisons=comparisons)
            r['active_case']=current
            def check(name,got,expected):
                nonlocal elements
                got,expected=np.asarray(got),np.asarray(expected);assert got.shape==expected.shape,name
                scale=max(float(np.max(np.abs(expected))),1e-300)
                error=float(np.max(np.abs(got-expected)))/scale;elements+=got.size;comparisons[name]=error
                if not np.isfinite(error) or error>2e-11:raise ValueError((case['name'],name,error))
            path=a.study/case['name']/'operators.npz';assert sha(path)==case['packet_sha256']
            with np.load(path) as f:z={key:f[key] for key in f.files}
            x=z['x'];wave=oracle.source(z,x)
            check('every_source_wave_sample',z['wave'],wave)
            check('every_source_adjoint_coefficient',z['source_adjoint'],oracle.source_adjoint(z,z['wave_dual']))
            # Observer comparisons use exactly the saved declared wave, so
            # source roundoff is measured separately from observation arithmetic.
            check('every_full_observation_row',z['full_forward'],oracle.full(z,z['wave']))
            groups=oracle.target(z,z['wave'])
            for g,expected in enumerate(groups):check('every_target_group_'+str(g),z['target_'+str(g)],expected)
            check('every_full_adjoint_coefficient',z['full_adjoint'],oracle.full_adjoint(z,z['full_dual']))
            dual=tuple(z['target_dual_'+str(g)] for g in range(7))
            check('every_target_adjoint_coefficient',z['target_adjoint'],oracle.target_adjoint(z,dual))
            check('every_prior_coefficient',z['prior_apply'],oracle.prior(z,x))
            check('every_prior_inverse_coefficient',z['prior_inverse'],oracle.prior(z,x,inverse=True))
            residual=oracle.full(z,z['wave'])-oracle.full(z,z['audio'])
            check('objective',case['objective'],.5*residual@residual+.5*x@oracle.prior(z,x))
            check('every_objective_gradient_coefficient',z['gradient'],oracle.full_adjoint(z,residual)+oracle.prior(z,x))
            metrics=declared(z['audio'],z['wave'],float(z['amplitude']),z['weights'])
            for key,expected in metrics.items():
                old=case['assessment']['metrics'][key]
                if any(v is None for v in np.asarray(expected,dtype=object).ravel()):assert old==expected
                else:check('original_metric_'+key,old,expected)
            assert case['assessment']['original_fidelity_passed']==fidelity(metrics)
            dense_checked=False
            if len(x)<=32:
                phi,b,t,rmat=oracle.dense(z)
                check('dense_source_all_rows',z['wave'].ravel(),phi@x)
                check('dense_source_all_adjoint_entries',z['source_adjoint'],phi.T@z['wave_dual'].ravel())
                check('dense_full_all_rows',z['full_forward'],b@x)
                check('dense_full_all_adjoint_entries',z['full_adjoint'],b.T@z['full_dual'])
                for g in range(7):check('dense_target_all_rows_'+str(g),z['target_'+str(g)],t[g]@x)
                check('dense_target_all_adjoint_entries',z['target_adjoint'],sum(m.T@y for m,y in zip(t,dual)))
                check('dense_prior_all_entries',z['prior_apply'],rmat@x)
                check('dense_gradient_all_entries',z['gradient'],b.T@(b@x-oracle.full(z,z['audio']))+rmat@x)
                dense_checked=True
                if 'null_vector' in z:
                    check('independent_null_wave',z['null_wave'],(phi@z['null_vector']).reshape(-1,2))
                    assert np.linalg.norm(z['null_vector'])==1. and not np.count_nonzero(z['null_wave'])
            else:
                assert (case['frames'],case['nodes'],case['orders'],case['unknowns'])==(18430,73,288,84096)
                expected_whole=1+(case['frames']-4096)//256
                expected_target=1+(case['frames']-8192)//256
                assert (expected_whole,expected_target)==(56,40)
                assert (case['whole_supported_windows'],case['target_supported_windows'])==(expected_whole,expected_target)
            r['cases'].append(dict(name=case['name'],comparisons=comparisons,elements_checked=elements,
                dense_all_rows_and_adjoint_entries_checked=dense_checked,complete_original_metrics_checked=17,
                maximum_scaled_error=max(comparisons.values())))
            save(a.out/'report.json',r);print('INDEPENDENT_OPERATOR',case['name'],elements,max(comparisons.values()),flush=True)
        # Undefined zero-target ratios must remain ineligible, including tiny errors.
        zero=np.zeros((8193,2));bad=zero.copy();bad[3000,0]=1e-100
        bad_metrics=declared(zero,bad,1.,np.ones(2049));assert not fidelity(bad_metrics)
        assert bad_metrics['target_wave_NRMSE'] is None
        r.pop('active_case',None)
        r.update(result='complete_known_matrixfree_source_operators_verified',verification_passed=True,
            producer_sha256=sha(a.study/'report.json'),maximum_scaled_error=max(c['maximum_scaled_error'] for c in r['cases']),
            zero_target_nonzero_error_rejected=True,full_dimension_source_and_observer_not_a_reduced_order_surrogate=True,
            constrained_solver_and_resource_convergence_still_pending=True,new_C1_source_eligible_for_statistics=False,
            no_actual_vehicle_fit_audio_C_or_naturalness_qualification=True)
        save(a.out/'report.json',r);print(r['result'],flush=True)
    except BaseException as error:r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
