"""Native log-band descriptions retaining both trend and unqualified residual."""
import numpy as np


def describe(matrices, starts, plan):
    spec, config = plan['measurement'], plan['features']
    power = matrices.diagonal(axis1=-2, axis2=-1).real
    floor = config['log_floor_FS2']
    features = 10*np.log10(np.maximum(power, floor)).reshape(len(starts), -1)
    times = (starts+spec['window_samples']/2)/spec['rate']
    design = np.column_stack([np.ones(len(times)), times-times.mean()])
    coefficients = np.linalg.lstsq(design, features, rcond=None)[0]
    trend = design@coefficients
    centered, residual = features-features.mean(axis=0), features-trend
    outputs = dict(times=times, log_power_dB=features, floored=power <= floor,
                   trend_coefficients=coefficients, fitted_trend_dB=trend,
                   affine_residual_dB=residual)
    for name, values in [('centered', centered), ('affine_residual', residual)]:
        outputs[name+'_covariance'] = values.T@values/len(values)
        outputs[name+'_lag_products'] = np.stack([
            values[:-lag].T@values[lag:]/(len(values)-lag) for lag in config['lags_windows']])
        outputs[name+'_eigenvalues'] = np.linalg.eigvalsh(outputs[name+'_covariance'])
    # ILD and complex coherence remain per-window observations; no widening.
    outputs['ILD_dB'] = features[:, 0::2]-features[:, 1::2]
    denominator = np.sqrt(np.maximum(power[:, :, 0], floor)*np.maximum(power[:, :, 1], floor))
    outputs['complex_coherence'] = matrices[:, :, 0, 1]/denominator
    return outputs
