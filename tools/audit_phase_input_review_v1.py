"""Independent all216 rows,54 signed Gram budgets and all published counts."""
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
    from phase_input_paths_v1.audit_oracle import budget
    repo=Path(__file__).resolve().parents[1];published=load(a.review/'report.json')
    for name,digest in published['sources'].items():assert sha(repo/name)==sha(a.review/'exact_sources'/name)==digest
    for key in ('summary','figure_inputs'):assert sha(a.review/(key+'.json'))==published[key+'_sha256']
    shutil.copy2(__file__,a.review/'executed_metrics_audit.py')
    data=load(a.review/'figure_inputs.json');rows=data['rows'];budgets=data['budgets'];s=load(a.review/'summary.json')
    producer=load(a.study/'report.json');parent=a.workspace/'baselines/conditional_phase_time_v1/evidence/real1'
    paths={(r['label'],seed['seed'],name):a.study/r['label']/desc['file'] for r in producer['cases'] for seed in r['seeds'] for name,desc in seed['decoders'].items()}
    truth_budgets={};maximum=0.;unique=set()
    for row in rows:
        identity=(row['label'],row['seed'],row['decoder']);tag=row['counterfactual'];key=(*identity,tag);assert key not in unique;unique.add(key)
        with np.load(paths[identity]) as z,np.load(parent/row['label']/'source.npz') as source:
            for prefix in ('line','broad'):
                truth={prefix+'_power_error_dB':[10*math.log10(x/y) for x,y in zip(z[tag+'_'+prefix+'_mean'],source[prefix+'_mean'])],
                    prefix+'_CV_error':abs(z[tag+'_'+prefix+'_CV']-source[prefix+'_CV']),
                    prefix+'_coherence_error':abs(z[tag+'_'+prefix+'_complex_coherence']-source[prefix+'_complex_coherence'])}
                for field,short in (('mean','power_error_dB'),('CV','CV_error'),('complex_coherence','coherence_error')):
                    x=z[tag+'_chunks_'+prefix+'_'+field];target=source[prefix+'_'+field]
                    truth['chunks_'+prefix+'_'+short]=np.array([[10*math.log10(v/t) for v,t in zip(part,target)] for part in x]) if field=='mean' else abs(x-target)
                for k,v in truth.items():
                    error=float(abs(np.asarray(v)-np.asarray(row[k])).max());assert error<1e-8;maximum=max(maximum,error)
                if tag=='joint':
                    values=budget(z['term_'+prefix+'_Gram']);ref=source[prefix+'_mean'].reshape(4,2)
                    entry=truth_budgets.setdefault(identity,{})
                    for field in ('self_power','signed_pairs','total_power'):
                        x=values[field];entry[prefix+'_'+field+'_over_reference']=x/ref.reshape((4,)+(1,)*(x.ndim-2)+(2,))
            assert np.array_equal(np.asarray(row['maximum_phase_step']),z['maximum_phase_step'][:,('base','P_only','U_only','joint').index(tag)])
            if tag=='joint':truth_budgets[identity]['phase_interaction_RMS_max']=z['phase_interaction_RMS_max']
    assert len(unique)==216 and len(truth_budgets)==54 and len(budgets)==54
    for b in budgets:
        identity=b['label'],b['seed'],b['decoder']
        for key,truth in truth_budgets[identity].items():assert abs(truth-np.asarray(b[key])).max()<1e-8
    def flat(parts):return [float(v) for p in parts for v in np.asarray(p).ravel()]
    def q(values):
        x=sorted(values);out=[]
        for p in (0,.25,.5,.75,1):
            i=(len(x)-1)*p;j=int(i);f=i-j;out.append(x[j]+f*(x[min(j+1,len(x)-1)]-x[j]))
        return out
    def check(x,y):assert np.allclose(x,y,rtol=1e-12,atol=2e-10),(x,y)
    for decoder,variants in s['decoders'].items():
        for cf,values in variants.items():
            chosen=[r for r in rows if r['decoder']==decoder and r['counterfactual']==cf];assert len(chosen)==18
            for key,v in values.items():
                if key=='maximum_phase_step_quantiles':check(v,q(flat([r['maximum_phase_step'] for r in chosen])));continue
                x=flat([r[key] for r in chosen]);assert v['count']==len(x)
                check(v['mean'],math.fsum(x)/len(x));check(v['mean_absolute'],math.fsum(abs(t) for t in x)/len(x));check(v['quantiles'],q(x))
    for decoder,pairs in s['paired'].items():
        for pair,values in pairs.items():
            newer,older=pair.split('_minus_');target={(r['label'],r['seed']):r for r in rows if r['decoder']==decoder and r['counterfactual']==older}
            chosen=[r for r in rows if r['decoder']==decoder and r['counterfactual']==newer]
            for prefix in ('line','broad','chunks_line','chunks_broad'):
                for suffix,tol in s['comparison_tolerances'].items():
                    key=prefix+'_'+suffix;x=flat([abs(np.asarray(r[key])) for r in chosen]);y=flat([abs(np.asarray(target[r['label'],r['seed']][key])) for r in chosen]);d=[a-b for a,b in zip(x,y)];v=values[key]
                    assert v['improved']==sum(t < -tol for t in d) and v['regressed']==sum(t>tol for t in d) and v['equal_within_numeric_gate']==sum(abs(t)<=tol for t in d)
                    assert v['literal_improved']==sum(a<b for a,b in zip(x,y)) and v['literal_equal']==sum(a==b for a,b in zip(x,y)) and v['literal_regressed']==sum(a>b for a,b in zip(x,y))
                    check(v['mean_signed_error_change'],math.fsum(d)/len(d))
    for decoder,v in s['signed_budgets'].items():
        chosen=[b for b in budgets if b['decoder']==decoder]
        for prefix in ('line','broad'):
            for field in ('self_power','signed_pairs','total_power'):
                key=prefix+'_'+field+'_over_reference';n=1 if field=='total_power' else 4 if field=='self_power' else 6
                sequences=[flat([np.asarray(b[key])[:,i,:] if n>1 else b[key] for b in chosen]) for i in range(n)]
                means=[math.fsum(x)/len(x) for x in sequences];bounds=[[min(x) for x in sequences],[max(x) for x in sequences]]
                check(v[prefix+'_'+field+'_mean_over_reference'],means[0] if n==1 else means)
                check(v[prefix+'_'+field+'_minmax_over_reference'],[bounds[0][0],bounds[1][0]] if n==1 else bounds)
        check(v['phase_interaction_RMS_max_quantiles'],np.array([q(flat([np.asarray(b['phase_interaction_RMS_max'])[:,j] for b in chosen])) for j in (0,1)]).T)
    save(a.review/'metrics_verification.json',dict(result='independent_phase_input_publication_passed',all216_rows54_budgets_and_aggregates_verified=True,
        full_Gram_signed_interference_verified=True,literal_and_numeric_counts_verified=True,maximum_row_error=maximum,
        figure_inputs_sha256=sha(a.review/'figure_inputs.json'),summary_sha256=sha(a.review/'summary.json'),auditor_sha256=sha(__file__)))
    print('independent_phase_input_publication_passed',flush=True)


if __name__=='__main__':main()
