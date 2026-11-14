"""Known deceleration and boundary controls, run before reading the real source."""
import numpy as np
from exterior_clock_v1.warp import carrier_rows
from .aperture import extract


def run(plan):
    rate = 48000
    times = np.arange(5*rate)/rate
    roots = 64*np.exp(-.08*times)
    cycles = np.r_[0., np.cumsum((roots[1:]+roots[:-1])/(2*rate))]
    audio = np.zeros((len(times), 2))
    for order, amplitude in [(3, .04), (5, .15), (7, .03), (10, .08), (15, .025)]:
        for channel in range(2):
            audio[:, channel] += amplitude*(1-.2*channel)*np.cos(
                2*np.pi*order*cycles+.13*order+.35*channel)
    grid = np.arange(.2, 4.801, .005)
    clock = [dict(seconds=float(t), root_hz=float(64*np.exp(-.08*t)*1.008)) for t in grid]
    results = []
    for center in (1.5, 3.5):
        normalized, where, info = extract(audio, 0, clock, center, plan)
        native_cycles = np.interp(where, times, cycles)
        error = float(np.std(native_cycles-np.arange(len(where))/1024))
        assert error < plan['gates']['known_phase_cycle_std'], error
        assert min(v for row in info['heldout_coherence'].values() for v in row) > .99
        maximum_lr_phase = 0.
        for order in (3, 5, 7, 10, 15):
            _, rows = carrier_rows(normalized, order)
            delta = np.angle(np.exp(1j*(np.angle(rows[:, 1]/rows[:, 0])-.35)))
            maximum_lr_phase = max(maximum_lr_phase, float(abs(delta).max()))
        assert maximum_lr_phase < .002
        results.append(dict(center_seconds=center, phase_cycle_std=error,
                            maximum_LR_phase_error_radians=maximum_lr_phase, extraction=info))
    rejected = []
    for center in (.19, .21, 4.79, 4.81):
        try:
            extract(audio, 0, clock, center, plan)
        except ValueError as exc:
            rejected.append(dict(center_seconds=center, reason=str(exc)))
        else:
            raise AssertionError('A boundary aperture unexpectedly extrapolated')
    return dict(result='pass', known_decelerations=results, rejected_boundaries=rejected,
                scope='Known finite tests of aperture/correction only, not real-source phase qualification')
