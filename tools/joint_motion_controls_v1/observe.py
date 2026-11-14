"""Full native band observations with absolute and normalized variation."""
import numpy as np
from native_regions_v1.spectrum import measure
from joint_envelopes_v1.features import describe


def observe(audio, plan):
    spec = plan['measurement']
    count = 1+(len(audio)-spec['window_samples'])//spec['hop_samples']
    region = np.zeros((count, spec['fft_samples']//2+1), dtype=np.uint8)
    values = measure(audio, region, spec)
    P = values['P_total']
    return dict(audio=audio, P=P, window_starts=values['window_starts'], **describe(P, values['window_starts'], plan))


def summary(values, floor):
    cov = values['affine_residual_covariance'][8:, 8:]
    eigen = np.linalg.eigvalsh(cov)
    return dict(HF_covariance_trace_dB2=float(np.trace(cov)),
                HF_std_dB=np.sqrt(np.maximum(0, np.diag(cov))).reshape(4, 2).tolist(),
                HF_PC1_fraction=float(eigen[-1]/np.trace(cov)) if np.trace(cov) > floor else None,
                HF_floor_values=int(values['floored'][:, 4:].sum()),
                HF_slope_dB_per_second=values['trend_coefficients'][1, 8:].reshape(4, 2).tolist())
