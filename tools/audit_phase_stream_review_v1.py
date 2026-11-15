"""Independently verify all108 published rows, signed budgets and aggregations."""
import argparse
import math
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','study','review'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from circular_phase_lift_v1.audit_oracle import group_summary
    repo=Path(__file__).resolve().parents[1]
    publication=load(a.review/'report.json');rows=load(a.review/'figure_inputs.json');summary=load(a.review/'summary.json')
    assert sha(a.review/'figure_inputs.json')==publication['figure_inputs_sha256'] and sha(a.review/'summary.json')==publication['summary_sha256']
    for path,digest in publication['inputs'].items():assert sha(path)==digest
    for name,digest in publication['sources'].items():assert sha(repo/name)==sha(a.review/'exact_sources'/name)==digest
    shutil.copy2(__file__,a.review/'executed_metrics_audit.py')
    parent=a.workspace/'baselines/conditional_phase_time_v1/evidence/real1';carrier=a.workspace/'baselines/carrier_transfer_v1/evidence/real1'
    producer=load(a.study/'report.json');new={(r['label'],s['seed']):a.study/r['label']/s['file'] for r in producer['cases'] for s in r['seeds']}
    old=load(carrier/'report.json');paths={(r['label'],s['seed'],v):carrier/r['label']/desc['file'] for r in old['cases'] for s in r['seeds'] for v,desc in s['variants'].items()}
    maximum=0.;verified=set()
    fields=('low_power','rest_power','signed_low_rest_cross','total_power')
    for row in rows:
        label,seed,name=row['label'],row['seed'],row['variant'];identity=(label,seed,name)
        assert identity not in verified;verified.add(identity)
        path=new[label,seed] if name=='independent_marginal' else paths[identity]
        with np.load(parent/label/'source.npz') as source,np.load(parent/label/f'probe_{seed}.npz') as oldz,np.load(path) as z:
            get=lambda key:z[key] if name=='independent_marginal' else oldz[name+'_'+key]
            truths={}
            for prefix in ('line','broad'):
                truths[prefix+'_power_error_dB']=np.array([10*math.log10(x/y) for x,y in zip(get(prefix+'_mean'),source[prefix+'_mean'])])
                truths[prefix+'_CV_error']=abs(get(prefix+'_CV')-source[prefix+'_CV'])
                truths[prefix+'_coherence_error']=abs(get(prefix+'_complex_coherence')-source[prefix+'_complex_coherence'])
                for field in ('mean','CV','complex_coherence'):
                    x=get('chunks_'+prefix+'_'+field);target=source[prefix+'_'+field]
                    key='power_error_dB' if field=='mean' else 'CV_error' if field=='CV' else 'coherence_error'
                    truths['chunks_'+prefix+'_'+key]=np.array([[10*math.log10(v/t) for v,t in zip(part,target)] for part in x]) if field=='mean' else abs(x-target)
                signed=group_summary(z[prefix+'_Gram'])
                for field in fields:truths[prefix+'_'+field+'_over_reference']=signed[field]/source[prefix+'_mean'].reshape(4,2)
            for key,truth in truths.items():
                error=float(abs(truth-np.asarray(row[key])).max());assert error<1e-8,(identity,key,error);maximum=max(maximum,error)
            if name!='fixed':
                target=z['independent_relative_max_step'] if name=='independent_marginal' else oldz[name+'_maximum_unwrapped_relative_phase_step']
                assert np.array_equal(target,np.asarray(row['maximum_relative_phase_step']))
    assert len(verified)==108

    def flat(parts):return [float(x) for part in parts for x in np.asarray(part).ravel()]
    def quantiles(values):
        x=sorted(values);out=[]
        for p in (0,.25,.5,.75,1):
            index=(len(x)-1)*p;low=int(index);high=min(low+1,len(x)-1);f=index-low
            out.append(x[low]+f*(x[high]-x[low]))
        return out
    def close(x,y):assert np.allclose(x,y,rtol=1e-12,atol=2e-10),(x,y)
    for name,saved in summary['variants'].items():
        selected=[r for r in rows if r['variant']==name];assert len(selected)==18
        for key,value in saved.items():
            if key=='maximum_relative_phase_step_quantiles':close(value,quantiles(flat([r['maximum_relative_phase_step'] for r in selected])));continue
            values=flat([r[key] for r in selected]);assert value['count']==len(values)
            close(value['mean'],math.fsum(values)/len(values));close(value['mean_absolute'],math.fsum(abs(x) for x in values)/len(values));close(value['quantiles'],quantiles(values))
    for key,paired in summary['paired'].items():
        new_name,old_name=key.split('_minus_');target={(r['label'],r['seed']):r for r in rows if r['variant']==old_name}
        chosen=[r for r in rows if r['variant']==new_name]
        for prefix in ('line','broad','chunks_line','chunks_broad'):
            for suffix,tolerance in summary['comparison_tolerances'].items():
                name=prefix+'_'+suffix
                x=flat([abs(np.asarray(r[name])) for r in chosen]);y=flat([abs(np.asarray(target[r['label'],r['seed']][name])) for r in chosen])
                d=[a-b for a,b in zip(x,y)];value=paired[name]
                assert value['improved']==sum(t < -tolerance for t in d)
                assert value['regressed']==sum(t > tolerance for t in d)
                assert value['equal_within_numeric_gate']==sum(abs(t)<=tolerance for t in d)
                for tag,op in (('improved',lambda a,b:a<b),('equal',lambda a,b:a==b),('regressed',lambda a,b:a>b)):
                    assert value['literal_'+tag]==sum(op(a,b) for a,b in zip(x,y))
                close(value['mean_signed_error_change'],math.fsum(d)/len(d))
        for prefix in ('line','broad'):
            for field in fields:
                name=prefix+'_'+field+'_over_reference'
                x=flat([r[name] for r in chosen]);y=flat([target[r['label'],r['seed']][name] for r in chosen]);d=[a-b for a,b in zip(x,y)]
                value=paired[prefix+'_signed_change_'+field]
                close(value['mean'],math.fsum(d)/len(d));close(value['quantiles'],quantiles(d))
                assert value['literal_positive']==sum(v>0 for v in d) and value['literal_negative']==sum(v<0 for v in d) and value['literal_zero']==sum(v==0 for v in d)
    save(a.review/'metrics_verification.json',dict(result='independent_phase_stream_publication_passed',all108_rows_and_aggregates_verified=True,
        full_Gram_signed_budgets_verified=True,literal_and_numeric_counts_verified=True,maximum_row_error=maximum,
        figure_inputs_sha256=sha(a.review/'figure_inputs.json'),summary_sha256=sha(a.review/'summary.json'),auditor_sha256=sha(__file__)))
    print('independent_phase_stream_publication_passed',flush=True)


if __name__=='__main__':main()
