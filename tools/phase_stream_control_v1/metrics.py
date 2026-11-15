"""All108 outcomes and signed budgets; no source/band/seed selection."""
import numpy as np
from research_archive_v1 import load,sha

VARIANTS=('fixed','relative','independent_marginal','parent','density','variation')
FIELDS=('low_power','rest_power','signed_low_rest_cross','total_power')


def collect(producer,study,parent,carrier,record_inputs=None):
    entries={r['path']:r['sha256'] for r in load(carrier/'manifest.json')['files']}
    original=load(carrier/'evidence/real1/report.json')
    descriptors={(r['label'],s['seed'],name):desc for r in original['cases'] for s in r['seeds'] for name,desc in s['variants'].items()}
    rows=[]
    def consume(path):
        digest=sha(path)
        if record_inputs is not None:record_inputs[str(path)]=digest
        return digest
    for case in producer['cases']:
        label=case['label']
        source_path=parent/label/'source.npz';consume(source_path)
        with np.load(source_path) as z:source={k:z[k] for prefix in ('line','broad') for k in (prefix+'_mean',prefix+'_CV',prefix+'_complex_coherence')}
        for seed in case['seeds']:
            old_path=parent/label/f'probe_{seed["seed"]}.npz';consume(old_path)
            with np.load(old_path) as old:
                for name in VARIANTS:
                    new=name=='independent_marginal'
                    path=study/label/seed['file'] if new else carrier/'evidence/real1'/label/descriptors[label,seed['seed'],name]['file']
                    digest=consume(path)
                    assert digest==(seed['sha256'] if new else descriptors[label,seed['seed'],name]['sha256'])
                    if not new:assert digest==entries[path.relative_to(carrier).as_posix()]
                    with np.load(path) as z:
                        row=dict(label=label,seed=seed['seed'],variant=name)
                        for prefix in ('line','broad'):
                            get=lambda field:z[field] if new else old[name+'_'+field]
                            mean=get(prefix+'_mean');cv=get(prefix+'_CV');coherence=get(prefix+'_complex_coherence')
                            row[prefix+'_power_error_dB']=(10*np.log10(mean/source[prefix+'_mean'])).tolist()
                            row[prefix+'_CV_error']=abs(cv-source[prefix+'_CV']).tolist()
                            row[prefix+'_coherence_error']=abs(coherence-source[prefix+'_complex_coherence']).tolist()
                            for field in ('mean','CV','complex_coherence'):
                                value=get('chunks_'+prefix+'_'+field)
                                key='power_error_dB' if field=='mean' else 'CV_error' if field=='CV' else 'coherence_error'
                                row['chunks_'+prefix+'_'+key]=(10*np.log10(value/source[prefix+'_mean']) if field=='mean' else abs(value-source[prefix+'_'+field])).tolist()
                            reference=source[prefix+'_mean'].reshape(4,2)
                            for field in FIELDS:
                                value=z[prefix+('_group_' if new else '_')+field]
                                row[prefix+'_'+field+'_over_reference']=(value/reference).tolist()
                            signed=sum(np.asarray(row[prefix+'_'+f+'_over_reference']) for f in FIELDS[:3])
                            assert abs(signed-np.asarray(row[prefix+'_total_power_over_reference'])).max()<2e-9
                        if name!='fixed':row['maximum_relative_phase_step']=(z['independent_relative_max_step'] if new else old[name+'_maximum_unwrapped_relative_phase_step']).tolist()
                    rows.append(row)
    return rows


def summarize(rows):
    result={};tol=dict(power_error_dB=1e-8,CV_error=2e-9,coherence_error=2e-9)
    for name in VARIANTS:
        selected=[r for r in rows if r['variant']==name];values={}
        for key in selected[0]:
            if not key.endswith(('_error_dB','_error','_over_reference')):continue
            x=np.concatenate([np.asarray(r[key]).ravel() for r in selected])
            values[key]=dict(mean=float(x.mean()),mean_absolute=float(abs(x).mean()),count=int(x.size),quantiles=np.quantile(x,[0,.25,.5,.75,1]).tolist())
        if name!='fixed':values['maximum_relative_phase_step_quantiles']=np.quantile([r['maximum_relative_phase_step'] for r in selected],[0,.25,.5,.75,1]).tolist()
        result[name]=values
    comparisons={}
    for new,old in [('independent_marginal','relative')]+[(v,'independent_marginal') for v in ('parent','density','variation')]:
        lookup={(r['label'],r['seed']):r for r in rows if r['variant']==old}
        selected=[r for r in rows if r['variant']==new];pair={}
        for prefix in ('line','broad','chunks_line','chunks_broad'):
            for suffix,tolerance in tol.items():
                x=np.concatenate([abs(np.asarray(r[prefix+'_'+suffix])).ravel() for r in selected])
                y=np.concatenate([abs(np.asarray(lookup[r['label'],r['seed']][prefix+'_'+suffix])).ravel() for r in selected])
                delta=x-y
                pair[prefix+'_'+suffix]=dict(improved=int((delta < -tolerance).sum()),equal_within_numeric_gate=int((abs(delta)<=tolerance).sum()),
                    regressed=int((delta>tolerance).sum()),literal_improved=int((x<y).sum()),literal_equal=int((x==y).sum()),literal_regressed=int((x>y).sum()),
                    mean_signed_error_change=float(delta.mean()))
        for prefix in ('line','broad'):
            for field in FIELDS:
                delta=np.array([np.asarray(r[prefix+'_'+field+'_over_reference'])-np.asarray(lookup[r['label'],r['seed']][prefix+'_'+field+'_over_reference']) for r in selected])
                pair[prefix+'_signed_change_'+field]=dict(mean=float(delta.mean()),quantiles=np.quantile(delta,[0,.25,.5,.75,1]).tolist(),
                    literal_positive=int((delta>0).sum()),literal_negative=int((delta<0).sum()),literal_zero=int((delta==0).sum()))
        comparisons[new+'_minus_'+old]=pair
    return dict(variants=result,paired=comparisons,comparison_tolerances=tol,all108_outcomes_retained=True,
        finite_saved_streams_not_population_or_physical_causation=True,normalized_coordinate_only=True,heard=False)
