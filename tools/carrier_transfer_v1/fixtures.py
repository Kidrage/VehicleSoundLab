"""Tagged analytic components, including deliberate cross-group cancellation."""
import numpy as np
from scipy.special import jv


def generate(kind, frames=16384):
    n = np.arange(frames)
    groups = np.zeros((frames, 6, 2))
    tones = []
    def add(tag, channel, order, coefficient):
        groups[:, tag, channel] += np.real(coefficient*np.exp(2j*np.pi*n*order/1024))
        tones.append([tag, channel, float(order), float(coefficient.real), float(coefficient.imag)])
    if kind == 'separated':
        for tag, order in enumerate([17, 64, 112, 144, 208, 260]):
            for channel in (0, 1):
                add(tag, channel, order, (.02+.003*tag)*np.exp(1j*(.2*tag-.3*channel)))
    elif kind in ('positive_cross', 'negative_cross', 'quadrature'):
        shift = {'positive_cross':0., 'negative_cross':np.pi, 'quadrature':np.pi/2}[kind]
        for channel in (0, 1):
            add(0, channel, 64, .04*np.exp(-.3j*channel))
            add(1, channel, 64, .032*np.exp(1j*(shift+.2*channel)))
    elif kind == 'low_AM_sidebands':
        for channel in (0, 1):
            amplitude = .04*np.exp(-.2j*channel)
            add(0, channel, 17, amplitude)
            add(0, channel, 117, .15*amplitude)
            add(0, channel, -83, .15*amplitude)
    elif kind == 'low_PM_sidebands':
        # Bessel sum declares the oracle; actual samples use direct PM.
        for channel in (0, 1):
            phase = -.2*channel
            groups[:, 0, channel] = .04*np.cos(2*np.pi*n*17/1024+phase+.4*np.sin(2*np.pi*n*100/1024))
            for m in range(-12, 13):
                z = .04*np.exp(1j*phase)*jv(m, .4)
                tones.append([0, channel, float(17+100*m), float(z.real), float(z.imag)])
    elif kind == 'edge_bins':
        for channel in (0, 1):
            add(0, channel, 0, .01*(1+channel)+0j)
            add(5, channel, 512, .02*(1+channel)+0j)
    elif kind != 'silence':
        raise ValueError(kind)
    return groups, dict(tones=np.asarray(tones).reshape(-1, 5), root_hz=64.)
