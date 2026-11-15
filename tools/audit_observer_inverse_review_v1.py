"""Independent raw-wave/raw-power audit of every published row and aggregate."""
import argparse, math, os, shutil, sys
from pathlib import Path
from research_archive_v1 import load, save, sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','root','review'):
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
        os.environ[name]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    shutil.copy2(__file__,a.review/'executed_metrics_audit.py')
    publication=load(a.review/'report.json')
    assert publication['result']=='observer_inverse_review_ready'
    for path,digest in publication['inputs'].items():assert sha(path)==digest
    for name,digest in publication['images'].items():assert sha(a.review/name)==digest
    rows=load(a.review/'figure_inputs.json');solves=load(a.review/'solve_inputs.json');summary=load(a.review/'summary.json')
    assert len(rows)==24 and len(solves)==18
    max_error=0.
    def equal(left,right):
        nonlocal max_error
        error=float(np.max(abs(np.asarray(left)-np.asarray(right))))
        assert error<2e-9,error
        max_error=max(max_error,error)
    def stats(z,prefix):
        p=z['power' if prefix=='line' else 'broadband_power']
        c=z['cross' if prefix=='line' else 'broadband_cross']
        mean=np.mean(p,axis=0)
        cv=np.divide(np.std(p,axis=0),mean,out=np.zeros_like(mean),where=mean>1e-24)
        den=np.sqrt(mean[::2]*mean[1::2])
        coherence=np.divide(c.mean(axis=0),den,out=np.zeros(len(den),complex),where=den>1e-24)
        return mean,cv,coherence
    mapping={'interpolated':('real1','interpolated_observations'),
        'original4000':('real1','inverse'),'preconditioned4000':('real2','inverse'),
        'corrected':('real3','inverse')}
    reports={n:load(a.root/n/'report.json') for n in ('real1','real2','real3')}
    verified=[]
    for row in rows:
        attempt,key=mapping[row['variant']]
        case=next(c for c in reports[attempt]['cases'] if c['label']==row['label'])
        desc=case['variants'][key]
        path=a.root/attempt/row['label']/desc['file'];assert sha(path)==desc['sha256']
        with np.load(a.root/'real1'/row['label']/'source.npz') as source,np.load(path) as capture:
            audio,reference=capture['audio'],source['audio']
            nrmse=float(np.linalg.norm(audio-reference)/max(np.linalg.norm(reference),1e-24))
            regions=[float(np.linalg.norm((audio-reference)[sl])/max(np.linalg.norm(reference[sl]),1e-24))
                     for sl in (slice(0,2048),slice(2048,-2048),slice(-2048,None))]
            equal(nrmse,row['wave_NRMSE']);equal(regions,row['wave_region_NRMSE'])
            assert row['root_hz']==case['root_hz']
            for prefix in ('line','broad'):
                mean,cv,coherence=stats(capture,prefix)
                refmean,refcv,refcoherence=stats(source,prefix)
                power=10*np.log10(np.maximum(mean,1e-24)/np.maximum(refmean,1e-24))
                equal(power.reshape(-1,2),row[prefix+'_power_error_dB'])
                equal(abs(cv-refcv).reshape(-1,2),row[prefix+'_CV_error'])
                equal(abs(coherence-refcoherence),row[prefix+'_coherence_error'])
        verified.append((row['label'],row['variant']))
    assert len(set(verified))==24
    for row in solves:
        case=next(c for c in reports[row['attempt']]['cases'] if c['label']==row['label'])
        for key,value in case['solve'].items():assert row[key]==value
        assert row['correction_stages']==case.get('correction_stages',[])
        assert row['cumulative_iterations']==case.get('cumulative_iterations',case['solve']['iterations'])
    mean=lambda values:math.fsum(float(x) for x in values)/len(values)
    fields=('line_power_error_dB','broad_power_error_dB','line_coherence_error',
        'broad_coherence_error','line_CV_error','broad_CV_error')
    for variant in mapping:
        rr=[r for r in rows if r['variant']==variant]
        aggregate=summary['variants'][variant]
        equal(mean([r['wave_NRMSE'] for r in rr]),aggregate['wave_NRMSE_mean'])
        equal([mean([r['wave_region_NRMSE'][j] for r in rr]) for j in range(3)],aggregate['wave_region_NRMSE_mean'])
        for key in fields:
            equal(mean([v for r in rr for v in abs(np.asarray(r[key])).ravel()]),aggregate[key+'_mean'])
        if variant=='interpolated':continue
        base={r['label']:r for r in rows if r['variant']=='interpolated'}
        for key,counts in summary['paired'][variant+'_minus_interpolated'].items():
            delta=[float(v) for r in rr for v in
                (abs(np.asarray(r[key]))-abs(np.asarray(base[r['label']][key]))).ravel()]
            equal(mean(delta),counts['mean_change'])
            assert counts['count']==len(delta)
            assert counts['improved']==sum(v < -1e-12 for v in delta)
            assert counts['regressed']==sum(v > 1e-12 for v in delta)
            assert counts['equivalent']==sum(abs(v)<=1e-12 for v in delta)
    for attempt in reports:
        assert summary['solver_converged'][attempt]==sum(c['solve']['converged'] for c in reports[attempt]['cases'])
    assert summary['source_models']==6 and summary['engines']==1
    for name in ('figure_inputs','solve_inputs','summary'):
        assert publication[name+'_sha256']==sha(a.review/(name+'.json'))
    result=dict(result='independent_observer_inverse_publication_passed',all24_rows_verified=True,
        all18_solver_records_verified=True,all_aggregates_and_improvement_regression_counts_verified=True,
        max_absolute_metric_difference=max_error,auditor_sha256=sha(__file__),
        figure_inputs_sha256=sha(a.review/'figure_inputs.json'),solve_inputs_sha256=sha(a.review/'solve_inputs.json'),
        summary_sha256=sha(a.review/'summary.json'))
    save(a.review/'metrics_verification.json',result);print(result['result'],flush=True)


if __name__=='__main__':
    main()
