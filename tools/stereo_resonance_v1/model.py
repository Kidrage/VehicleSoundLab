"""Two-channel VAR colour, certified stability and a stereo Welch operator."""
import numpy as np
from scipy import linalg, ndimage, signal


def matrix(row):
    cross = complex(*row['cross'])
    return np.array([[row['power'][0], cross.conjugate()], [cross, row['power'][1]]])


def root(matrix, inverse=False):
    values, vectors = np.linalg.eigh(matrix)
    if min(values) <= 0:
        raise ValueError('Non-positive stereo covariance; no clipping')
    return (vectors * (1/np.sqrt(values) if inverse else np.sqrt(values))) @ vectors.conj().T


def predictor(gamma, order):
    """Gamma[k] = E[x[n] x[n-k]^T]; solve the block Yule-Walker equations."""
    cov = np.block([[gamma[j-i] if j >= i else gamma[i-j].T
                     for j in range(order)] for i in range(order)])
    yz = np.concatenate([gamma[i] for i in range(1, order+1)], axis=1)
    coefficients = linalg.solve(cov, yz.T, assume_a='pos').T
    innovation = gamma[0]-coefficients@yz.T
    return coefficients.reshape(2, order, 2).transpose(1, 0, 2), np.linalg.cholesky((innovation+innovation.T)*.5)


def fit(reference, band, debt, plan):
    rate, n, order = 48000, plan['fft_frames'], plan['order']
    kw = dict(fs=rate, nperseg=2048, noverlap=1536, detrend=False)
    hz, power = signal.welch(reference, axis=0, **kw)
    _, cross = signal.csd(reference[:, 0], reference[:, 1], **kw)
    freq = np.fft.rfftfreq(n, 1/rate)
    raw = np.empty((len(freq), 2, 2), complex)
    for i in range(2):
        raw[:, i, i] = np.interp(freq, hz, power[:, i])
    raw[:, 1, 0] = np.interp(freq, hz, cross.real)+1j*np.interp(freq, hz, cross.imag)
    raw[:, 0, 1] = raw[:, 1, 0].conj()
    raw = ndimage.gaussian_filter1d(raw, plan['spectral_smoothing_hz']/(rate/n), axis=0)
    low, high = band; pad = (high-low)*plan['taper_fraction']
    weight = np.zeros(len(freq)); weight[(freq >= low) & (freq <= high)] = 1
    keep = (freq > low-pad) & (freq < low)
    weight[keep] = .5-.5*np.cos(np.pi*(freq[keep]-low+pad)/pad)
    keep = (freq > high) & (freq < high+pad)
    weight[keep] = .5+.5*np.cos(np.pi*(freq[keep]-high)/pad)
    raw *= weight[:, None, None]
    average = raw.sum(axis=0)*rate/n
    tint = root(debt) @ root(average, inverse=True)
    positive = tint @ raw @ tint.conj().T
    # Positive-frequency one-sided density -> real process covariance.
    full = np.zeros((n, 2, 2), complex)
    full[:n//2+1] = positive*.5
    full[n//2+1:] = full[1:n//2][::-1].conj()
    gamma = np.fft.ifft(full, axis=0).real*rate
    gamma[0] += np.eye(2)*np.trace(gamma[0])*plan['covariance_ridge']/2
    a, noise = predictor(gamma, order)
    coefficients = a.transpose(1, 0, 2).reshape(2, 2*order)
    companion = np.zeros((2*order, 2*order))
    companion[:2] = coefficients; companion[2:, :-2] = np.eye(2*order-2)
    radius = float(max(abs(np.linalg.eigvals(companion))))
    if radius >= plan['max_pole_radius']:
        raise ValueError(f'Unqualified stereo VAR poles: {band}, {radius}')
    certificate = linalg.solve_discrete_lyapunov(companion.T, np.eye(2*order))
    certificate = (certificate+certificate.T)*.5
    certificate /= max(np.diag(certificate))
    np.linalg.cholesky(certificate)
    margin = certificate-companion.T@certificate@companion
    np.linalg.cholesky((margin+margin.T)*.5)
    sos = signal.butter(plan['postfilter_order'], [low-pad, high+pad], fs=rate, btype='bandpass', output='sos')
    return dict(band_hz=band, a=a.tolist(), noise=noise.tolist(), sos=sos.tolist(),
                certificate=certificate.tolist(), gain=1., pole_radius=radius,
                certificate_margin=float(min(np.linalg.eigvalsh(margin))))


def density(model, frames=65536):
    a = np.array(model['a']); hz = np.arange(frames)*48000/frames
    phase = np.exp(-2j*np.pi*hz[:, None]*np.arange(1, len(a)+1)/48000)
    b = np.eye(2)-np.einsum('nk,kij->nij', phase, a)
    h = np.empty_like(b); det = b[:, 0, 0]*b[:, 1, 1]-b[:, 0, 1]*b[:, 1, 0]
    h[:, 0, 0] = b[:, 1, 1]/det; h[:, 1, 1] = b[:, 0, 0]/det
    h[:, 0, 1] = -b[:, 0, 1]/det; h[:, 1, 0] = -b[:, 1, 0]/det
    noise = np.array(model['noise']); sigma = noise@noise.T
    _, post = signal.sosfreqz(model['sos'], worN=2*np.pi*hz/48000)
    return (h@sigma@h.conj().transpose(0, 2, 1))/48000*abs(post[:, None, None])**2


def measured(density, bands):
    n = len(density); size = 2048
    window = signal.windows.hann(size, sym=False)
    kernel = abs(np.fft.fft(window, n))**2; kernel /= kernel.sum()
    smooth = np.fft.ifft(np.fft.fft(density, axis=0)*np.fft.fft(kernel)[:, None, None], axis=0)
    one = smooth[np.arange(size//2+1)*(n//size)].copy(); one[1:-1] *= 2
    hz = np.fft.rfftfreq(size, 1/48000)
    return np.array([one[(hz >= low) & (hz < high)].sum(axis=0)*48000/size for low, high in bands])


def pack(matrices):
    return np.column_stack([matrices[:, 0, 0].real, matrices[:, 1, 1].real,
                            matrices[:, 1, 0].real, matrices[:, 1, 0].imag])


def export(path, models, base):
    lines = [f'VSL_STEREO_RESONANCE 1 48000 {len(models)} 96000 {base:.17g}']
    for m in models:
        a = np.array(m['a']); sos = np.array(m['sos'])
        lines.append(f'{len(a)} {len(sos)} {m["band_hz"][0]} {m["band_hz"][1]} {m["gain"]:.17g}')
        for value in (a, np.array(m['noise']), sos, np.array(m['certificate'])):
            lines.append(' '.join(f'{v:.17g}' for v in value.ravel()))
    path.write_text('\n'.join(lines)+'\n', encoding='ascii')
