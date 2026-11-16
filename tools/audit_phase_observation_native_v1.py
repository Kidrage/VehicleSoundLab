"""Audit every native query and every observed coefficient of the known bridge."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load,save,sha


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','study','out'):parser.add_argument('--'+name,type=Path,required=True)
    a=parser.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import math
    import numpy as np
    from phase_observation_native_v1.audit import continuous,phase,native_bridge,stft_coefficients,hann_coefficients,envelope64
    a.out.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1]
    r=dict(result='running',cases=[],sources={},maximum_errors={})
    errors=r['maximum_errors']
    def check(name,actual,expected,gate,scale=1.):
        actual,expected=np.asarray(actual),np.asarray(expected);assert actual.shape==expected.shape,name
        value=float(abs(actual-expected).max())/scale;errors[name]=value
        if not np.isfinite(value) or value>gate:raise ValueError((name,value,gate))
    def moments(z,scale):
        x=np.column_stack((z[:,0].real,z[:,0].imag,z[:,1].real,z[:,1].imag))
        mean=np.array([math.fsum(col)/len(x) for col in x.T]);x-=mean
        c0=np.einsum('ni,nj->ij',x,x,optimize=False)/len(x)
        result=dict(rows=len(z),variance_trace_FS2=float(np.trace(c0)),variation_RMS_FS=float(np.sqrt(np.trace(c0))),lags=[])
        for lag in (1,2,4,8):
            c=np.array([[math.fsum(x[t+lag,i]*x[t,j] for t in range(len(x)-lag))/(len(x)-lag) for j in range(4)] for i in range(4)])
            result['lags'].append(dict(lag_rows=lag,lag_covariance_FS2=c.tolist(),
                skew_norm_over_source_scale_squared=float(np.linalg.norm((c-c.T)/2)/scale**2)))
        return result
    def compare_moments(prefix,saved,expected):
        for key in ('variance_trace_FS2','variation_RMS_FS'):check(prefix+key,saved[key],expected[key],2e-11,.07 if key=='variation_RMS_FS' else .07**2)
        assert saved['rows']==expected['rows']
        for left,right in zip(saved['lags'],expected['lags']):
            assert left['lag_rows']==right['lag_rows']
            check(prefix+'lag'+str(left['lag_rows']),left['lag_covariance_FS2'],right['lag_covariance_FS2'],2e-11,.07**2)
            check(prefix+'skew'+str(left['lag_rows']),left['skew_norm_over_source_scale_squared'],right['skew_norm_over_source_scale_squared'],2e-11)
    try:
        for name in ('tools/audit_phase_observation_native_v1.py','tools/phase_observation_native_v1/audit.py','tools/research_archive_v1.py'):
            dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest);r['sources'][name]=sha(dest)
        source=load(a.study/'report.json');assert source['result']=='native_phase_observation_known_controls_measured'
        assert source['truth_contract']=='per-variant instantaneous carrier64 envelope in observer coordinates'
        for name,digest in source['sources'].items():assert sha(repo/name)==sha(a.study/'exact_sources'/name)==digest
        for name,digest in source['inputs'].items():assert sha(name)==digest
        plan=load(a.study/'exact_sources/research/phase_observation_native_v1_plan.json');g=plan['geometry'];rules=plan['checks']
        for case in source['cases']:
            label=case['label'];path=a.study/(label+'.npz');assert sha(path)==case['sha256']
            with np.load(path) as f:data={k:f[k] for k in f.files}
            spec={k:data[k] for k in ('orders','amplitudes','phases')};spec['kind']=case['source_kind']
            check(label+'_native_phase_all',data['native_coordinate'],phase(data['native_times'],g,case['source_clock_depth']),2e-11,max(1.,abs(data['native_coordinate']).max()))
            check(label+'_native_source_all',data['native_audio'],continuous(spec,data['native_coordinate']),rules['saved_integer_fixture_FS'])
            q=phase(data['positions'],g,case['source_clock_depth'])
            check(label+'_source_query_all',data['source_query_coordinate'],q,2e-11,max(1.,abs(q).max()))
            clock=phase(data['positions'],g,case['observer_clock_depth'])
            assert abs(clock-np.arange(len(q))).max()<rules['analytic_clock_virtual_samples']
            check(label+'_query_wave_all',data['query_exact_audio'],continuous(spec,q),rules['saved_integer_fixture_FS'])
            check(label+'_canonical_wave_all',data['canonical_audio'],continuous(spec,np.arange(len(q))),rules['saved_integer_fixture_FS'])
            bridge=native_bridge(data['native_audio'],data['positions'],case['inherited_warp']['source_cutoff_hz'])
            peak=max(float(abs(data['native_audio']).max()),1e-30)
            check(label+'_native_operator_all_queries',data['native_normalized_audio'],bridge,rules['independent_bridge_relative_peak'],peak)
            measured=float(abs(data['native_normalized_audio']-data['query_exact_audio']).max())
            assert measured==case['native_bridge_error_FS'] and measured<rules['native_bridge_approximation_FS']
            for cycles in (2,4,8):
                starts=np.arange(0,len(q)-1024*cycles+1,256)
                check(f'{label}_{cycles}_frame_starts',data[f'starts_cycles{cycles}'],starts,0.)
                centers=starts+512*cycles
                for variant in ('native','query','canonical'):
                    key={'native':'native_normalized_audio','query':'query_exact_audio','canonical':'canonical_audio'}[variant]
                    z=data[f'{variant}_cycles{cycles}'];independent=stft_coefficients(data[key],cycles)
                    check(f'{label}_{variant}_{cycles}_all_coefficients',z,independent,rules['independent_projection_FS'])
                    if variant=='canonical':
                        check(f'{label}_{cycles}_analytic_Hann',z,hann_coefficients(spec,len(q),cycles),rules['independent_projection_FS'])
                    row=next(v for v in case['observations'] if v['variant']==variant and v['cycles']==cycles)
                    assert row['rows']==len(z)
                    compare_moments(f'{label}_{variant}_{cycles}_observed_',row['observed'],moments(z[:,63],.07))
                    compare_moments(f'{label}_{variant}_{cycles}_prefix_',row['observed_prefix40'],moments(z[:40,63],.07))
                    compare_moments(f'{label}_{variant}_{cycles}_hop1024_',row['hop1024_subset'],moments(z[::4,63],.07))
                    truth=data[f'truth_{variant}_cycles{cycles}']
                    # Canonical audio has a canonical-time truth, including in
                    # the deliberately wrong-clock case. Query/native use the
                    # actual physical source coordinate at observer centres.
                    source_centers=centers if variant=='canonical' else q[centers]
                    check(f'{label}_{variant}_{cycles}_truth_definition',truth,
                        envelope64(spec,source_centers,centers),rules['independent_projection_FS'])
                    compare_moments(f'{label}_{variant}_{cycles}_truth_',row['truth'],moments(truth,.07))
                    compare_moments(f'{label}_{variant}_{cycles}_truthprefix_',row['truth_prefix40'],moments(truth[:40],.07))
            r['cases'].append(dict(label=label,all_native_queries_and_coefficients_verified=True))
            save(a.out/'report.json',r);print('NATIVE_OBSERVATION_AUDIT',label,flush=True)
        r.update(result='independent_native_phase_observation_verified',verification_passed=True,
            producer_sha256=sha(a.study/'report.json'),maximum_comparison_error=max(errors.values()),
            all9_cases_complete=len(r['cases'])==9,new_C1_source_eligible_for_statistics=False,
            no_vehicle_clock_estimator_audio_C_or_naturalness_qualification=True)
        save(a.out/'report.json',r);print(r['result'],len(errors),flush=True)
    except BaseException as error:r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
