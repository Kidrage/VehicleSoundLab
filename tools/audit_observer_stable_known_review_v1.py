"""Independently bind every published control number, count and figure input."""
import argparse, math, shutil, sys
from pathlib import Path
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'study', 'previous', 'review'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    shutil.copy2(__file__,a.review/'executed_metrics_audit.py')
    r = dict(result='running')
    try:
        pub=load(a.review/'report.json')
        data=load(a.review/'figure_inputs.json')
        assert sha(a.review/'figure_inputs.json')==pub['figure_inputs_sha256']
        assert sha(a.review/'executed_publication.py')==pub['publisher_sha256']
        for name,digest in pub['inputs'].items(): assert sha(name)==digest
        for name,digest in pub['images'].items(): assert sha(a.review/name)==digest
        assert not pub['source_or_full_solver_or_runtime_or_hearing_qualified']
        after=load(a.study/'known_audit1/report.json')
        before=load(a.previous/'reorth_known_audit1/report.json')
        captures=load(a.study/'known1/report.json')
        old_captures=load(a.previous/'reorth_known1/report.json')
        mapped=load(a.study/'known_mapped_audit1/report.json')
        storage=load(a.study/'storage_audit1/report.json')
        estimator=load(a.study/'controls1/report.json')
        decimal=load(a.study/'controls_audit1/report.json')
        assert data['gates']==dict(normal=1e-11,backward=1e-11,gradient=2e-7,gap_relative=1e-6,gap_absolute=1e-10)
        assert len(data['rows'])==len(after['cases'])==len(before['cases'])==12
        assert len({(v['kind'],v['label']) for v in data['rows']})==12
        keys=dict(direct_normal_relative='independent_direct_transformed_normal_relative',
            stable_normal_relative='stable_normal_relative',backward_discrepancy='independent_backward_discrepancy',
            gradient='gradient',dense_relative_error='dense_relative_error')
        errors=[]
        for row,now,old,new_capture,old_capture in zip(data['rows'],after['cases'],before['cases'],captures['cases'],old_captures['cases']):
            assert (row['kind'],row['label'])==(now['kind'],now['label'])==(old['kind'],old['label'])
            assert row['stop']==now['stopping_code']==2 and row['old_stop']==old['stopping_code']
            assert row['qualified']==now['qualified'] and row['old_qualified']==old['qualified']
            for key,src in keys.items(): assert row[key]==now[src],(row['label'],key)
            assert row['directions']==new_capture['solver']['directions']
            assert math.isclose(row['gap_gate'],now['original_objective']/1e6+1e-10,rel_tol=2e-15,abs_tol=0)
            for name in ('residual','representer'):
                assert row[name+'_gap']==now['certificates'][name]['gap']
                assert row[name+'_gap']<=row['gap_gate'] and now['certificates'][name]['passed']
            assert row['gradient']<2e-7 and row['backward_discrepancy']<=1e-11
            assert row['stable_normal_relative']<=1e-11
            p0=a.previous/'reorth_known1'/old_capture['file']
            p1=a.study/'known1'/new_capture['file']
            with np.load(p0) as x,np.load(p1) as y:
                exact=bool(np.array_equal(x['fitted'],y['fitted']))
                difference=float(np.max(abs(x['fitted']-y['fitted'])))
            assert row['fitted_bitwise_equal_old']==exact and exact
            assert row['maximum_fitted_difference']==difference==0
            errors.append(row['dense_relative_error'])
        e={c['label']:c['info'] for c in estimator['cases']}
        dec={c['label']:c for c in decimal['cases']}
        outside=data['controls']['outside_gradient']
        assert outside==dict(projected=e['outside_gradient']['projected_only_normal_norm'],
            modeled_full=e['outside_gradient']['stable_normal_norm'],direct_full=e['outside_gradient']['direct_normal_norm'])
        assert outside['projected']==0 and outside['modeled_full']==outside['direct_full']==3
        ill=data['controls']['ill_conditioned']
        assert ill['modeled_full_binary64']==e['ill_conditioned']['stable_normal_norm']
        for key,src in (('high_precision_projected_model','projected_high_precision_normal_norm'),
                ('high_precision_original','original_high_precision_normal_norm'),
                ('gradient_defect_bound','projection_gradient_defect_bound'),('actual_gradient_defect','actual_gradient_defect')):
            assert ill[key]==float(dec['ill_conditioned'][src])
        assert ill['high_precision_original']>3 and ill['high_precision_projected_model']<1e-15
        assert ill['actual_gradient_defect']<=ill['gradient_defect_bound']
        defect=data['controls']['projection_defect']
        assert defect['backward_discrepancy']==e['projection_defect']['relative_backward_discrepancy']
        assert defect['gate']==1e-11 and defect['backward_discrepancy']>defect['gate']
        for case in decimal['cases']:
            assert case['independent_precision_digits']==[80,110]
            assert case['maximum_precision_difference']<1e-50
        summary=dict(unique_known_cases=12,old_qualified=4,stable_qualified=12,mapped_qualified=12,
            estimator_controls=7,bitwise_equal_old_fitted=12,storage_arrays_per_case=[18]*12,
            trimmed_basis_files=24,dense_error_range=[min(errors),max(errors)],
            max_independent_backward_discrepancy=max(c['independent_backward_discrepancy'] for c in after['cases']),
            maximum_fitted_difference=0.0)
        assert data['summary']==pub['summary']==summary
        assert sum(c['qualified'] for c in before['cases'])==4
        assert all(c['qualified'] for c in mapped['cases']) and len(mapped['cases'])==12
        assert len(storage['cases'])==12 and all(len(c['arrays_sha256'])==18 for c in storage['cases'])
        assert sum(len(c['raw_basis_files_sha256']) for c in storage['cases'])==24
        r.update(result='independent_observer_stable_known_publication_passed',summary=summary,
            all_published_rows_controls_and_counts_verified=True,producer_sha256=sha(a.review/'report.json'),auditor_sha256=sha(__file__))
        save(a.review/'metrics_verification.json',r)
        print(r['result'],summary,flush=True)
    except BaseException as error:
        r.update(result='failed',error=repr(error))
        save(a.review/'metrics_verification.json',r)
        raise


if __name__=='__main__':
    main()
