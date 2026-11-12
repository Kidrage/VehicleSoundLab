"""Fractional-grid projections; no assumption of an integer-only spectrum."""
import numpy as np
from .coordinate import render
from .projection import project as project_joint


def project(audio, cycle, orders, projection_cycles, hop_coarse_cycles, window_kind='hann'):
    size = round(projection_cycles*cycle)
    starts = np.arange(0, len(audio)-size+1, round(hop_coarse_cycles*cycle))
    if len(starts)<3:
        raise ValueError('Insufficient complete fractional-grid projection windows')
    orders = np.asarray(orders, dtype=float)
    bins = orders*projection_cycles
    if np.max(abs(bins-np.round(bins)))>1e-8:
        raise ValueError('Projection does not resolve the declared fractional grid')
    window = np.ones(size) if window_kind=='rectangular' else .5-.5*np.cos(2*np.pi*np.arange(size)/size)
    values = np.array([np.fft.rfft(audio[start:start+size]*window[:,None], axis=0)[np.round(bins).astype(int)]
        *2/window.sum() for start in starts])
    return starts, values*np.exp(-2j*np.pi*starts[:,None,None]*orders[None,:,None]/cycle), size


def diagnostics(audio, cycle, heldout, cycles, rules):
    check_orders = sorted(set(heldout+[2,3,5,7,15]))
    _, values, _ = project(audio, cycle, check_orders, cycles, .25)
    power = abs(values[:,:,0])**2
    result = {}
    accepted = []
    for index, order in enumerate(check_orders):
        supported = power[:,index] >= np.maximum(power.max(axis=1),1e-30)*.001
        coherence = abs(values[:,index].mean(axis=0))/np.maximum(np.mean(abs(values[:,index]),axis=0),1e-30)
        fitted = order not in heldout
        result[str(order)] = dict(fitted=fitted, supported_fraction=float(supported.mean()), coherence_LR=coherence.tolist())
        if not fitted and supported.mean()>=rules['minimum_carrier_support'] and coherence[0]>=rules['minimum_carrier_coherence']:
            accepted.append(order)
    return dict(carriers=result, accepted_unfitted_orders=accepted,
        passed=len(accepted)>=rules['minimum_separate_carriers'])


def refine_once(audio, source_start, normalized, positions, cutoff, coordinate, plan):
    cycle = coordinate['samples_per_coarse_cycle']
    denominator = coordinate['fractional_denominator']
    maximum_order=max(20,max(plan['fit_orders']))
    observed_orders = np.arange(denominator,round(maximum_order*denominator)+1)/denominator
    if plan.get('projection_mode')=='local_joint':
        starts,values,size,projection_meta=project_joint(normalized,cycle,observed_orders,plan,denominator)
        if projection_meta['maximum_gram_condition']>plan['maximum_gram_condition']:
            raise ValueError('Fractional neighbour system is too ill-conditioned')
    elif plan.get('projection_mode')=='rectangular_grid':
        starts,values,size=project(normalized,cycle,observed_orders,
            plan['projection_cycles'],plan['hop_coarse_cycles'],'rectangular')
        projection_meta=dict(mode='rectangular_grid',full_fifth_grid_periods=plan['projection_cycles']/denominator,
            interpretation='One complete declared fractional-grid period; all grid neighbours are orthogonal without a local inverse')
    else:
        starts, values, size = project(normalized, cycle, observed_orders,
            plan['projection_cycles'], plan['hop_coarse_cycles'])
        projection_meta=dict(mode='long_window_fft')
    fit = np.asarray(plan['fit_orders'])
    columns = np.searchsorted(observed_orders,fit)
    z = values[:,columns,0]
    power = abs(values[:,:,0])**2
    supported = power[:,columns] >= np.maximum(power.max(axis=1,keepdims=True),1e-30)*10**(plan['support_relative_db']/10)
    if np.any(supported.sum(axis=1)<plan['minimum_fit_lines']):
        raise ValueError('Missing simultaneous fractional-grid phase support; no filling')
    offsets = np.full(len(fit), np.nan)
    correction = np.empty(len(starts))
    current = 0.
    for row in range(len(starts)):
        active = supported[row]
        new = active & ~np.isfinite(offsets)
        offsets[new] = np.angle(z[row,new])-2*np.pi*fit[new]*current
        delta = np.angle(z[row,active]*np.exp(-1j*(offsets[active]+2*np.pi*fit[active]*current)))/(2*np.pi*fit[active])
        current += float(np.median(delta))
        correction[row] = current
    for _ in range(plan['global_iterations']):
        for column, order in enumerate(fit):
            active = supported[:,column]
            if active.any():
                offsets[column] = np.angle(np.mean(z[active,column]*np.exp(-2j*np.pi*order*correction[active])))
        error = np.angle(z*np.exp(-1j*(offsets[None,:]+2*np.pi*fit[None,:]*correction[:,None])))/(2*np.pi*fit[None,:])
        reliability = np.array([np.percentile(abs(error[supported[:,column],column]),95)
            if supported[:,column].any() else np.inf for column in range(len(fit))])
        preferred = np.argsort(reliability)[:plan['minimum_fit_lines']]
        for row in range(len(starts)):
            active = preferred[supported[row,preferred]]
            if len(active)<plan['minimum_fit_lines']:
                active = np.flatnonzero(supported[row])
            correction[row] += float(np.average(error[row,active],weights=fit[active]**2))
    final_error = np.angle(z*np.exp(-1j*(offsets[None,:]+2*np.pi*fit[None,:]*correction[:,None])))/(2*np.pi*fit[None,:])
    counts = np.sum(supported & (abs(final_error)<=plan['outlier_cycles']),axis=1)
    if np.any(counts<plan['minimum_fit_lines']):
        raise ValueError('Fractional-grid calibrated lines remain incompatible')
    centers = starts+size/2
    indices = np.arange(int(centers[0]),int(centers[-1])+1)
    phase = indices/cycle+np.interp(indices,centers,correction)
    if min(np.diff(phase))<=0:
        raise ValueError('Measured fractional correction is not monotonic')
    uniform = np.arange(int(np.ceil(phase[0]*cycle)),int(np.floor(phase[-1]*cycle)))/cycle
    at = np.interp(uniform,phase,indices)
    where = np.interp(at,np.arange(len(positions)),positions)
    result, cutoff = render(audio,source_start,where,cycle,cutoff)
    return result,where,dict(preferred_orders=fit[preferred].tolist(),projection=projection_meta,
        phase_residual_p95_cycles=[float(value) if np.isfinite(value) else None for value in reliability],
        minimum_retained_lines=int(min(counts)),
        source_cutoff_hz=cutoff,source_seconds=[float(where[0]),float(where[-1])])


def refine(audio, source_start, normalized, positions, cutoff, coordinate, phase_plan):
    history = []
    for _ in range(phase_plan['refinement_passes']):
        normalized, positions, evidence = refine_once(audio,source_start,normalized,positions,cutoff,coordinate,phase_plan)
        cutoff = evidence['source_cutoff_hz']
        history.append(evidence)
    return normalized, positions, dict(passes=history,source_cutoff_hz=cutoff)
