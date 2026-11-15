"""Retain all216 counterfactuals and all54 anchored signed wave budgets."""
import numpy as np
from research_archive_v1 import sha

DECODERS=('parent','density','variation')
COUNTERFACTUALS=('base','P_only','U_only','joint')


def collect(producer,study,parent):
    rows=[];budgets=[]
    for case in producer['cases']:
        label=case['label']
        with np.load(parent/label/'source.npz') as z:source={k:z[k] for prefix in ('line','broad') for k in (prefix+'_mean',prefix+'_CV',prefix+'_complex_coherence')}
        for seed in case['seeds']:
            for decoder,desc in seed['decoders'].items():
                path=study/label/desc['file'];assert sha(path)==desc['sha256']
                with np.load(path) as z:
                    budget=dict(label=label,seed=seed['seed'],decoder=decoder)
                    for prefix in ('line','broad'):
                        ref=source[prefix+'_mean'].reshape(4,2)
                        for field in ('self_power','signed_pairs','total_power'):
                            x=z['term_'+prefix+'_'+field]
                            budget[prefix+'_'+field+'_over_reference']=(x/ref.reshape((4,)+(1,)*(x.ndim-2)+(2,))).tolist()
                        own=np.asarray(budget[prefix+'_self_power_over_reference']).sum(axis=1)
                        pairs=np.asarray(budget[prefix+'_signed_pairs_over_reference']).sum(axis=1)
                        assert abs(own+pairs-np.asarray(budget[prefix+'_total_power_over_reference'])).max()<2e-9
                    budget['phase_interaction_RMS_max']=z['phase_interaction_RMS_max'].tolist()
                    budgets.append(budget)
                    for j,tag in enumerate(COUNTERFACTUALS):
                        row=dict(label=label,seed=seed['seed'],decoder=decoder,counterfactual=tag,maximum_phase_step=z['maximum_phase_step'][:,j].tolist())
                        for prefix in ('line','broad'):
                            row[prefix+'_power_error_dB']=(10*np.log10(z[tag+'_'+prefix+'_mean']/source[prefix+'_mean'])).tolist()
                            row[prefix+'_CV_error']=abs(z[tag+'_'+prefix+'_CV']-source[prefix+'_CV']).tolist()
                            row[prefix+'_coherence_error']=abs(z[tag+'_'+prefix+'_complex_coherence']-source[prefix+'_complex_coherence']).tolist()
                            for field,key in (('mean','power_error_dB'),('CV','CV_error'),('complex_coherence','coherence_error')):
                                value=z[tag+'_chunks_'+prefix+'_'+field]
                                row['chunks_'+prefix+'_'+key]=(10*np.log10(value/source[prefix+'_mean']) if field=='mean' else abs(value-source[prefix+'_'+field])).tolist()
                        rows.append(row)
    return rows,budgets


def summarize(rows,budgets):
    summaries={};pairs={};tol=dict(power_error_dB=1e-8,CV_error=2e-9,coherence_error=2e-9)
    for decoder in DECODERS:
        variants={}
        for cf in COUNTERFACTUALS:
            chosen=[r for r in rows if r['decoder']==decoder and r['counterfactual']==cf]
            values={}
            for key in chosen[0]:
                if not key.endswith(('_error_dB','_error')):continue
                x=np.concatenate([np.asarray(r[key]).ravel() for r in chosen])
                values[key]=dict(mean=float(x.mean()),mean_absolute=float(abs(x).mean()),quantiles=np.quantile(x,[0,.25,.5,.75,1]).tolist(),count=int(x.size))
            values['maximum_phase_step_quantiles']=np.quantile([r['maximum_phase_step'] for r in chosen],[0,.25,.5,.75,1]).tolist()
            variants[cf]=values
        summaries[decoder]=variants
        paired={}
        for new,old in (('P_only','base'),('U_only','base'),('joint','base'),('P_only','joint'),('U_only','joint')):
            target={(r['label'],r['seed']):r for r in rows if r['decoder']==decoder and r['counterfactual']==old}
            chosen=[r for r in rows if r['decoder']==decoder and r['counterfactual']==new];values={}
            for prefix in ('line','broad','chunks_line','chunks_broad'):
                for suffix,tolerance in tol.items():
                    key=prefix+'_'+suffix
                    x=np.concatenate([abs(np.asarray(r[key])).ravel() for r in chosen])
                    y=np.concatenate([abs(np.asarray(target[r['label'],r['seed']][key])).ravel() for r in chosen]);d=x-y
                    values[key]=dict(improved=int((d < -tolerance).sum()),equal_within_numeric_gate=int((abs(d)<=tolerance).sum()),regressed=int((d>tolerance).sum()),
                        literal_improved=int((x<y).sum()),literal_equal=int((x==y).sum()),literal_regressed=int((x>y).sum()),mean_signed_error_change=float(d.mean()))
            paired[new+'_minus_'+old]=values
        pairs[decoder]=paired
    signed={}
    for decoder in DECODERS:
        selected=[r for r in budgets if r['decoder']==decoder];value={}
        for prefix in ('line','broad'):
            for field in ('self_power','signed_pairs','total_power'):
                x=np.array([r[prefix+'_'+field+'_over_reference'] for r in selected])
                # Source/seed/band/channel mean; preserve each term/pair axis.
                value[prefix+'_'+field+'_mean_over_reference']=x.mean(axis=(0,1,-1)).tolist()
                value[prefix+'_'+field+'_minmax_over_reference']=[x.min(axis=(0,1,-1)).tolist(),x.max(axis=(0,1,-1)).tolist()]
        value['phase_interaction_RMS_max_quantiles']=np.quantile([r['phase_interaction_RMS_max'] for r in selected],[0,.25,.5,.75,1],axis=(0,1)).tolist()
        signed[decoder]=value
    return dict(decoders=summaries,paired=pairs,signed_budgets=signed,comparison_tolerances=tol,
        all216_outcomes_and54_budgets_retained=True,anchor_dependent_counterfactuals_not_physical_source_shares=True,
        fixed_P_or_U_not_sound_presets=True,normalized_coordinate_only=True,native48k_or_listening=False)
