"""Original harmonic observer plus separately normalized full-band wave powers."""
import numpy as np
from sound_dna.windowed import coefficients


def power_statistics(power, cross):
    n = len(power)
    mean = power.mean(axis=0)
    centered = power-mean
    covariance = centered.T@centered/n
    defined = mean > 1e-24
    cv = np.divide(np.sqrt(np.maximum(0, np.diag(covariance))), mean,
                   out=np.zeros_like(mean), where=defined)
    denominator = np.sqrt(mean[::2]*mean[1::2])
    stereo_defined = denominator > 1e-24
    coherence = np.divide(cross.mean(axis=0), denominator, out=np.zeros(len(denominator), complex),
                          where=stereo_defined)
    mid = (mean[::2]+mean[1::2]+2*cross.mean(axis=0).real)/4
    side = (mean[::2]+mean[1::2]-2*cross.mean(axis=0).real)/4
    lags = []
    for lag in range(1, min(9, n)):
        lags.append(centered[:-lag].T@centered[lag:]/(n-lag))
    return dict(mean=mean, covariance=covariance, CV=cv, power_defined=defined,
                complex_coherence=coherence, coherence_defined=stereo_defined,
                mid_power=mid, side_power=side, lag_covariance=np.array(lags))


def coefficient_powers(z, root, bands):
    hz = np.arange(1, z.shape[1]+1)*root
    power = []
    cross = []
    for lo, hi in bands:
        part = z[:, (hz >= lo)&(hz < hi)]
        power.append(np.sum(abs(part)**2, axis=1)/2)
        cross.append(np.sum(part[..., 0]*part[..., 1].conj(), axis=1)/2)
    return np.concatenate(power, axis=1), np.stack(cross, axis=1)


def analyze(audio, harmonics, root, bands):
    raw = coefficients(audio, harmonics, cycles=4).reshape(-1, harmonics, 2, 2)
    z = raw[..., 0]+1j*raw[..., 1]
    power, cross = coefficient_powers(z, root, bands)
    size = 4096
    window = .5-.5*np.cos(2*np.pi*np.arange(size)/size)
    starts = np.arange(0, len(audio)-size+1, 256)
    full = np.array([np.fft.rfft(audio[start:start+size]*window[:, None], axis=0) for start in starts])
    hz = np.fft.rfftfreq(size, d=1/(1024*root))
    scale = np.full(size//2+1, 2/(size*np.dot(window, window)))
    scale[[0, -1]] /= 2
    broad_power = []
    broad_cross = []
    for lo, hi in bands:
        mask = (hz >= lo)&(hz < hi)
        broad_power.append(np.sum(abs(full[:, mask])**2*scale[mask, None], axis=1))
        broad_cross.append(np.sum(full[:, mask, 0]*full[:, mask, 1].conj()*scale[mask], axis=1))
    broad_power = np.concatenate(broad_power, axis=1)
    broad_cross = np.stack(broad_cross, axis=1)
    return dict(coefficients=z, power=power, cross=cross, broadband_power=broad_power,
                broadband_cross=broad_cross,
                **{'line_'+k:v for k, v in power_statistics(power, cross).items()},
                **{'broad_'+k:v for k, v in power_statistics(broad_power, broad_cross).items()})


def summary(measurement):
    result = {}
    for key, value in measurement.items():
        if key in ('coefficients', 'power', 'cross', 'broadband_power', 'broadband_cross'):
            continue
        result[key] = np.stack([value.real, value.imag], axis=-1).tolist() if np.iscomplexobj(value) else value.tolist()
    return result
