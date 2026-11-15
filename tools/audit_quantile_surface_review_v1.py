"""Independent new54 rows/moments and all162 aggregate/count verification.

Old108 rows are required literally identical to their already independently
audited immutable publication. This does not rerender those historical waves.
"""
import argparse,math,os,shutil,sys
from pathlib import Path
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('workspace','study','review'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    for n in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[n]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from circular_phase_lift_v1.audit_oracle import group_summary
    repo=Path(__file__).resolve().parents[1];pub=load(a.review/'report.json')
    for n,digest in pub['sources'].items():assert sha(repo/n)==sha(a.review/'exact_sources'/n)==digest
    for path,digest in pub['inputs'].items():assert sha(path)==digest
    for key in ('figure_inputs','moment_inputs','summary'):assert sha(a.review/(key+'.json'))==pub[key+'_sha256']
    shutil.copy2(__file__,a.review/'executed_metrics_audit.py')
    stream=a.workspace/'baselines/phase_stream_control_v1';entries={r['path']:r['sha256'] for r in load(stream/'manifest.json')['files']}
    assert sha(stream/'manifest.json')==load(repo/'research/phase_stream_control_v1_summary.json')['manifest_sha256']
    for name in ('figure_inputs.json','metrics_verification.json','summary.json'):assert sha(stream/'evidence/review1'/name)==entries['evidence/review1/'+name]
    receipt=load(stream/'evidence/review1/metrics_verification.json');assert receipt['all108_rows_and_aggregates_verified']
    rows=load(a.review/'figure_inputs.json');moments=load(a.review/'moment_inputs.json');summary=load(a.review/'summary.json')
    assert rows[:108]==load(stream/'evidence/review1/figure_inputs.json')
    producer=load(a.study/'report.json');assert sha(a.study/'report.json')==pub['producer_sha256']
    paths={(c['label'],s['seed'],'Q_'+n):(a.study/c['label']/v['file'],v['sha256']) for c in producer['cases'] for s in c['seeds'] for n,v in s['decoders'].items()}
    identities={(r['label'],r['seed'],r['variant']) for r in rows};assert len(identities)==len(rows)==162
    maximum=0.;fields=('low_power','rest_power','signed_low_rest_cross','total_power')
    def close(x,y):
        nonlocal maximum
        err=float(abs(np.asarray(x)-np.asarray(y)).max());maximum=max(maximum,err);assert np.allclose(x,y,rtol=1e-12,atol=2e-10),(err,x,y)
    for row in rows[108:]:
        identity=row['label'],row['seed'],row['variant'];path,digest=paths[identity];assert sha(path)==digest
        source_path=a.workspace/'baselines/conditional_phase_time_v1/evidence/real1'/row['label']/'source.npz'
        with np.load(source_path) as source,np.load(path) as z:
            for prefix in ('line','broad'):
                for suffix,f in (('power_error_dB','mean'),('CV_error','CV'),('coherence_error','complex_coherence')):
                    target=source[prefix+'_'+f];value=z[prefix+'_'+f]
                    truth=np.array([10*math.log10(x/y) for x,y in zip(value,target)]) if f=='mean' else abs(value-target)
                    close(truth,row[prefix+'_'+suffix]);value=z['chunks_'+prefix+'_'+f]
                    truth=np.array([[10*math.log10(x/y) for x,y in zip(v,target)] for v in value]) if f=='mean' else abs(value-target)
                    close(truth,row['chunks_'+prefix+'_'+suffix])
                signed=group_summary(z[prefix+'_Gram'])
                for f in fields:close(signed[f]/source[prefix+'_mean'].reshape(4,2),row[prefix+'_'+f+'_over_reference'])
            assert np.array_equal(z['maximum_phase_step'],row['maximum_relative_phase_step'])
            close(z['instant_mean'],row['instant_mean']);close(z['instant_CV'],row['instant_CV'])
            close(z['instant_complex_coherence'],np.array(row['instant_complex_coherence_pairs'])@np.array([1.,1j]))
    moment_ids=set()
    for row in moments:
        identity=row['label'],row['variant'];assert identity not in moment_ids;moment_ids.add(identity)
        with np.load(a.study/row['label']/'midpoint_moments.npz') as z:
            name=row['variant'][2:];truth=abs(z[name+'_old']-z[name+'_new'])
            assert row['count']==truth.size;close(truth,row['loss'])
    assert len(moment_ids)==18 and sum(r['count'] for r in moments)==160704

    def flat(parts):return [float(x) for part in parts for x in np.asarray(part).ravel()]
    def quantile(x):
        x=sorted(x);out=[]
        for p in (0,.25,.5,.75,1):
            index=p*(len(x)-1);lo=int(index);hi=min(lo+1,len(x)-1);out.append(x[lo]+(index-lo)*(x[hi]-x[lo]))
        return out
    for name,saved in summary['variants'].items():
        chosen=[r for r in rows if r['variant']==name];assert len(chosen)==18
        for key,value in saved.items():
            if key=='maximum_relative_phase_step_quantiles':close(value,quantile(flat([r['maximum_relative_phase_step'] for r in chosen])));continue
            x=flat([r[key] for r in chosen]);assert value['count']==len(x)
            close(value['mean'],math.fsum(x)/len(x));close(value['mean_absolute'],math.fsum(abs(t) for t in x)/len(x));close(value['quantiles'],quantile(x))
    expected_pairs={('independent_marginal','relative')}|{(n,'independent_marginal') for n in ('parent','density','variation')}
    expected_pairs|={('Q_'+n,n) for n in ('parent','density','variation')}|{('Q_'+n,b) for n in ('parent','density','variation') for b in ('independent_marginal','relative')}
    assert set(summary['paired'])=={x+'_minus_'+y for x,y in expected_pairs}
    for key,paired in summary['paired'].items():
        new,old=key.split('_minus_');target={(r['label'],r['seed']):r for r in rows if r['variant']==old};chosen=[r for r in rows if r['variant']==new]
        for prefix in ('line','broad','chunks_line','chunks_broad'):
            for suffix,tol in summary['comparison_tolerances'].items():
                name=prefix+'_'+suffix;x=flat([abs(np.asarray(r[name])) for r in chosen]);y=flat([abs(np.asarray(target[r['label'],r['seed']][name])) for r in chosen]);d=[a-b for a,b in zip(x,y)];v=paired[name]
                assert (v['improved'],v['equal_within_numeric_gate'],v['regressed'])==(sum(t < -tol for t in d),sum(abs(t)<=tol for t in d),sum(t>tol for t in d))
                assert (v['literal_improved'],v['literal_equal'],v['literal_regressed'])==(sum(a<b for a,b in zip(x,y)),sum(a==b for a,b in zip(x,y)),sum(a>b for a,b in zip(x,y)))
                close(v['mean_signed_error_change'],math.fsum(d)/len(d))
        for prefix in ('line','broad'):
            for f in fields:
                name=prefix+'_'+f+'_over_reference';x=flat([r[name] for r in chosen]);y=flat([target[r['label'],r['seed']][name] for r in chosen]);d=[a-b for a,b in zip(x,y)];v=paired[prefix+'_signed_change_'+f]
                close(v['mean'],math.fsum(d)/len(d));close(v['quantiles'],quantile(d))
                assert (v['literal_positive'],v['literal_negative'],v['literal_zero'])==(sum(t>0 for t in d),sum(t<0 for t in d),sum(t==0 for t in d))
    for name,v in summary['midpoint_circular_moment_loss'].items():
        x=flat([r['loss'] for r in moments if r['variant']==name]);assert v['count']==len(x) and v['changed_beyond_2e_12']==sum(t>2e-12 for t in x)
        close(v['mean'],math.fsum(x)/len(x));close(v['quantiles'],quantile(x))
    save(a.review/'metrics_verification.json',dict(result='independent_quantile_surface_publication_passed',all162_rows_and_aggregates_verified=True,
        historical108_exact_and_previously_audited=True,new54_signed_Gram_budgets_verified=True,all160704_moment_losses_verified=True,
        literal_and_numeric_counts_verified=True,maximum_error=maximum,auditor_sha256=sha(__file__),
        **{k+'_sha256':sha(a.review/(k+'.json')) for k in ('figure_inputs','moment_inputs','summary')}))
    print('independent_quantile_surface_publication_passed',flush=True)


if __name__=='__main__':main()
