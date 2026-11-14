"""Conditional harmonic projection of untouched native samples, not source identity."""
import numpy as np
from scipy import linalg


def inverse_phase(source_seconds, registered_start, first_frame, count, rate=48000):
    positions = np.asarray(source_seconds)
    if positions.ndim != 1 or len(positions) < 2 or not np.isfinite(positions).all() or np.any(np.diff(positions) <= 0):
        raise ValueError('Finite strictly increasing observed coordinates required')
    times = registered_start+(first_frame+np.arange(count))/rate
    if times[0] < positions[0] or times[-1] > positions[-1]:
        raise ValueError('Native samples leave observed coordinate support')
    return np.interp(times, positions, np.arange(len(positions))/1024)


class Projector:
    def __init__(self, phase, harmonics=288, minimum_diagonal=.1):
        self.phase = np.asarray(phase)
        if self.phase.ndim != 1 or len(self.phase) <= 1+2*harmonics or not np.isfinite(self.phase).all():
            raise ValueError('Insufficient finite phase support')
        angle = 2*np.pi*self.phase[:, None]*np.arange(1, harmonics+1)
        self.design = np.column_stack([np.ones(len(phase)), np.cos(angle), np.sin(angle)])
        self.q, self.r = linalg.qr(self.design, mode='economic')
        self.minimum_diagonal = float(abs(self.r.diagonal()).min())
        if self.minimum_diagonal < minimum_diagonal:
            raise ValueError('Conditional periodic design rank unsupported')

    def split(self, audio):
        if audio.ndim != 2 or len(audio) != len(self.phase) or not np.isfinite(audio).all():
            raise ValueError('Finite matching native frames required')
        coefficients = linalg.solve_triangular(self.r, self.q.T@audio)
        harmonic = self.design@coefficients
        remainder = audio-harmonic
        report = dict(frames=len(audio), rank=self.design.shape[1],
                      minimum_QR_diagonal=self.minimum_diagonal,
                      max_reconstruction_FS=float(abs(audio-harmonic-remainder).max()),
                      max_normal_residual_FS=float(abs(self.design.T@remainder).max()/len(audio)),
                      global_HR_FS2=(harmonic.T@remainder/len(audio)).tolist())
        return harmonic, remainder, coefficients, report
