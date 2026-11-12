"""Compare predictive risk to an independent explicit ridge/covariance formula."""
import numpy as np
from aperture_model_v1.forward import Aperture,real_rows
from .select_sure import select
from .covariance import covariance_trace


def controls(plan):
    local={**plan,'cycles':20,'samples_per_cycle':32}
    frames=local['cycles']*local['samples_per_cycle']
    operator=Aperture(frames,local)
    rng=np.random.default_rng(246761)
    wave=rng.normal(size=(frames,12))
    design=real_rows(operator.apply(wave))
    class Linear:
        aperture=operator
        time=np.arange(frames)/local['samples_per_cycle']
        def prediction(self,parameters,jacobian=False):
            value=design@parameters
            return (value,design.copy()) if jacobian else value
    model=Linear()
    actual=rng.normal(0,.03,12)
    initial=rng.normal(0,.01,12)
    target=design@actual+real_rows(operator.apply(rng.normal(0,.04,frames)))
    regularizer=np.zeros((8,12))
    regularizer[:,4:]=np.diag(np.linspace(.7,2.1,8))
    matrix,evidence=select(model,initial,target,regularizer)
    weight=evidence['weight']
    normal=design.T@design+weight*(regularizer.T@regularizer)
    fitted=np.linalg.solve(normal,design.T@target)
    residual=design@fitted-target
    explicit=real_rows(operator.apply(np.eye(frames)))
    source_design=explicit.T@design
    trace=float(np.trace(np.linalg.solve(normal,source_design.T@source_design)))
    variance=evidence['source_white_noise_variance_proxy']
    risk=float(np.dot(residual,residual)+2*variance*trace-variance*covariance_trace(operator))
    risk_error=abs(risk-evidence['risk'])/max(abs(risk),1e-30)
    trace_error=abs(trace-evidence['noise_hat_trace'])/max(abs(trace),1e-30)
    gram_error=float(np.linalg.norm(matrix.T@matrix-weight*regularizer.T@regularizer)/
        max(np.linalg.norm(weight*regularizer.T@regularizer),1e-30))
    assert risk_error<1e-10 and trace_error<1e-10 and gram_error<1e-12
    return dict(passed=True,explicit_ridge_risk_relative_error=risk_error,
        explicit_covariance_hat_trace_relative_error=trace_error,selected_gram_relative_error=gram_error,
        selected_weight=weight,source_white_noise_proxy=evidence['source_white_noise_standard_deviation_proxy'],
        correlated_rows=design.shape[0],parameters=design.shape[1])
