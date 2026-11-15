"""Convex primal/dual gap on the original complete weighted objective.

This is a floating-point evaluation of an analytic bound, not interval arithmetic,
physical identifiability, a listening score or a replacement LSMR stop code.
"""
import numpy as np
from scipy import linalg
from observer_inverse_v1.fit import real_vector, complex_array


def bound(system, audio, nodes):
    q = nodes/system.scale[None]
    x = real_vector(q)
    y = system.rhs(audio)[:system.ysize]
    residual = (system@x)[:system.ysize]-y
    rows = np.zeros(system.shape[0]); rows[:system.ysize] = residual
    p = complex_array(system.rmatvec(rows), system.nshape)
    D = system.D.toarray()
    R = system.alpha*D.T@D+system.beta*np.eye(len(q))
    inverse_p = linalg.cho_solve(linalg.cho_factor(R), p.reshape(len(q), -1)).reshape(q.shape)
    r2 = float(residual@residual)
    yr = float(y@residual)
    pRinvp = float(np.vdot(p, inverse_p).real)
    if pRinvp < -1e-10*max(1., r2):
        raise ArithmeticError('Negative inverse-penalty quadratic form')
    denominator = r2+max(0., pRinvp)
    t = -yr/denominator if denominator else 0.
    def penalty(z):
        d = D@z.reshape(len(z), -1)
        return float(system.alpha*np.sum(abs(d)**2)+system.beta*np.sum(abs(z)**2))
    primal = r2+penalty(q)
    dual = -(t*t)*denominator-2*t*yr
    # Stable sum of nonnegative squares, rather than subtracting nearly equal
    # primal and dual values. The dual point u=t*r is always feasible.
    gap = (1-t)**2*r2+penalty(q+t*inverse_p)
    if abs((primal-dual)-gap) > 2e-8*max(1., primal, abs(dual)):
        raise ArithmeticError('Primal/dual identity failed')
    relative = gap/max(primal, 1e-24)
    return dict(primal=primal, dual_lower_bound=dual, gap_upper_bound=gap,
        relative_gap_upper_bound=relative, residual_dual_scale=t,
        weighted_wave_distance_to_optimum_upper_bound=float(np.sqrt(gap)),
        normalized_node_distance_to_optimum_upper_bound=float(np.sqrt(gap/system.beta)),
        additional_gap_gate_passed=bool(gap <= 1e-6*primal+1e-10),
        relative_gate=1e-6, absolute_gate=1e-10,
        original_LSMR_gate_unchanged=True, floating_point_not_interval_certificate=True,
        physical_source_or_sustained_or_hearing_qualified=False)
