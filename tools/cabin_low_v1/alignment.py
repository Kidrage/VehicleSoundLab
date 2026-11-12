"""Stereo waveform alignment with an explicit ambiguity rejection."""
import numpy as np
from scipy import signal


def locate(template, search, rate):
    x = np.asarray(template, dtype=float)
    y = np.asarray(search, dtype=float)
    assert x.ndim == y.ndim == 1 and len(y) >= len(x)
    x = x-x.mean()
    n = len(x)
    cumulative = np.r_[0.,np.cumsum(y)]
    squared = np.r_[0.,np.cumsum(y*y)]
    variance = squared[n:]-squared[:-n]-(cumulative[n:]-cumulative[:-n])**2/n
    denominator = np.sqrt(np.maximum(np.dot(x,x)*variance,1e-60))
    scores = signal.correlate(y,x,mode='valid',method='fft')/denominator
    best = int(np.argmax(scores))
    others = scores.copy()
    exclusion = round(.005*rate)
    others[max(0,best-exclusion):min(len(scores),best+exclusion+1)] = -np.inf
    second = float(others.max()) if np.isfinite(others).any() else -1.
    return dict(start_sample=best, ncc=float(scores[best]),
        second_peak_outside_5ms=second, peak_margin=float(scores[best]-second))


def controls():
    # Known nonperiodic signal + attenuation/DC/noise; expected insertion index
    # is supplied by construction, independently of the correlation formula.
    rng = np.random.default_rng(921763)
    rate=2000; template=rng.normal(size=1600)
    search=rng.normal(scale=.01,size=2400)
    search[271:1871] += .23*template+2.4
    measured=locate(template,search,rate)
    assert measured['start_sample']==271 and measured['ncc']>.99
    # A periodic tone can correlate very well at many offsets. Its high NCC
    # must not establish unique synchronization.
    tone=np.sin(2*np.pi*np.arange(1600)/40)
    repeated=np.sin(2*np.pi*(np.arange(2400)-113)/40)
    ambiguous=locate(tone,repeated,rate)
    assert ambiguous['ncc']>.99 and ambiguous['peak_margin']<.02
    return dict(known_insertion=measured, periodic_ambiguity=ambiguous,
        known_insertion_pass=True, periodic_signal_rejected=True)
