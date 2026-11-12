"""Scalar adjoint and explicit covariance controls with no analytic fixtures."""
import numpy as np
from aperture_model_v1.forward import Aperture,real_rows
from .covariance import adjoint,covariance_trace


def controls(plan):
    local={**plan,'cycles':20,'samples_per_cycle':32}
    frames=local['cycles']*local['samples_per_cycle']
    operator=Aperture(frames,local)
    rng=np.random.default_rng(827530)
    samples=rng.normal(size=frames)
    projected=real_rows(operator.apply(samples))
    weights=rng.normal(size=(len(projected),3))
    back=adjoint(operator,weights,frames)
    expected=projected@weights
    observed=samples@back
    inner_product_error=float(np.linalg.norm(expected-observed)/np.linalg.norm(expected))
    assert inner_product_error<1e-12
    explicit=real_rows(operator.apply(np.eye(frames)))
    operator_error=float(abs(explicit.T@weights-back).max())
    assert operator_error<1e-12
    trace=float(np.sum(explicit**2))
    trace_error=abs(trace-covariance_trace(operator))/trace
    assert trace_error<1e-12
    return dict(passed=True,inner_product_relative_error=inner_product_error,
        explicit_matrix_adjoint_maximum_error=operator_error,exact_covariance_trace_relative_error=trace_error,
        scalar_covariance_trace=trace,source_frames=frames)
