"""Independent analytic signals; construction never calls the estimated clock."""
import numpy as np
from scipy import signal


def make(case, seconds):
    rate = 48000
    t = np.arange(round(seconds*rate))/rate
    root, kind = float(case['root_hz']), case['kind']
    phase = root*t
    frequency = np.full(len(t), root)
    if kind in ('drift', 'partial_gap', 'sideband', 'masking', 'phase_contamination', 'stereo_delay'):
        for depth, hz in ((.025, .6), (.012, 1.9)):
            phase += root*depth*(1-np.cos(2*np.pi*hz*t))/(2*np.pi*hz)
            frequency += root*depth*np.sin(2*np.pi*hz*t)
    if kind == 'rise':
        phase += 3.0*t*t
        frequency += 6.0*t
    if kind == 'rapid_corner':
        u = np.clip((t-1.7)/.38, 0, 1)
        frequency = np.interp(u, [0, .32, .53, .68, 1], [25, 30, 50, 63, 70])
        # Trapezoids integrate this independently declared piecewise-linear
        # curve, rather than using any inverse clock or projection utility.
        phase = np.r_[0, np.cumsum((frequency[1:]+frequency[:-1])/(2*rate))]
    audio = np.zeros((len(t), 2))
    for order in range(1, 289):
        if kind == 'noise_only' or (kind == 'single_carrier' and order != 5):
            continue
        amplitude = .014/(1+order/12)**.8
        if order in (2, 3, 5, 7, 10, 15, 20):
            amplitude = .045
        level = 1+.09*np.sin(2*np.pi*.73*t+.19*order)
        if kind == 'partial_gap' and order == 5:
            level *= 1-np.exp(-((t-2.05)/.12)**8)
        if kind == 'all_carriers_gap':
            level *= 1-np.exp(-((t-2.05)/.18)**8)
        angle = 2*np.pi*order*phase+.37*order+.013*order*order
        if kind == 'phase_contamination' and order == case.get('contaminated_order', 5):
            angle += 1.2*np.sin(2*np.pi*6*t)
        audio[:, 0] += amplitude*level*np.cos(angle)
        right_angle = angle+.17+.021*order
        if kind == 'stereo_delay':
            delayed_time = t-.0007
            delayed_phase = root*delayed_time
            for depth, hz in ((.025, .6), (.012, 1.9)):
                delayed_phase += root*depth*(1-np.cos(2*np.pi*hz*delayed_time))/(2*np.pi*hz)
            right_angle = 2*np.pi*order*delayed_phase+.37*order+.013*order*order+.17+.021*order
        audio[:, 1] += amplitude*.82*level*np.cos(right_angle)
        if kind == 'sideband' and order == 5:
            # Symmetric AM sidebands; do not alter the underlying common phase.
            audio[:, 0] += amplitude*.7*np.cos(2*np.pi*6*t)*np.cos(angle)
            audio[:, 1] += amplitude*.7*.82*np.cos(2*np.pi*6*t)*np.cos(angle+.17+.021*order)
    if kind == 'masking':
        audio += .09*np.cos(2*np.pi*(case.get('masked_order', 5)*root+7.3)*t)[:, None]*np.array([1, .63])
    rng = np.random.default_rng(910246)
    noise = signal.sosfilt(signal.butter(2, 9000, fs=rate, output='sos'), rng.normal(size=audio.shape))
    audio += .0025*noise
    return audio, t, phase, frequency
