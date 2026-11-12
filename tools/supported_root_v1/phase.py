"""Resolve low-order phase branches before adding more ambiguous high orders."""
from fractional_clock_v1.phase import refine_once,refine as original_refine


def refine(audio,source_start,normalized,positions,cutoff,coordinate,plan):
    stages=plan.get('fit_order_stages')
    if stages is None:
        return original_refine(audio,source_start,normalized,positions,cutoff,coordinate,plan)
    if len(stages)!=plan['refinement_passes'] or stages[-1]!=plan['fit_orders']:
        raise ValueError('Phase hierarchy must end in the declared complete fit set')
    history=[]
    for orders in stages:
        local=dict(plan,fit_orders=orders)
        normalized,positions,evidence=refine_once(audio,source_start,normalized,positions,cutoff,coordinate,local)
        cutoff=evidence['source_cutoff_hz']
        evidence['declared_fit_orders']=orders
        history.append(evidence)
    return normalized,positions,dict(passes=history,source_cutoff_hz=cutoff)
