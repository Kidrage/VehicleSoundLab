"""Finite-window stereo power matrices; no source separation or waveform fitting."""
import numpy as np


def frames(audio, spec):
    n, hop = spec['window_samples'], spec['hop_samples']
    starts = np.arange(0, len(audio)-n+1, hop)
    assert len(starts) and audio.ndim == 2 and audio.shape[1] == 2
    return starts, audio[starts[:, None]+np.arange(n)]


def density(audio, spec):
    starts, parts = frames(audio, spec)
    n, size, rate = spec['window_samples'], spec['fft_samples'], spec['rate']
    window = .5-.5*np.cos(2*np.pi*np.arange(n)/n)
    ft = np.fft.rfft(parts*window[None, :, None], n=size, axis=1)
    factor = np.full(size//2+1, 2/(rate*np.dot(window, window)))
    factor[[0, -1]] *= .5
    matrix = np.einsum('wfc,wfd->fcd', ft, ft.conj())/len(starts)*factor[:, None, None]
    hz = np.arange(len(matrix))*rate/size
    return hz, matrix, ft


def matrices(audio, spec):
    hz, power, _ = density(audio, spec)
    step = spec['rate']/spec['fft_samples']
    return np.array([power[(hz >= lo)&(hz < hi)].sum(axis=0)*step for lo, hi in spec['bands_hz']])


def describe(matrix):
    diagonal = matrix.diagonal(axis1=-2, axis2=-1).real
    scale = np.sqrt(np.maximum(diagonal[:, 0]*diagonal[:, 1], 1e-60))
    rho = matrix[:, 0, 1]/scale
    mid = (diagonal.sum(axis=1)+2*matrix[:, 0, 1].real)/4
    side = (diagonal.sum(axis=1)-2*matrix[:, 0, 1].real)/4
    return dict(power_LR=diagonal.tolist(),
                cross_L_conjR=np.column_stack((matrix[:, 0, 1].real, matrix[:, 0, 1].imag)).tolist(),
                complex_correlation=np.column_stack((rho.real, rho.imag)).tolist(),
                side_mid_db=(10*np.log10(np.maximum(side, 1e-30)/np.maximum(mid, 1e-30))).tolist(),
                side_mid_floor_applied=((side <= 1e-30)|(mid <= 1e-30)).tolist())


def compare(reference, generated):
    delta = reference-generated
    eigen = np.linalg.eigvalsh(delta)
    p = generated.diagonal(axis1=-2, axis2=-1).real
    q = reference.diagonal(axis1=-2, axis2=-1).real
    return dict(C_minus_native_power_db=(10*np.log10(np.maximum(p, 1e-30)/np.maximum(q, 1e-30))).tolist(),
                debt_eigenvalues=eigen.tolist(),
                debt_positive_definite=(eigen[:, 0] > 0).tolist(),
                diagonal_debt_positive=np.all((q-p) > 0, axis=1).tolist(),
                debt_matrix_real=delta.real.tolist(),
                debt_matrix_imag=delta.imag.tolist())


def known(spec):
    t = np.arange(8192)
    phase = 2*np.pi*512*t/4096
    delay = 2*np.pi*512*3/4096
    full = dict(spec, bands_hz=[[0, 24000.001]])
    controls = [
        ('mono', np.column_stack((.2*np.cos(phase), .2*np.cos(phase))), np.array([[.02, .02], [.02, .02]], complex)),
        ('asymmetric', np.column_stack((.2*np.cos(phase), .1*np.cos(phase))), np.array([[.02, .01], [.01, .005]], complex)),
        ('quadrature', np.column_stack((.2*np.cos(phase), .2*np.sin(phase))), np.array([[.02, .02j], [-.02j, .02]], complex)),
        ('delay', np.column_stack((.2*np.cos(phase), .2*np.cos(phase-delay))),
         np.array([[.02, .02*np.exp(1j*delay)], [.02*np.exp(-1j*delay), .02]], complex))]
    result = []
    for name, audio, expected in controls:
        actual = matrices(audio, full)[0]
        error = float(np.max(abs(actual-expected)))
        phase_error = float(abs(np.angle(actual[0, 1]/expected[0, 1])))
        assert error <= 1e-12 and phase_error <= 1e-10
        result.append(dict(name=name, matrix_error_FS2=error,
                           cross_phase_error_radians=phase_error))
    indefinite = np.array([[[1., 2.], [2., 1.]]])
    positive = np.array([[[1., .2], [.2, 1.]]])
    assert compare(indefinite+3*np.eye(2), 3*np.eye(2)[None])['debt_positive_definite'] == [False]
    assert compare(positive+3*np.eye(2), 3*np.eye(2)[None])['debt_positive_definite'] == [True]
    assert np.all(indefinite.diagonal(axis1=-2, axis2=-1) > 0)
    return result
