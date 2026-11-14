"""Declared exact mixtures; deterministic sidebands are not mechanical noise."""
import numpy as np
from .projection import inverse_phase


def fixtures(settings):
    n, rate, root = [settings[k] for k in ['frames', 'rate', 'root_hz']]
    time = np.arange(n)/rate
    phase = root*time

    def tones(p, mono=False):
        left = sum(a*np.cos(2*np.pi*k*p+.13*k) for k, a in [(5, .12), (127, .035), (201, .02)])
        right = left.copy() if mono else sum(.7*a*np.cos(2*np.pi*k*p+.13*k+.4) for k, a in [(5, .12), (127, .035), (201, .02)])
        return np.column_stack([left, right])

    h = tones(phase)
    empty = np.zeros_like(h)
    inter = np.column_stack([
        .04*np.cos(2*np.pi*60.5*phase+.2)+.03*np.sin(2*np.pi*170.5*phase+.1),
        .025*np.cos(2*np.pi*60.5*phase+.7)+.035*np.sin(2*np.pi*170.5*phase-.1)])
    cases = [dict(name='zero', phase=phase, full=empty, truth_H=empty, truth_R=empty),
             dict(name='mono', phase=phase, full=tones(phase, True), truth_H=tones(phase, True), truth_R=empty),
             dict(name='asymmetric_phase', phase=phase, full=h, truth_H=h, truth_R=empty),
             dict(name='interharmonic', phase=phase, full=inter, truth_H=empty, truth_R=inter),
             dict(name='mixed_half_order', phase=phase, full=h+inter, truth_H=h, truth_R=inter)]
    carrier = np.column_stack([.13*np.cos(2*np.pi*127*phase+.1), .09*np.cos(2*np.pi*127*phase+.5)])
    sideband = .4*np.cos(np.pi*phase)[:, None]*carrier
    cases.append(dict(name='deterministic_AM', phase=phase, full=carrier+sideband,
                      truth_H=carrier, truth_R=sideband))
    analytic_phase = 60*time+7.5*time*time
    grid = np.arange(int(np.ceil(analytic_phase[-1]*1024))+1)/1024
    # Stable positive inverse of60t+7.5t^2, independent of interpolation.
    positions = 2*grid/(60+np.sqrt(3600+30*grid))
    observed = inverse_phase(positions, 0, 0, n, rate)
    cases.append(dict(name='rising_inverse_clock', phase=observed, full=tones(analytic_phase),
                      truth_H=tones(analytic_phase), truth_R=empty,
                      exact_analytic_phase=analytic_phase, source_seconds=positions))
    for seed in settings['seeds']:
        rng = np.random.default_rng(seed)
        normal = rng.standard_normal((n, 2))
        noise = .035*np.column_stack([normal[:, 0], .6*normal[:, 0]+.8*normal[:, 1]])
        cases.append(dict(name='white_mix_'+str(seed), phase=phase, full=h+noise,
                          noise=noise, deterministic_H=h))
    return cases
