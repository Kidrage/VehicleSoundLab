"""All162 outcomes; old108 immutable, new54 independently rendered first."""
import numpy as np
from research_archive_v1 import load,sha

OLD=('fixed','relative','independent_marginal','parent','density','variation')
NEW=('Q_parent','Q_density','Q_variation')
VARIANTS=OLD+NEW
FIELDS=('low_power','rest_power','signed_low_rest_cross','total_power')
PAIRS=[('independent_marginal','relative')]+[(n,'independent_marginal') for n in OLD[3:]]
PAIRS += [(n,old) for n,old in zip(NEW,OLD[3:])]+[(n,b) for n in NEW for b in ('independent_marginal','relative')]


def collect(workspace,study,record):
    stream=workspace/'baselines/phase_stream_control_v1';parent=workspace/'baselines/conditional_phase_time_v1'
    def consume(p):record[str(p)]=sha(p);return p
    def frozen(root,name):
        entries={r['path']:r['sha256'] for r in load(consume(root/'manifest.json'))['files']}
        p=consume(root/name);assert record[str(p)]==entries[name];return p
    rows=load(frozen(stream,'evidence/review1/figure_inputs.json'))
    assert len(rows)==108
    old_summary=load(frozen(stream,'evidence/review1/summary.json'))
    receipt=load(frozen(stream,'evidence/review1/metrics_verification.json'))
    assert receipt['all108_rows_and_aggregates_verified']
    producer=load(consume(study/'report.json'));moments=[]
    for case in producer['cases']:
        label=case['label']
        with np.load(frozen(parent,f'evidence/real1/{label}/source.npz')) as z:
            source={k:z[k] for p in ('line','broad') for k in (p+'_mean',p+'_CV',p+'_complex_coherence')}
        mp=consume(study/label/case['midpoint_moments']['file']);assert sha(mp)==case['midpoint_moments']['sha256']
        with np.load(mp) as z:
            for name in OLD[3:]:
                loss=abs(z[name+'_new']-z[name+'_old'])
                moments.append(dict(label=label,variant='Q_'+name,loss=loss.tolist(),count=int(loss.size)))
        for seed in case['seeds']:
            for name,desc in seed['decoders'].items():
                path=consume(study/label/desc['file']);assert sha(path)==desc['sha256']
                with np.load(path) as z:
                    row=dict(label=label,seed=seed['seed'],variant='Q_'+name)
                    for p in ('line','broad'):
                        for f,suffix in (('mean','power_error_dB'),('CV','CV_error'),('complex_coherence','coherence_error')):
                            target=source[p+'_'+f];value=z[p+'_'+f]
                            row[p+'_'+suffix]=(10*np.log10(value/target) if f=='mean' else abs(value-target)).tolist()
                            value=z['chunks_'+p+'_'+f]
                            row['chunks_'+p+'_'+suffix]=(10*np.log10(value/target) if f=='mean' else abs(value-target)).tolist()
                        for field in FIELDS:row[p+'_'+field+'_over_reference']=(z[p+'_'+field]/source[p+'_mean'].reshape(4,2)).tolist()
                        assert abs(sum(np.asarray(row[p+'_'+f+'_over_reference']) for f in FIELDS[:3])-np.asarray(row[p+'_total_power_over_reference'])).max()<2e-9
                    row['maximum_relative_phase_step']=z['maximum_phase_step'].tolist()
                    # Separate instantaneous coefficient probe, not observer scores.
                    row['instant_mean']=z['instant_mean'].tolist();row['instant_CV']=z['instant_CV'].tolist()
                    row['instant_complex_coherence_pairs']=np.stack((z['instant_complex_coherence'].real,z['instant_complex_coherence'].imag),axis=-1).tolist()
                    rows.append(row)
    assert len(rows)==162 and sum(r['count'] for r in moments)==160704
    return rows,moments,old_summary


def summarize(rows,moments):
    result={};tolerance=dict(power_error_dB=1e-8,CV_error=2e-9,coherence_error=2e-9)
    for name in VARIANTS:
        selected=[r for r in rows if r['variant']==name];assert len(selected)==18
        values={}
        for key in selected[0]:
            if not key.endswith(('_error_dB','_error','_over_reference')):continue
            x=np.concatenate([np.asarray(r[key]).ravel() for r in selected])
            values[key]=dict(mean=float(x.mean()),mean_absolute=float(abs(x).mean()),count=int(x.size),quantiles=np.quantile(x,[0,.25,.5,.75,1]).tolist())
        if name!='fixed':values['maximum_relative_phase_step_quantiles']=np.quantile([r['maximum_relative_phase_step'] for r in selected],[0,.25,.5,.75,1]).tolist()
        result[name]=values
    comparisons={}
    for new,old in PAIRS:
        lookup={(r['label'],r['seed']):r for r in rows if r['variant']==old};chosen=[r for r in rows if r['variant']==new];pair={}
        for prefix in ('line','broad','chunks_line','chunks_broad'):
            for suffix,tol in tolerance.items():
                key=prefix+'_'+suffix
                x=np.concatenate([abs(np.asarray(r[key])).ravel() for r in chosen]);y=np.concatenate([abs(np.asarray(lookup[r['label'],r['seed']][key])).ravel() for r in chosen]);d=x-y
                pair[key]=dict(improved=int((d < -tol).sum()),equal_within_numeric_gate=int((abs(d)<=tol).sum()),regressed=int((d>tol).sum()),
                               literal_improved=int((x<y).sum()),literal_equal=int((x==y).sum()),literal_regressed=int((x>y).sum()),mean_signed_error_change=float(d.mean()))
        for prefix in ('line','broad'):
            for field in FIELDS:
                key=prefix+'_'+field+'_over_reference';d=np.array([np.asarray(r[key])-np.asarray(lookup[r['label'],r['seed']][key]) for r in chosen])
                pair[prefix+'_signed_change_'+field]=dict(mean=float(d.mean()),quantiles=np.quantile(d,[0,.25,.5,.75,1]).tolist(),literal_positive=int((d>0).sum()),literal_negative=int((d<0).sum()),literal_zero=int((d==0).sum()))
        comparisons[new+'_minus_'+old]=pair
    moment_summary={}
    for name in NEW:
        x=np.concatenate([np.asarray(r['loss']).ravel() for r in moments if r['variant']==name])
        moment_summary[name]=dict(count=int(x.size),mean=float(x.mean()),quantiles=np.quantile(x,[0,.25,.5,.75,1]).tolist(),
                                  changed_beyond_2e_12=int((x>2e-12).sum()))
    return dict(variants=result,paired=comparisons,comparison_tolerances=tolerance,midpoint_circular_moment_loss=moment_summary,
                all162_outcomes_retained=True,all160704_midpoint_moments_retained=True,
                midpoint_geometry_unweighted_not_material_distribution=True,normalized_coordinate_only=True,heard=False)
