"""Complete all-bin basis matrix/QR for known captures only, never real fits."""
import numpy as np
from scipy import linalg
from observer_complete_v1.audit_oracle import hats
from observer_frequency_v1.reduced_oracle import carrier_table
from waveform_file_real_v1.audit_oracle import qr_solve


def matrix(oracle):
    N, C = oracle.audio.shape; M, H, _ = oracle.shape
    n = 2*M*H
    if n > 512 or C != 2:
        raise ValueError('Complete known-only basis matrix; no real-source dense fitting')
    basis = hats(oracle.positions, N)
    carriers = carrier_table(tuple(int(k) for k in oracle.orders))[np.arange(N)%1024]
    phi = np.empty((N, n))
    for m in range(M):
        for h in range(H):
            j = m*H+h
            phi[:, j] = basis[m]*carriers[:, h].real*oracle.scale[h, 0]
            phi[:, M*H+j] = -basis[m]*carriers[:, h].imag*oracle.scale[h, 0]
    normalizer = 1/np.sqrt(oracle.profile['full_coverage'])
    window = .5-.5*np.cos(2*np.pi*np.arange(4096)/4096)
    endpoint = np.r_[1., np.full(2047, np.sqrt(2.)), 1.]
    rows = []
    for first in range(0, N-4096+1, 256):
        segment = phi[first:first+4096]*normalizer[first:first+4096, None]
        segment = segment*window[:, None]
        rows.append(np.fft.rfft(segment, axis=0)*endpoint[:, None]/64)
    rows = np.asarray(rows)*oracle.profile['amplitude']*oracle.profile['weights'][None, :, None]
    B = np.vstack((phi/oracle.profile['sigma'], rows.real.reshape(-1, n), rows.imag.reshape(-1, n)))
    tail = np.vstack((np.sqrt(.001)*linalg.block_diag(np.kron(oracle.D, np.eye(H)), np.kron(oracle.D, np.eye(H))), .001*np.eye(n)))
    return B, tail, oracle.target().reshape(-1, 2)


def solve(B, tail, target):
    return qr_solve(B, tail, target)
