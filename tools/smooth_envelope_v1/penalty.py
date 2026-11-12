"""Slow real amplitude prior; numerical observations only, no fixture inputs."""
import numpy as np
from scipy.interpolate import BSpline
from aperture_model_v1.forward import real_rows


def build(model,initial,target,plan,settings):
    order=settings['derivative_order']
    if order!=3:
        raise ValueError('This exact piecewise-constant quadrature is for cubic third derivatives')
    gaps=np.diff(model.orders)
    if len(gaps)<2 or np.any(gaps<=0):
        raise ValueError('At least three ascending measured candidate orders required')
    cutoff=float(gaps.min()/2)
    spacing=plan['amplitude_knot_cycles']
    intervals=np.r_[0.,np.arange(spacing,plan['cycles'],spacing),float(plan['cycles'])]
    knots=np.r_[[0.]*4,intervals[1:-1],[float(plan['cycles'])]*4]
    spline=BSpline(knots,np.eye(len(knots)-4),3)
    midpoint=(intervals[:-1]+intervals[1:])/2
    basis=spline.derivative(order)(midpoint)[:,1:]
    assert basis.shape[1]==model.envelope_count
    deviation=plan['amplitude_control_bound']/np.sqrt(3)
    roughness=basis*np.sqrt(np.diff(intervals))[:,None]/(deviation*(2*np.pi*cutoff)**order)
    residual=model.prediction(initial)-target
    proxy=float(1.4826*np.median(abs(residual-np.median(residual))))
    # The only changing parameters in this prior are real amplitude controls.
    # Constant coefficients, common phase and minority phases have zero columns.
    matrix=np.zeros((model.parts*len(midpoint),model.parameter_count))
    first=2*model.parts+model.phase_count
    for part in range(model.parts):
        rows=slice(part*len(midpoint),(part+1)*len(midpoint))
        columns=slice(first+part*model.envelope_count,first+(part+1)*model.envelope_count)
        matrix[rows,columns]=proxy*roughness
    return matrix,dict(derivative_order=order,cutoff_cycles_per_coarse_cycle=cutoff,
        minimum_measured_order_gap=float(gaps.min()),amplitude_prior_standard_deviation=float(deviation),
        projection_residual_scale_proxy=proxy,prior_rows=matrix.shape[0],quadrature_intervals=intervals.tolist(),
        noise_calibrated=False,strict_bandlimit=False,phase_penalty=False,truth_used=False,heldout_used=False)
