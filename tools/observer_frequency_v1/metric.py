"""Positive, bounded, shared-L/R weights on a complete finite Hann frame."""
import numpy as np
from observer_complete_v1.frame import CompleteHann

EDGES = (0., 3000., 6000., 8000., 10000., 14000.)
FLOOR_FRACTION = 1e-8  # Mathematical conditioning floor, not measured noise.


class FrequencyMetric:
    def __init__(self, audio, root_hz, floor_fraction=FLOOR_FRACTION):
        audio = np.asarray(audio)
        if audio.ndim != 2 or audio.shape[1] not in (1, 2):
            raise ValueError('Invalid audio dimensions')
        if not np.isfinite([root_hz, floor_fraction]).all() or root_hz <= 0 or not 0 < floor_fraction <= 1:
            raise ValueError('Invalid frequency scale/floor')
        self.frame = CompleteHann(len(audio), audio.shape[1])
        rows = self.frame.forward(audio)
        frequencies = np.arange(self.frame.size//2+1)*1024*root_hz/self.frame.size
        self.bands = np.searchsorted(EDGES[1:], frequencies, side='right')
        self.global_power = float(np.sum(audio**2)/audio.size)
        self.band_power = np.array([float(np.sum(abs(rows[:, self.bands == b])**2)/audio.size)
                                   for b in range(len(EDGES))])
        self.root_hz = float(root_hz)
        self.floor_fraction = float(floor_fraction)
        self.silent = self.global_power == 0
        self.weights = (np.ones(len(frequencies)) if self.silent else
            1/np.sqrt(np.maximum(self.band_power[self.bands], self.global_power*floor_fraction)))
        if not np.isfinite(self.weights).all() or np.any(self.weights <= 0):
            raise ValueError('Nonpositive or nonfinite frequency metric')
        self.shape = self.frame.shape

    def forward(self, audio):
        return self.frame.forward(audio)*self.weights[None, :, None]

    def adjoint(self, rows):
        return self.frame.adjoint(rows*self.weights[None, :, None])

    def normal(self, audio):
        return self.adjoint(self.forward(audio))
