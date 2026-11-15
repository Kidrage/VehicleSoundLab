"""Audit every terminal full288 publication row, guard, frequency label and count."""
import argparse, math, shutil
from pathlib import Path
from research_archive_v1 import load, save, sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('study','audit','review'):
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    shutil.copy2(__file__,a.review/'executed_metrics_audit.py')
    r=dict(result='running')
    try:
        pub=load(a.review/'report.json')
        data=load(a.review/'figure_inputs.json')
        source=load(a.study/'report.json')
        audit=load(a.audit/'report.json')
        assert source['result']=='observer_stable_full_known_measured'
        assert audit['result']=='independent_observer_stable_full_passed'
        assert audit['producer_sha256']==sha(a.study/'report.json')
        units_path=a.study.parent/'frequency_units_audit1/report.json'
        units=load(units_path)
        assert pub['inputs'][str(units_path)]==sha(units_path)
        assert units['result']=='independent_observer_stable_frequency_units_passed'
        assert units['bins_per_band']==[188,187,125,125,250,1174]
        assert units['final_band_Hz']==[14000.,32768.]
        assert units['final_band_includes_Nyquist']
        assert pub['inputs'][str(a.study/'report.json')]==sha(a.study/'report.json')
        assert pub['inputs'][str(a.audit/'report.json')]==sha(a.audit/'report.json')
        assert pub['publisher_sha256']==sha(a.review/'executed_publication.py')
        assert pub['figure_inputs_sha256']==sha(a.review/'figure_inputs.json')
        assert not pub['source_or_runtime_or_hearing_qualified']
        for name,digest in pub['inputs'].items(): assert sha(name)==digest
        for name,digest in pub['images'].items(): assert sha(a.review/name)==digest
        candidates=[Path(n) for n in source['inputs'] if n.endswith('report.json') and 'observer_representer_v1' in n]
        assert len(candidates)==1
        old=load(candidates[0])
        assert sha(candidates[0])==source['inputs'][str(candidates[0])]
        assert old['metrics']==source['old_results']
        assert data['gates']==dict(stable_normal=1e-11,backward=1e-11,original_gradient=2e-7,gap_relative=1e-6,gap_absolute=1e-10)
        checkpoints=data['checkpoints']
        assert len(checkpoints)==len(source['solver']['checkpoints'])
        for row,c in zip(checkpoints,source['solver']['checkpoints']):
            for key,field in (('directions','directions'),('stable_normal_relative','stable_normal_relative'),
                    ('direct_normal_relative','direct_normal_relative'),('backward_discrepancy','relative_backward_discrepancy'),('accepted','accepted')):
                assert row[key]==c[field]
            assert row['original_gradient']==c['original_checks']['relative_stationarity']
            assert row['original_residual_gap_passed']==c['original_checks']['residual_gap_passed']
            assert row['original_representer_gap_passed']==c['original_checks']['representer_gap_passed']
        assert checkpoints[-1]['directions']==source['solver']['directions']
        assert len(data['gaps'])==4
        for row in data['gaps']:
            origin=old if row['version']=='previous' else source
            c=origin[row['kind']+'_certificate']
            assert row['gap']==c['gap_upper_bound'] and row['objective']==c['primal']
            gate=c['primal']/1e6+1e-10
            assert math.isclose(row['gate'],gate,rel_tol=2e-15,abs_tol=0)
            assert math.isclose(row['ratio'],row['gap']/gate,rel_tol=2e-15,abs_tol=0)
            assert row['passed']==c['additional_gap_gate_passed']==(row['gap']<=gate)
        expected_bands=['0-3','3-6','6-8','8-10','10-14','14-32.768']
        # 1024 samples/cycle * root64; rFFT4096 has 2049 bins including Nyquist.
        assert (2049-1)*(64/4)/1000==32.768
        rows=data['fidelity_rows']
        assert len(rows)==17
        counts={}
        for field in ('target_supported_band_complex_NRMSE','whole_supported_band_complex_NRMSE'):
            subset=[row for row in rows if row['metric']==field]
            assert len(subset)==6 and [row['band_kHz'] for row in subset]==expected_bands
            for j,row in enumerate(subset):
                assert row['previous']==old['metrics'][field][j]
                assert row['stable']==audit['metrics'][field][j]
                assert row['regressed']==(row['stable']>row['previous'])
            counts[field]=sum(row['regressed'] for row in subset)
        for field in ('whole_wave_NRMSE','target_wave_NRMSE'):
            subset=[row for row in rows if row['metric']==field]
            assert len(subset)==1
            row=subset[0]
            assert row['previous']==old['metrics'][field] and row['stable']==audit['metrics'][field]
            assert row['regressed']==(row['stable']>row['previous'])
            counts[field]=int(row['regressed'])
        subset=[row for row in rows if row['metric']=='whole_wave_regions_NRMSE']
        assert [row['region'] for row in subset]==['before','target','after']
        for j,row in enumerate(subset):
            assert row['previous']==old['metrics']['whole_wave_regions_NRMSE'][j]
            assert row['stable']==audit['metrics']['whole_wave_regions_NRMSE'][j]
            assert row['regressed']==(row['stable']>row['previous'])
        counts['whole_wave_regions_NRMSE']=sum(row['regressed'] for row in subset)
        summary=data['summary']
        assert summary==pub['summary']
        assert summary['regressions']==counts
        for key in ('solver_qualified','fidelity_qualified'): assert summary[key]==source[key]==audit[key]
        assert summary['directions']==source['solver']['directions']
        assert summary['stopping_code']==source['solver']['stop']
        assert summary['accepted']==source['solver']['accepted']
        assert summary['original_gradient']==audit['original_space_gradient']
        assert summary['full_Gram_verified']==audit['full_basis_Grams_verified']
        assert summary['projection_columns_independently_checked']==len(audit['independently_checked_projection_columns'])
        assert summary['final_stable_estimator_pass']==audit['independent_stable_pass']
        assert summary['final_backward_discrepancy']==audit['independent_backward_discrepancy']
        for key in ('whole_wave_NRMSE','target_wave_NRMSE'):
            assert summary[key+'_before']==old['metrics'][key]
            assert summary[key+'_after']==audit['metrics'][key]
        assert not summary['source_or_native48k_or_C_or_hearing_qualified']
        r.update(result='independent_observer_stable_full_publication_passed',all17_fidelity_rows_all_checkpoints_and_four_gaps_verified=True,
            final_band_includes_analysis_Nyquist_32768Hz=True,summary=summary,producer_sha256=sha(a.review/'report.json'),auditor_sha256=sha(__file__))
        save(a.review/'metrics_verification.json',r)
        print(r['result'],summary,flush=True)
    except BaseException as error:
        r.update(result='failed',error=repr(error))
        save(a.review/'metrics_verification.json',r)
        raise


if __name__=='__main__':
    main()
