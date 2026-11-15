"""Analytic multitone/AM/PM controls; no vehicle chronology or fitted source."""
import numpy as np


def generate(kind, frames=16384):
    n = np.arange(frames)
    orders = np.array([17, 64, 112, 144, 208])
    amplitudes = np.array([[.025, .02], [.07, .05], [.035, .04], [.02, .025], [.012, .015]])
    phases = np.array([[.2, -.3], [.1, .7], [-.4, .2], [.6, -.6], [.2, .9]])
    audio = np.zeros((frames, 2))
    for j, order in enumerate(orders):
        carrier = 2*np.pi*(n % 1024)*order/1024
        modulation = 2*np.pi*n/(7*1024)
        for channel in (0, 1):
            gain = 1.
            angle = carrier+phases[j, channel]
            if j == 1 and kind in ('common_AM', 'differential_AM'):
                sign = 1 if kind == 'common_AM' or channel == 0 else -1
                gain = 1+sign*.3*np.cos(modulation)
            if j == 1 and kind in ('common_PM', 'relative_PM'):
                sign = 1 if kind == 'common_PM' or channel == 0 else -1
                angle = angle+sign*.4*np.sin(modulation)
            audio[:, channel] += amplitudes[j, channel]*gain*np.cos(angle)
    if kind == 'sideband':
        audio[:, 0] += .013*np.cos(2*np.pi*n*(64+1/7)/1024+.3)
        audio[:, 1] += .017*np.cos(2*np.pi*n*(64-1/7)/1024-.2)
    if kind == 'silence':
        audio[:] = 0
    return audio, dict(kind=kind, orders=orders, amplitudes=amplitudes, phases=phases,
                       root_hz=64., modulation_cycles_per_cycle=1/7, modulation_depth=.3, PM_depth=.4)
