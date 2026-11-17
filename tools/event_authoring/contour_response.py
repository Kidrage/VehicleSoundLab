"""Exact finite-waveform quadratic responses for coarse contour controls.

Offline only: knot interpolation, modal summation and noise coloration are linear
in the knot gains when component coefficients and the random sequence are fixed.
Hann powers are therefore quadratic. No new runtime generator or audio asset.
"""
from copy import deepcopy

import numpy as np

from .model import synth


class QuadraticResponse:
    def __init__(self, profile, duration):
        self.sizes = [len(c['gain']) for c in profile['contours']]
        self.count = sum(self.sizes)
        waves = []
        for index in range(self.count):
            p = deepcopy(profile)
            offset = 0
            for contour, size in zip(p['contours'], self.sizes):
                contour['gain'] = [float(offset+k == index) for k in range(size)]
                offset += size
            waves.append(synth(p, seconds=duration))
        # Any component outside a declared contour is a constant contribution.
        p = deepcopy(profile)
        for contour in p['contours']:
            contour['gain'] = [0.]*len(contour['gain'])
        self.constant = synth(p, seconds=duration)
        self.waves = np.column_stack(waves)-self.constant[:, None]
        extended = np.column_stack((self.waves, self.constant))
        self.temporal = self._grams(extended, 240,
            ((60,300), (300,1200), (1200,4500), (4500,14000)))
        self.spectral = self._grams(extended, 1024,
            ((0,60), (60,300), (300,1200), (1200,4500), (4500,14000), (14000,24001))).mean(axis=1)

    @staticmethod
    def power(gram, gains):
        extended = np.r_[gains, 1.]
        return np.einsum('i,...ij,j->...', extended, gram, extended, optimize=True)

    @staticmethod
    def derivative(gram, gains):
        extended = np.r_[gains, 1.]
        return 2*np.einsum('...ij,j->...i', gram, extended, optimize=True)[..., :-1]

    def waveform(self, gains):
        return self.waves@np.asarray(gains)+self.constant

    @staticmethod
    def _grams(waves, hop, edges):
        size = 2048
        window = .5-.5*np.cos(2*np.pi*np.arange(size)/size)
        starts = np.arange(0, len(waves)-size+1, hop)
        frequency = np.fft.rfftfreq(size, 1/48000)
        weight = np.full(len(frequency), 2/(size*float(window@window)))
        weight[[0,-1]] *= .5
        result = np.empty((len(edges), len(starts), waves.shape[1], waves.shape[1]))
        # Bounded workspaces; exact rFFT rather than an approximate filter bank.
        for first in range(0, len(starts), 16):
            offsets = starts[first:first+16, None]+np.arange(size)[None, :]
            z = np.fft.rfft(waves[offsets]*window[None,:,None], axis=1)
            for band, (low, high) in enumerate(edges):
                selected = (frequency >= low)&(frequency < high)
                value = z[:,selected,:]*np.sqrt(weight[selected])[None,:,None]
                gram = np.swapaxes(value.real,1,2)@value.real + np.swapaxes(value.imag,1,2)@value.imag
                result[band,first:first+len(offsets)] = gram
        return result
