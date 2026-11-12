"""Infer active lines from real finite-window observations on disjoint intervals."""
import numpy as np
from aperture_model_v1.forward import Aperture,real_rows
from .inputs import GEOMETRY_KEYS,DISCOVERY_KEYS


def discover(audio,time,geometry,settings):
    if set(geometry)!=set(GEOMETRY_KEYS) or set(settings)!=set(DISCOVERY_KEYS):
        raise ValueError('Discovery accepts only the declared numerical input fields')
    denominator=settings['dictionary_denominator']
    low,high=settings['dictionary_order_range']
    orders=np.arange(round(low*denominator),round(high*denominator)+1)/denominator
    coefficients=[]
    rows=[]
    for first,stop in settings['support_intervals']:
        selected=(time>=first)&(time<stop)
        local_time=time[selected]
        if not len(local_time):
            raise ValueError('No samples in declared support interval')
        operator=Aperture(len(local_time),geometry)
        angle=2*np.pi*local_time[:,None]*orders[None,:]
        dictionary=np.column_stack((np.cos(angle),np.sin(angle)))
        design=real_rows(operator.apply(dictionary))
        target=real_rows(operator.apply(audio[selected,0]))
        parameters,_,rank,singular=np.linalg.lstsq(design,target,rcond=None)
        condition=float(singular[0]/singular[-1])
        if rank!=len(orders)*2 or condition>settings['maximum_dictionary_condition']:
            raise ValueError('Observed finite-window dictionary is not independently resolved')
        amplitude=np.hypot(parameters[:len(orders)],parameters[len(orders):])
        coefficients.append(amplitude)
        rows.append(dict(interval=[first,stop],amplitudes=amplitude.tolist(),rank=int(rank),condition=condition,
            normalized_constant_line_residual=float(np.linalg.norm(design@parameters-target)/max(np.linalg.norm(target),1e-30))))
    coefficients=np.asarray(coefficients)
    threshold=max(settings['minimum_absolute_amplitude'],settings['minimum_relative_amplitude']*float(coefficients[0].max()))
    supported=np.all(coefficients>=threshold,axis=0)
    chosen=orders[supported].tolist()
    return chosen,dict(orders=orders.tolist(),threshold=threshold,intervals=rows,selected_orders=chosen,
        supported=supported.tolist(),source_truth_supplied=False,heldout_supplied=False,
        interpretation='Measured active constant-line candidates on a declared grid; not physical engine orders or a noise uncertainty estimate')
