"""Analytic first-order boundary alias, independent of any fitted phase."""
import numpy as np
from aperture_model_v1.forward import Aperture,real_rows
from .geometry import extend


def controls(plan):
    time=np.arange(plan['cycles']*plan['samples_per_cycle'])/plan['samples_per_cycle']
    orders=np.arange(1,8.0001,.2)
    # Exact grid construction avoids arange drift in harmonic identities.
    orders=np.arange(5,41)/5
    coefficients=(.02+.003*np.cos(np.arange(len(orders))*.29))*np.exp(1j*(.31*orders+.07*orders**2))
    gap=.2
    amount=.001
    angle=np.exp(2j*np.pi*time[:,None]*orders)
    derivative=np.real(angle@(2j*np.pi*orders*coefficients))
    phase_direction=amount*np.sin(2*np.pi*gap*time)
    apparent_change=phase_direction*derivative
    correction=np.zeros_like(coefficients)
    for index,order in enumerate(orders):
        if index+1<len(orders):
            correction[index+1]-=np.pi*amount*order*coefficients[index]
        if index>0:
            correction[index-1]+=np.pi*amount*order*coefficients[index]
    remaining=apparent_change+np.real(angle@correction)
    # Scalar analytic expression for only the two boundary sidebands.
    boundary=np.real(np.pi*amount*(orders[-1]*coefficients[-1]*np.exp(2j*np.pi*(orders[-1]+gap)*time)-
        orders[0]*coefficients[0]*np.exp(2j*np.pi*(orders[0]-gap)*time)))
    closure=float(abs(remaining-boundary).max())
    assert closure<1e-12
    old={**plan,'source_orders':orders.tolist(),'observed_order_range':[1,8]}
    guarded,evidence=extend(old)
    before=real_rows(Aperture(len(time),old).apply(remaining))
    after=real_rows(Aperture(len(time),guarded).apply(remaining))
    hidden=float(np.linalg.norm(before))
    exposed=float(np.linalg.norm(after))
    assert hidden<1e-12 and exposed>1e-4
    assert guarded['source_orders']==old['source_orders']
    original_shape=float(np.linalg.norm(real_rows(Aperture(len(time),old).apply(apparent_change))))
    return dict(passed=True,analytic_sample_closure_maximum_error=closure,
        original_observation_boundary_residual_norm=hidden,guarded_boundary_residual_norm=exposed,
        uncompensated_phase_direction_projection_norm=original_shape,
        phase_amplitude_cycles=amount,phase_modulation_order=gap,guard_geometry=evidence,
        interpretation='First-order alias hidden by candidate-complete projection; not proof of global waveform nonidentifiability')
