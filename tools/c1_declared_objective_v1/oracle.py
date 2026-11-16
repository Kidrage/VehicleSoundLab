"""Full independent scalar OSC equations using one declared rounded frame law."""
import numpy as np
from locked_source_guard_v1.measurement import frame
from observer_complete_v1.audit_oracle import curvature
from observer_supported_v1.full_oracle import FullOracle
from .profile import prepare


def frame_adjoint(rows, coverage, frames):
    endpoint = np.r_[1., np.full(2047, np.sqrt(2.)), 1.]
    window = .5-.5*np.cos(2*np.pi*np.arange(4096)/4096)
    normalizer = 1/np.sqrt(coverage)
    output = np.zeros((frames, 2))
    for j, first in enumerate(range(-3840, frames, 256)):
        lo, hi = max(0, first), min(frames, first+4096)
        offset = np.arange(lo-first, hi-first)
        for c in (0, 1):
            samples = np.fft.irfft(rows[j, :, c]/endpoint, n=4096)*64
            output[lo:hi, c] += samples[offset]*window[offset]*normalizer[lo:hi]
    return output


class DeclaredOracle(FullOracle):
    def spectral(self, wave):
        rows, _ = frame(wave)
        return rows[self.profile['keep']]*self.profile['amplitude']*self.profile['weights'][None, :, None]

    def spectral_adjoint(self, rows):
        full = np.zeros((len(self.profile['keep']), 2049, 2), complex)
        full[self.profile['keep']] = rows*self.profile['amplitude']*self.profile['weights'][None, :, None]
        return frame_adjoint(full, self.profile['full_coverage'], len(self.audio))


def make(d, check):
    profile, old = prepare(d, check)
    result = object.__new__(DeclaredOracle)
    result.audio, result.positions, result.orders, result.scale = d['audio'], d['positions'], d['orders'], d['scale']
    result.shape = (len(d['positions']), len(d['orders']), 2)
    result.profile = profile
    result.D = curvature(d['positions'])
    result.R = .001*result.D.T@result.D+.000001*np.eye(len(d['positions']))
    result.wave_size = d['audio'].size
    result.row_shape = profile['rows'].shape
    result.data_size = d['audio'].size+2*int(np.prod(result.row_shape))
    return result, old
