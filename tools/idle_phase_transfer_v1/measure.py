"""Read-only frozen power-law coordinates and moments; no synthesis or fitting."""
import numpy as np
from idle_phase_difference_v1.features import matrix
from idle_positive_power_v1.model import predict


def phasors(profile, first, frames, rate=48000):
    index = [1, 2, 4]; modal = profile['modal']
    t = np.arange(first, first+frames)/rate
    theta = 2*np.pi*np.remainder(t[:, None]*np.asarray(modal['frequencies_hz'])[index], 1.)
    theta += np.asarray(modal['initial_phase_LR'])[index, 0]
    return np.exp(1j*theta)


def observe(z, law):
    feature = matrix(z, hop=1, trim=0); q = predict(law, feature)
    closure = z[:, 2]*z[:, 1].conj()*z[:, 0].conj()
    circular = np.r_[z.mean(axis=0), closure.mean()]
    mean = q.mean(axis=0); centered = q-mean
    values = dict(mean=mean, second=q.T@q/len(q), covariance=centered.T@centered/len(q),
                  quantiles=np.quantile(q, [0., .01, .5, .99, 1.], axis=0),
                  feature_mean=feature.mean(axis=0), circular=circular,
                  resultant=abs(circular))
    assert np.all(q > 0) and np.isfinite(q).all()
    assert np.all(q.min(axis=0) >= law['bounds']['power_lower'])
    assert np.all(q.max(axis=0) <= law['bounds']['power_upper'])
    return q, values


def serial(values):
    out = {key: value.tolist() for key, value in values.items() if key != 'circular'}
    out['circular_real_imag'] = np.column_stack((values['circular'].real, values['circular'].imag)).tolist()
    return out


def known():
    t = np.arange(48000)/48000; f = np.array([75., 112.5, 187.5]); p = np.array([.2, -.4, .7])
    z = np.exp(1j*(2*np.pi*t[:, None]*f+p))
    coefficient = np.zeros((13, 4)); coefficient[0] = np.log([.7, 1., 1.3, 2.])
    from idle_positive_power_v1.model import bounds
    law = dict(coefficients=coefficient.tolist(), bounds=bounds(coefficient))
    q, values = observe(z, law); expected = np.tile([.7, 1., 1.3, 2.], (len(z), 1))
    constant_error = float(abs(q-expected).max()); assert constant_error < 1e-14
    closure = z[:, 2]*z[:, 1].conj()*z[:, 0].conj()
    closure_error = float(abs(closure-np.exp(1j*(p[2]-p[1]-p[0]))).max()); assert closure_error < 5e-12
    tt = np.arange(0, 180*48000, 48)/48000; detuned = f.copy(); detuned[2] += .00625
    zz = np.exp(1j*(2*np.pi*tt[:, None]*detuned+p))
    closure = zz[:, 2]*zz[:, 1].conj()*zz[:, 0].conj()
    oracle = np.exp(1j*(p[2]-p[1]-p[0]+2*np.pi*.00625*tt))
    detuned_error = float(abs(closure-oracle).max()); assert detuned_error < 1e-10
    coefficient = np.sin(np.arange(52).reshape(13, 4))*.07
    law = dict(coefficients=coefficient.tolist(), bounds=bounds(coefficient)); q, _ = observe(z, law)
    delta = np.array([.41, -.37, .83]); changes = np.r_[delta, delta[1]-delta[0], delta[2]-delta[0], delta[2]-delta[1]]
    rotated = coefficient.copy(); a, b = coefficient[1:7], coefficient[7:]
    rotated[1:7] = a*np.cos(changes[:, None])-b*np.sin(changes[:, None])
    rotated[7:] = a*np.sin(changes[:, None])+b*np.cos(changes[:, None])
    newlaw = dict(coefficients=rotated.tolist(), bounds=bounds(rotated))
    adjusted, _ = observe(z*np.exp(1j*delta), newlaw)
    rotation_error = float(abs(adjusted-q).max()); assert rotation_error < 1e-12
    chunks = np.concatenate([observe(z[i:i+777], law)[0] for i in range(0, len(z), 777)])
    chunk_error = float(abs(chunks-q).max()); assert chunk_error < 1e-12
    return dict(constant_error=constant_error, closure_error=closure_error, detuned180s_error=detuned_error,
                phase_origin_rotation_error=rotation_error, chunk_error=chunk_error)
