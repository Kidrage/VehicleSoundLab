"""Analytic spectra and an exactly ambiguous AM/long-period construction."""
import numpy as np


def cases(cycle=1024, root=33.0):
    at = np.arange(96*cycle)/cycle
    carriers = np.array([2, 3, 5, 7, 15])
    amplitudes = np.array([.4, .3, .9, .25, .15])
    phase = np.array([.4, 1.1, -.2, .6, -.7])

    def tones(orders, amp, offsets):
        return np.column_stack([sum(a*np.sin(2*np.pi*order*(at-root*delay)+p)
            for order, a, p in zip(orders, amp, offsets)) for delay in (0., .0007)])

    integer = tones(carriers, amplitudes, phase)
    fifth = np.sort(np.r_[carriers, carriers-.2, carriers+.2])
    seventh = np.sort(np.r_[carriers, carriers-1/7, carriers+1/7])
    # sin(A)cos(B) = (sin(A+B)+sin(A-B))/2. Different source
    # descriptions are sample-identical; spectrum cannot choose one causally.
    am = np.column_stack([sum(a*np.sin(2*np.pi*order*(at-root*delay)+p) *
        (1+.6*np.cos(2*np.pi*.2*(at-root*delay))) for order, a, p in zip(carriers, amplitudes, phase))
        for delay in (0., .0007)])
    long_period = tones(np.r_[carriers, carriers-.2, carriers+.2],
        np.r_[amplitudes, amplitudes*.3, amplitudes*.3], np.r_[phase, phase, phase])
    rng = np.random.default_rng(62017)
    return [dict(id='integer_delayed_stereo', audio=integer, expected=carriers),
        dict(id='fifth_grid', audio=tones(fifth, np.full(len(fifth), .25), np.zeros(len(fifth))), expected=fifth),
        dict(id='seventh_grid', audio=tones(seventh, np.full(len(seventh), .25), np.zeros(len(seventh))), expected=seventh),
        dict(id='am_sidebands', audio=am, expected=fifth),
        dict(id='same_samples_long_period_description', audio=long_period, expected=fifth),
        dict(id='noise_only', audio=rng.standard_normal((len(at), 2))*.2, expected=None)], float(abs(am-long_period).max())
