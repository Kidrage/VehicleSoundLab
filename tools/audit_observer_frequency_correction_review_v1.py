"""Independent raw-array reconstruction of all36 publication rows and counts."""
import argparse,os,shutil,sys
from pathlib import Path
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('workspace','original','study','optimality','review'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    for n in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[n]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from circular_phase_lift_v1.audit_oracle import statistics
    repo=Path(__file__).resolve().parents[1];shutil.copy2(__file__,a.review/'executed_metrics_audit.py')
    pub=load(a.review/'report.json');assert pub['result']=='observer_frequency_correction_review_ready'
    for n,d in pub['inputs'].items():assert sha(n)==d
    for n,d in pub['sources'].items():assert sha(repo/n)==sha(a.review/'exact_sources'/n)==d
    old=load(a.original/'report.json');new=load(a.study/'report.json');gap=load(a.optimality/'report.json')
    original={c['label']:c for c in old['cases']};current={c['label']:c for c in new['cases']}
    rows,solves,summary=(load(a.review/(n+'.json')) for n in ('figure_inputs','solve_inputs','summary'))
    assert load(a.review/'gap_inputs.json')==gap['cases']
    tags=('interpolated','old_original4000','old_corrected','complete','weighted','block_refined')
    errors=('wave_NRMSE','wave_region_NRMSE','line_power_error_dB','broad_power_error_dB','line_coherence_error',
        'broad_coherence_error','line_CV_error','broad_CV_error','chunks_broad_power_error_dB','chunks_broad_coherence_error','chunks_broad_CV_error')
    def close(x,y,label):
        x,y=np.asarray(x),np.asarray(y)
        assert x.shape==y.shape and np.allclose(x,y,rtol=2e-10,atol=2e-11),label
    assert len(rows)==36 and len(solves)==6
    assert len({(r['label'],r['variant']) for r in rows})==36
    oracle=[]
    for saved in rows:
        label,tag=saved['label'],saved['variant']
        case=current[label] if tag=='block_refined' else original[label]
        folder=(a.study if tag=='block_refined' else a.original)/label
        desc=case if tag=='block_refined' else case['variants'][tag]
        path=folder/desc['file'];assert sha(path)==desc['sha256']
        expected_obj=case['solve']['objective'] if tag=='block_refined' else desc['weighted_objective']
        assert saved['root_hz']==case['root_hz'] and saved['weighted_objective']==expected_obj
        with np.load(folder/'source.npz') as z:source={k:z[k] for k in z.files}
        slices=np.array_split(np.arange(case['source_rows']),3)
        with np.load(path) as z:
            diff=z['audio']-source['audio']
            out=dict(wave_NRMSE=float(np.linalg.norm(diff)/np.linalg.norm(source['audio'])),
                wave_region_NRMSE=[float(np.linalg.norm(diff[s])/np.linalg.norm(source['audio'][s])) for s in (slice(0,2048),slice(2048,-2048),slice(-2048,None))])
            for prefix,pk,ck in (('line','power','cross'),('broad','broadband_power','broadband_cross')):
                origin=statistics(source[pk],source[ck]);rendered=statistics(z[pk],z[ck])
                out[prefix+'_power_error_dB']=(10*(np.log10(np.maximum(rendered['mean'],1e-24))-np.log10(np.maximum(origin['mean'],1e-24)))).reshape(-1,2)
                out[prefix+'_coherence_error']=abs(rendered['complex_coherence']-origin['complex_coherence'])
                out[prefix+'_CV_error']=abs(rendered['CV']-origin['CV']).reshape(-1,2)
            for k in ('power_error_dB','coherence_error','CV_error'):out['chunks_broad_'+k]=[]
            for s in slices:
                origin=statistics(source['broadband_power'][s],source['broadband_cross'][s]);rendered=statistics(z['broadband_power'][s],z['broadband_cross'][s])
                out['chunks_broad_power_error_dB'].append((10*(np.log10(np.maximum(rendered['mean'],1e-24))-np.log10(np.maximum(origin['mean'],1e-24)))).reshape(-1,2))
                out['chunks_broad_coherence_error'].append(abs(rendered['complex_coherence']-origin['complex_coherence']))
                out['chunks_broad_CV_error'].append(abs(rendered['CV']-origin['CV']).reshape(-1,2))
            for k,v in out.items():close(v,saved[k],(label,tag,k))
            close(z['broad_mean'].reshape(-1,2),saved['rendered_broad_mean'],'rendered mean')
            close(source['broad_mean'].reshape(-1,2),saved['source_broad_mean'],'source mean')
        oracle.append(dict(label=label,variant=tag,weighted_objective=expected_obj,**out))
    for c,s in zip(new['cases'],solves):assert s==dict(label=c['label'],**c['solve'])
    for tag in tags:
        rr=[r for r in oracle if r['variant']==tag];ss=summary['variants'][tag]
        for k in errors:close(np.mean(abs(np.array([r[k] for r in rr]))),ss[k+'_mean'],(tag,k))
        close(np.mean([r['weighted_objective'] for r in rr]),ss['weighted_objective_mean'],'objective mean')
        close(np.mean([r['broad_power_error_dB'] for r in rr],axis=(0,2)),ss['broad_signed_power_error_dB_by_band'],'signed bands')
    candidate={r['label']:r for r in oracle if r['variant']=='block_refined'}
    for tag in tags[:-1]:
        for k in errors:
            delta=np.array([abs(np.asarray(candidate[r['label']][k]))-abs(np.asarray(r[k])) for r in oracle if r['variant']==tag])
            saved=summary['paired']['block_refined_minus_'+tag][k]
            expected=dict(improved=int((delta < -1e-12).sum()),regressed=int((delta > 1e-12).sum()),equivalent=int((abs(delta)<=1e-12).sum()),count=int(delta.size))
            assert all(saved[k]==v for k,v in expected.items()),(tag,k)
            close(delta.mean(),saved['mean_change'],'paired mean')
    assert summary['original_solver_converged']==sum(c['solve']['converged'] for c in new['cases'])
    assert summary['stops']==[c['solve']['stop'] for c in new['cases']]
    assert summary['additional_gap_passed']==gap['gap_passed'] and summary['additional_gap_not_original_stop_gate']
    assert (summary['source_models'],summary['engines'],summary['ascents'])==(6,1,2)
    result=dict(result='independent_observer_frequency_correction_publication_passed',all36_rows_verified=True,
        all6_solver_records_verified=True,all12_gap_records_exact=True,all_aggregates_and_regression_counts_verified=True,
        **{n+'_sha256':sha(a.review/(n+'.json')) for n in ('figure_inputs','solve_inputs','gap_inputs','summary')},
        auditor_sha256=sha(__file__),oracle_sha256=sha(repo/'tools/circular_phase_lift_v1/audit_oracle.py'))
    save(a.review/'metrics_verification.json',result);print(result['result'],flush=True)


if __name__=='__main__':main()
