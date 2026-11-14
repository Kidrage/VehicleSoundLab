"""Declared finite-window controls, including deterministic AM and swept overlap."""
import numpy as np


def cases(plan):
    p, spec = plan['known_before_source'], plan['measurement']
    rate, root, n = p['rate'], p['root_hz'], p['frames']
    t = np.arange(n)/rate
    orders = [(5, .12), (127, .035), (201, .02)]

    def tones(phase, half=False, mono=False):
        items = [(60.5, .04), (170.5, .03)] if half else orders
        left = sum(amp*np.cos(2*np.pi*k*phase+.13*k) for k, amp in items)
        right = left.copy() if mono else sum(.7*amp*np.cos(2*np.pi*k*phase+.13*k+.4) for k, amp in items)
        return np.column_stack([left, right])

    phase = root*t
    h, inter = tones(phase), tones(phase, half=True)
    inputs = [('zero', np.zeros_like(h)), ('mono', tones(phase, mono=True)),
              ('asymmetric_phased', h), ('static_interline', inter), ('static_mixed', h+inter)]
    carrier = np.column_stack([.13*np.cos(2*np.pi*127*phase+.1), .09*np.cos(2*np.pi*127*phase+.5)])
    inputs.append(('deterministic_half_order_AM', carrier*(1+.4*np.cos(np.pi*phase))[:, None]))
    results = [dict(name=name, audio=audio, bounds_kind='static') for name, audio in inputs]
    sweep = 60*t+7.5*t*t
    results += [dict(name='rising_harmonics', audio=tones(sweep), bounds_kind='linear'),
                dict(name='rising_half_orders', audio=tones(sweep, half=True), bounds_kind='linear')]
    time = np.arange(2*rate)/rate
    amplitude = 1+.4*np.cos(2*np.pi*4*time)
    stereo = np.column_stack([.13*np.cos(2*np.pi*127*root*time+.1), .09*np.cos(2*np.pi*127*root*time+.5)])
    results.append(dict(name='slow_AM', audio=stereo*amplitude[:, None], bounds_kind='static', envelope=amplitude))
    for seed in p['seeds']:
        normal = np.random.default_rng(seed).standard_normal((rate, 2))
        audio = .035*np.column_stack([normal[:, 0], .6*normal[:, 0]+.8*normal[:, 1]])
        results.append(dict(name='white_'+str(seed), audio=audio, bounds_kind='static'))
    return results


def bounds(case, spec):
    starts = np.arange(0, len(case['audio'])-spec['window_samples']+1, spec['hop_samples'])
    if case['bounds_kind'] == 'linear':
        first = 60+15*starts/spec['rate']
        last = 60+15*(starts+spec['window_samples']-1)/spec['rate']
        return np.column_stack([first, last])
    return np.full((len(starts), 2), 64.)
