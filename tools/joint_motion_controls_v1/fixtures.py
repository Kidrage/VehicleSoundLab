"""Known stable, boundary-crossing and dense harmonics with explicit AM truth."""
import numpy as np


def render(plan, family, motion, modulation):
    cfg = plan['known']
    rate = 48000
    t = np.arange(round(rate*cfg['seconds']))/rate
    if family == 'zero':
        return np.zeros((len(t), 2))
    if family == 'dense':
        h = np.arange(1, cfg['dense_harmonics']+1)
        initial = cfg['dense_root_rise_start'] if motion == 'rising' else cfg['dense_root_static']
        slope = (cfg['dense_root_rise_stop']-initial)/cfg['seconds'] if motion == 'rising' else 0
        frequencies = initial*h
        slopes = slope*h
        phase = .13*h+.013*h*h
        amplitudes = np.column_stack([.12/h**.75, .12/h**.75*.7*(1+.15*np.sin(.37*h))])
        offsets = np.column_stack([phase, phase+.2*np.sin(.23*h)])
        reference = cfg['dense_root_static']*h
    else:
        frequencies = np.array(cfg['safe_hz'], float)
        slopes = np.full(4, 100. if motion == 'rising' else 0.)
        amplitude = np.array(cfg['safe_amplitude'])
        phase = np.array([.2, -.4, .65, -.8])
        if family == 'edge':
            frequencies = np.r_[frequencies, cfg['edge_hz']]
            slopes = np.r_[np.zeros(4), np.full(4, cfg['edge_rise_hz_per_s'] if motion == 'rising' else 0.)]
            amplitude = np.r_[amplitude, np.full(4, cfg['edge_amplitude'])]
            phase = np.r_[phase, [.3, -.7, .9, -.2]]
        amplitudes = np.column_stack([amplitude, .7*amplitude])
        offsets = np.column_stack([np.zeros(len(phase)), phase])
        reference = frequencies
    groups = np.clip(np.searchsorted([6000, 8000, 10000], reference, side='right'), 0, 3)
    out = np.zeros((len(t), 2))
    # Bound temporary arrays while preserving deterministic partial order.
    for j, (frequency, slope, g) in enumerate(zip(frequencies, slopes, groups)):
        angle = 2*np.pi*(frequency*t+.5*slope*t*t)
        for c in range(2):
            if modulation == 'common':
                envelope = 1+.4*np.cos(2*np.pi*4*t)
            elif modulation == 'differential':
                envelope = 1+(.25*np.cos(2*np.pi*(2+g)*t+.3*g) if c == 0 else .2*np.sin(2*np.pi*(3+g)*t+.5*g))
            else:
                envelope = 1
            out[:, c] += amplitudes[j, c]*envelope*np.cos(angle+offsets[j, c])
    return out


def cases(plan):
    yield dict(label='known_zero', family='zero', motion='static', modulation='none')
    for family in plan['known']['families']:
        for motion in plan['known']['motion']:
            for modulation in plan['known']['modulation']:
                yield dict(label=f'known_{family}_{motion}_{modulation}', family=family, motion=motion, modulation=modulation)
