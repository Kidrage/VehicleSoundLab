"""Scalar-carrier audit of the full composite system; no production fitter import."""
import numpy as np
from scipy import linalg
from observer_complete_v1.audit_oracle import full_frame, hats, curvature
from observer_frequency_v1.audit_oracle import frame_adjoint
from observer_frequency_v1.reduced_oracle import synthesize, adjoint, carrier_table
from .audit_oracle import metric


def vec(q):
    return np.r_[q.real.ravel(), q.imag.ravel()]


class FullOracle:
    def __init__(self, audio, positions, orders, scale):
        self.audio, self.positions, self.orders, self.scale = audio, positions, orders, scale
        self.shape = (len(positions), len(orders), audio.shape[1])
        self.profile = metric(audio, 64.)
        self.D = curvature(positions)
        self.R = .001*self.D.T@self.D + .000001*np.eye(len(positions))
        self.wave_size = audio.size
        self.row_shape = self.profile['rows'].shape
        self.data_size = self.wave_size + 2*int(np.prod(self.row_shape))

    def nodes(self, x):
        size = int(np.prod(self.shape))
        return x[:size].reshape(self.shape) + 1j*x[size:].reshape(self.shape)

    def spectral(self, wave):
        rows, _ = full_frame(wave)
        return rows[self.profile['keep']]*self.profile['amplitude']*self.profile['weights'][None, :, None]

    def spectral_adjoint(self, rows):
        full = np.zeros((len(self.profile['keep']), 2049, self.shape[-1]), complex)
        full[self.profile['keep']] = rows*self.profile['weights'][None, :, None]*self.profile['amplitude']
        return frame_adjoint(full, self.profile['full_coverage'], len(self.audio))

    def data_forward(self, x):
        wave = synthesize(self.nodes(x)*self.scale[None], self.positions, self.orders, len(self.audio))
        return np.r_[wave.ravel()/self.profile['sigma'], vec(self.spectral(wave))]

    def data_adjoint(self, y):
        wave = y[:self.wave_size].reshape(self.audio.shape)/self.profile['sigma']
        part = y[self.wave_size:]
        size = int(np.prod(self.row_shape))
        rows = part[:size].reshape(self.row_shape) + 1j*part[size:].reshape(self.row_shape)
        wave = wave + self.spectral_adjoint(rows)
        return vec(adjoint(wave, self.positions, self.orders)*self.scale[None])

    def forward(self, x):
        q = self.nodes(x)
        d = (self.D@q.reshape(len(q), -1)).reshape((len(q)-2,)+q.shape[1:])
        return np.r_[self.data_forward(x), np.sqrt(.001)*vec(d), .001*x]

    def backward(self, y):
        out = self.nodes(self.data_adjoint(y[:self.data_size]))
        n = int(np.prod((len(self.positions)-2,)+self.shape[1:]))
        rest = y[self.data_size:]
        d = rest[:n].reshape((len(self.positions)-2,)+self.shape[1:]) + 1j*rest[n:2*n].reshape((len(self.positions)-2,)+self.shape[1:])
        out += np.sqrt(.001)*(self.D.T@d.reshape(len(d), -1)).reshape(self.shape)
        return vec(out) + .001*rest[2*n:]

    def target(self):
        return np.r_[self.audio.ravel()/self.profile['sigma'], vec(self.profile['rows']*self.profile['weights'][None, :, None])]

    def penalty(self, q):
        d = self.D@q.reshape(len(q), -1)
        return float(.001*np.sum(abs(d)**2) + .000001*np.sum(abs(q)**2))

    def direct_blocks(self):
        """Direct carrier quadrature on nonzero hat pairs, without cyclic FFTs."""
        M, H, _ = self.shape
        basis = hats(self.positions, len(self.audio))
        table = carrier_table(tuple(int(k) for k in self.orders))[np.arange(len(self.audio)) % 1024]
        result = np.repeat(linalg.block_diag(self.R, self.R)[None], H, axis=0)
        weights = self.profile['weights'][4*self.orders]**2
        for i in range(M):
            for j in range(i, min(M, i+2)):
                product = basis[i]*basis[j]
                selected = product != 0
                c, s = table[selected].real, -table[selected].imag
                coverage = self.scale[:, 0]**2 * (1/self.profile['sigma']**2 +
                    self.profile['time_coverage'][selected, None]*weights[None])
                w = product[selected, None]*coverage
                cc, ss, cs = (np.sum(w*t, axis=0) for t in (c*c, s*s, c*s))
                for left, right, values in ((i, j, cc), (M+i, M+j, ss), (i, M+j, cs), (j, M+i, cs)):
                    result[:, left, right] += values
                    if left != right:
                        result[:, right, left] += values
                # For i==j the real/imag block was enumerated twice above.
                if i == j:
                    result[:, i, M+i] -= cs
                    result[:, M+i, i] -= cs
        return np.array([linalg.solve_triangular(np.linalg.cholesky(K).T, np.eye(2*M), lower=False) for K in result])

    def gap(self, x, t):
        q = self.nodes(x)
        y = self.target()
        e = self.data_forward(x)-y
        p = self.nodes(self.data_adjoint(e))
        inverse = linalg.solve(self.R, p.reshape(len(q), -1), assume_a='pos').reshape(q.shape)
        primal = float(e@e) + self.penalty(q)
        dual = float(-t*t*(e@e + np.vdot(p, inverse).real) - 2*t*(y@e))
        gap = float((1-t)**2*(e@e)) + self.penalty(q+t*inverse)
        return dict(primal=primal, dual_lower_bound=dual, gap_upper_bound=gap)
