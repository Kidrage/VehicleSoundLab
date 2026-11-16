"""Frozen full-order observations and explicitly scaled complex temporal metrics."""
import numpy as np
from sound_dna.windowed import coefficients


def observe(audio,cycles):
    raw=coefficients(audio,288,cycles).reshape(-1,288,2,2)
    return raw[...,0]+1j*raw[...,1]


def temporal(z,scale):
    x=np.stack((z.real,z.imag),axis=-1).reshape(len(z),-1)
    x-=x.mean(axis=0);c0=x.T@x/len(x)
    rows=[]
    # Absolute source amplitude scale avoids amplifying numerical modulation in
    # exact static or silent controls into unit-variance features.
    for lag in (1,2,4,8):
        c=x[lag:].T@x[:-lag]/(len(x)-lag)
        rows.append(dict(lag_rows=lag,lag_covariance_FS2=c.tolist(),
            skew_norm_over_source_scale_squared=float(np.linalg.norm((c-c.T)/2)/scale**2)))
    return dict(rows=len(z),variance_trace_FS2=float(np.trace(c0)),
        variation_RMS_FS=float(np.sqrt(np.trace(c0))),lags=rows,
        metrics_are_complex_envelope_not_vehicle_or_audibility_scores=True)
