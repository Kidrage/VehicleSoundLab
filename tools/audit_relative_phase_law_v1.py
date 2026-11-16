"""Independent all-entry and scalar-anchor verification of saved texture-law diagnostics."""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load,save,sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('workspace','study','out'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from relative_phase_law_v1.measure import assess
    from relative_phase_law_v1.audit import verify
    a.out.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1]
    result=dict(result='running',sources={},cases=[],maximum_errors={})
    errors=result['maximum_errors']
    try:
        for name in ('tools/audit_relative_phase_law_v1.py','tools/relative_phase_law_v1/audit.py','tools/research_archive_v1.py'):
            dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(repo/name,dest);result['sources'][name]=sha(dest)
        source=load(a.study/'report.json')
        assert source['result'] in ('relative_phase_law_known_controls_passed','six_saved_relative_phase_laws_measured_without_training')
        for name,digest in source['sources'].items():assert sha(repo/name)==sha(a.study/'exact_sources'/name)==digest
        for name,digest in source['inputs'].items():assert sha(name)==digest
        for case in source['cases']:
            path=a.study/case['label']/'factors.npz';assert sha(path)==case['factors_sha256']
            with np.load(path) as f:data={k:f[k] for k in f.files}
            model={k:data[k] for k in ('basis','rho','residual_std','residual_rho')}
            arrays,rows,groups,meta=assess(model,{k:data[k] for k in ('scores','pc','residual')},data['lags'])
            assert rows==case['rows'] and groups==case['groups'] and meta==case['metadata']
            for name,digest in case['all_matrix_sha256'].items():
                assert hashlib.sha256(np.ascontiguousarray(arrays[name]).tobytes()).hexdigest()==digest,name
            def check(name,actual,expected,scale):
                actual,expected=np.asarray(actual),np.asarray(expected)
                assert actual.shape==expected.shape,name
                value=float(np.max(abs(actual-expected)))/max(float(scale),1e-300)
                errors[case['label']+'_'+name]=value
                if not np.isfinite(value) or value>2e-11:raise ValueError((name,value))
            evidence=verify(arrays,case['rows'],case['groups'],case['metadata'],check)
            if source['stage']=='known':
                rotation,scalar=data['known_rotation_A'],data['known_scalar_A']
                assert np.linalg.norm(rotation-rotation.T)>.5 and np.linalg.norm(rotation@rotation-scalar@scalar)>.2
                check('known_diagonal_lag1_equal',np.diag(rotation),np.diag(scalar),1.)
                for key in ('known_zero_model','known_zero_observed'):assert np.count_nonzero(data[key])==0
                for key in ('known_silent_model','known_silent_observed'):assert np.count_nonzero(data[key][-1])==0
                original=data['known_source_rows'];reversed_rows=original[::-1]
                c=lambda v,lag:np.einsum('ni,nj->ij',(v-v.mean(0))[lag:],(v-v.mean(0))[:len(v)-lag],optimize=False)/(len(v)-lag)
                check('known_reverse',c(reversed_rows,1),c(original,1).T,1.)
                check('known_permuted_static',c(original[data['known_permutation']],0),c(original,0),1.)
                assert np.linalg.norm(c(original[data['known_permutation']],1)-c(original,1))>.3
            result['cases'].append(dict(label=case['label'],**evidence))
            save(a.out/'report.json',result)
            print('LAW_AUDIT_PASS',case['label'],flush=True)
        result.update(result='independent_relative_phase_law_verified',verification_passed=True,
            producer_sha256=sha(a.study/'report.json'),maximum_comparison_error=max(errors.values()),
            no_audible_or_physical_cause_claim=True,new_C1_source_eligible_for_statistics=False,
            no_source_fit_training_C_room_or_hearing_change=True)
        save(a.out/'report.json',result)
        print(result['result'],max(errors.values()),flush=True)
    except BaseException as error:
        result.update(result='failed',error=repr(error));save(a.out/'report.json',result);raise


if __name__=='__main__':main()
