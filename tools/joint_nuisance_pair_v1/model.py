"""Original real a/b and relative positive envelope; common phase is immutable."""
import numpy as np


class FixedClockModel:
    def __init__(self, cosine, sine, envelope_basis, bound):
        self.cosine, self.sine, self.basis = cosine, sine, envelope_basis
        self.parts, self.count = cosine.shape[1], envelope_basis.shape[1]
        self.bound = bound
        self.size = 2*self.parts+self.parts*self.count
        self.lower = np.r_[np.full(2*self.parts, -1.), np.full(self.parts*self.count, -bound)]
        self.upper = -self.lower

    def samples(self, x, derivative=False):
        n = self.parts
        envelope = 1+self.basis@x[2*n:].reshape(n, self.count).T
        carrier = self.cosine*x[:n]+self.sine*x[n:2*n]
        values = np.sum(envelope*carrier, axis=1)
        if not derivative:
            return values
        amplitude = (carrier[:, :, None]*self.basis[:, None, :]).reshape(len(values), -1)
        return values, np.column_stack((envelope*self.cosine, envelope*self.sine, amplitude))


def from_original(model, parameters):
    m = model.original
    assert not m.selected
    start = 2*m.parts
    stop = start+m.phase_count
    phase = m.phase_basis@parameters[start:stop]
    angle = 2*np.pi*(m.time[:, None]+phase[:, None])*m.orders[None, :]
    fixed = FixedClockModel(np.cos(angle), np.sin(angle), m.envelope_basis, model.bound)
    indices = np.r_[np.arange(start), np.arange(stop, m.parameter_count)]
    assert len(indices) == fixed.size
    return fixed, parameters[indices].copy(), indices
