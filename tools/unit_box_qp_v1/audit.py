"""Independently map and certify saved unit-box QPs without solving."""
import numpy as np
from phase_envelope_blocks_v1.checks import certificate_function


def check(q,gram,gradient,weighted,matrix,lower,upper,certificate):
    # Existing independent certificate checks original full KKT and old QR lift.
    if np.max(abs(gradient))>0:
        result=certificate(q,gram,gradient,(matrix,lower,upper),weighted)
    else:
        # The legacy checker assumes nonzero gradient normalization.
        scale=max(float(abs(gram).max()),1.);x=np.array(q['primal_solution']);y=np.array(q['dual_solution'])
        primal=float(max(0.,np.max(lower-matrix@x),np.max(matrix@x-upper)))
        dual=float(abs((gram+gram.T)@x/(2*scale)+matrix.T@y).max())
        assert scale==q['objective_scale'] and primal==q['constraint_violation'] and dual==q['normalized_dual_stationarity']
        assert primal<=1e-9 and dual<=1e-8 and q['success']
        result=dict(success=True,zero_gradient_scale_checked=True)
    coarse=q.get('coarse_attempt',q)
    transform=coarse['unit_transform'];radius=transform['radius'];d=np.array(transform['row_scales'])
    dense=matrix.toarray();expected=[]
    for row,lo,hi in zip(dense,lower,upper):
        values=[abs(float(a)*radius) for a in row]
        if np.isfinite(lo):values.append(abs(float(lo)))
        if np.isfinite(hi):values.append(abs(float(hi)))
        largest=max(values);expected.append(largest if largest>0 else 1.)
    assert np.array_equal(d,expected)
    t=np.array(transform['unit_primal']);x=np.array(coarse['primal_solution'])
    assert np.array_equal(x,radius*t)
    high=np.flatnonzero(np.isfinite(upper));low=np.flatnonzero(np.isfinite(lower))
    z=np.array(coarse['inequality_dual']);unit_z=np.array(transform['unit_inequality_dual'])
    assert np.array_equal(z,unit_z*np.r_[radius/d[high],radius/d[low]])
    aux=np.array(transform['unit_auxiliary']);eq=np.array(transform['unit_equality_dual'])
    assert np.array_equal(np.array(coarse['auxiliary_solution']),np.sqrt(radius)*aux)
    assert np.array_equal(np.array(coarse['equality_dual']),np.sqrt(radius)*eq)
    factor=np.linalg.qr(weighted,mode='r');scale=coarse['objective_scale']
    root=factor*np.sqrt(radius/scale)
    unit_equality_error=float(abs(root@t-aux).max())
    # Objective/row algebra checked on the actual candidate, not reoptimized.
    original_objective=float(.5*x@gram@x+gradient@x)
    transformed_objective=float(.5*t@(radius*gram/scale)@t+(gradient/scale)@t)
    objective_error=abs(original_objective/(scale*radius)-transformed_objective)
    assert objective_error<=1e-12*max(1.,abs(transformed_objective))
    unit_matrix=dense*(radius/d)[:,None]
    row_error=float(abs(unit_matrix@t-(matrix@x)/d).max());assert row_error<=1e-12
    assert transform['objective_divisor']==scale*radius
    result.update(unit_primal_dual_map_exact=True,row_scales_exact=True,unit_lifted_equality_error=unit_equality_error,
        equivalent_objective_error=float(objective_error),equivalent_row_error=row_error)
    return result
