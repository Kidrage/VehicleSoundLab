"""Independent explicit bases and SciPy frame formulas, without fitter imports."""
import numpy as np
from scipy import linalg
from observer_complete_v1.audit_oracle import full_frame, hats, curvature, synthesize, wave_adjoint


def metric(audio, root):
    rows, cover = full_frame(audio)
    frequencies = np.arange(2049)*root/4
    boundaries = (0., 3000., 6000., 8000., 10000., 14000., np.inf)
    ids = np.zeros(2049, int); power = []
    for j, (low, high) in enumerate(zip(boundaries[:-1], boundaries[1:])):
        keep = (frequencies >= low) & (frequencies < high)
        ids[keep] = j
        power.append(float(np.sum(rows[:, keep].real**2+rows[:, keep].imag**2)/audio.size))
    power = np.array(power)
    total = float(np.mean(audio**2))
    weights = np.array([1/np.sqrt(max(power[b], total*1e-8)) for b in ids]) if total else np.ones(2049)
    return rows, cover, weights, power, ids


def frame_adjoint(rows, coverage, frames):
    weights = np.r_[1., np.full(2047, np.sqrt(2.)), 1.]
    result = np.zeros((frames, rows.shape[-1]))
    for j, start in enumerate(range(-3840, frames, 256)):
        half = rows[j]/weights[:, None]
        full = np.concatenate((half, half[-2:0:-1].conj()), axis=0)
        full[[0, 2048]] = full[[0, 2048]].real
        wave = np.fft.ifft(full, axis=0).real*64
        first, last = max(start, 0), min(start+4096, frames)
        offsets = np.arange(first-start, last-start)
        window = .5-.5*np.cos(2*np.pi*offsets/4096)
        result[first:last] += wave[offsets]*window[:, None]/np.sqrt(coverage[first:last, None])
    return result


def matrices(positions, orders, scale, audio, weights, sigma):
    N, C = audio.shape; M, H = len(positions), len(orders)
    size = M*H*C
    basis = hats(positions, N)
    phase = 2*np.pi*np.arange(N)[:, None]*orders[None]/1024
    Phi = np.zeros((N*C, 2*size))
    for m in range(M):
        for h in range(H):
            for c in range(C):
                j = (m*H+h)*C+c
                Phi[c::C, j] = basis[m]*np.cos(phase[:, h])*scale[h, 0]
                Phi[c::C, size+j] = -basis[m]*np.sin(phase[:, h])*scale[h, 0]
    D = curvature(positions)
    reg = np.sqrt(.001)*linalg.block_diag(np.kron(D, np.eye(H*C)), np.kron(D, np.eye(H*C)))
    tail = np.vstack((reg, np.sqrt(.000001)*np.eye(2*size)))
    # Fixture is mono, so each explicit waveform column can be a SciPy channel.
    assert C == 1
    frame, cover = full_frame(Phi)
    z = frame*weights[None, :, None]
    data = np.vstack((z.real.reshape(-1, 2*size), z.imag.reshape(-1, 2*size)))
    target, _ = full_frame(audio)
    target *= weights[None, :, None]
    weighted = (np.vstack((data, tail)), np.r_[target.real.ravel(), target.imag.ravel(), np.zeros(len(tail))])
    complete = (np.vstack((Phi/sigma, tail)), np.r_[audio.ravel()/sigma, np.zeros(len(tail))])
    # Explicit original finite-window demodulation, not the synthesis observer.
    n = np.arange(4096); w = .5-.5*np.cos(2*np.pi*n/4096)
    rows, targets = [], []
    for start in range(0, N-4096+1, 256):
        carrier = np.exp(-2j*np.pi*(start+n)[:, None]*orders[None]/1024)
        rows.append((2/w.sum())*(carrier.T@(w[:, None]*Phi[start:start+4096])))
        targets.append((2/w.sum())*(carrier.T@(w[:, None]*audio[start:start+4096])))
    y = np.array(rows)/scale[None]
    b = np.array(targets)/scale[None]
    old = (np.vstack((y.real.reshape(-1, 2*size), y.imag.reshape(-1, 2*size), tail)),
           np.r_[b.real.ravel(), b.imag.ravel(), np.zeros(len(tail))])
    return dict(old_harmonic=old, global_wave=complete, weighted_frame=weighted), Phi, D


def objective_gradient(nodes, positions, scale, reference, weights):
    orders = np.arange(1, nodes.shape[1]+1)
    audio = synthesize(nodes, positions, orders, len(reference))
    rows, cover = full_frame(audio-reference)
    origin, _ = full_frame(reference)
    weighted = rows*weights[None, :, None]
    wave_gradient = frame_adjoint(rows*weights[None, :, None]**2, cover, len(reference))
    first_gradient = frame_adjoint(origin*weights[None, :, None]**2, cover, len(reference))
    q = nodes/scale[None]; D = curvature(positions)
    d = (D@q.reshape(len(q), -1)).reshape((len(D),)+q.shape[1:])
    g = wave_adjoint(wave_gradient, positions, orders)*scale[None]
    g += .001*(D.T@d.reshape(len(d), -1)).reshape(q.shape)+.000001*q
    first = wave_adjoint(first_gradient, positions, orders)*scale[None]
    value = float(np.sum(abs(weighted)**2)+.001*np.sum(abs(d)**2)+.000001*np.sum(abs(q)**2))
    return value, float(np.linalg.norm(g)/max(np.linalg.norm(first), 1e-24))
