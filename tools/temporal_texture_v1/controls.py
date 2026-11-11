"""Known beating and common modulation controls, independent of recording fits."""
import numpy as np
from .features import measure,phase_surrogate,scalar_power_check,summarize


def run(plan):
    rate = plan['sample_rate'];time = np.arange(4*rate)/rate
    controls = []
    # Analytic window-weighted power of a two-sine beat, with no added AM.
    a,b,delta = .7,.3,7.
    mono = a*np.cos(2*np.pi*2500*time)+b*np.cos(2*np.pi*(2500+delta)*time)
    audio = np.column_stack((mono,.6*mono))
    data = measure(audio,plan)
    window = .5-.5*np.cos(2*np.pi*np.arange(plan['size'])/plan['size'])
    expected = []
    for start in data['window_starts']:
        t = (start+np.arange(plan['size']))/rate
        expected.append(np.sum(window**2*((a*a+b*b)/2+a*b*np.cos(2*np.pi*delta*t)))/np.sum(window**2))
    expected = np.array(expected)
    rms_error = float(np.max(abs(np.sqrt(data['power'][0,:,3,0]/expected)-1)))
    assert rms_error < plan['two_tone_rms_relative_tolerance'],rms_error
    peak_error = float(abs(data['modulation_peak_hz'][:,3,0]-delta).max())
    assert peak_error < plan['beat_peak_error_hz'],peak_error
    direct_error = scalar_power_check(audio,data,plan)
    assert direct_error < plan['scalar_dft_relative_tolerance'],direct_error
    controls.append(dict(name='two_sine_beat_without_added_AM',analytic_rms_relative_error=rms_error,
        peak_error_hz=peak_error,scalar_dft_relative_error=direct_error,summary=summarize(data)))

    centers = [(lo+hi)/2 for lo,hi in plan['bands']]
    mono = sum(np.cos(2*np.pi*hz*time) for hz in centers)*(1+.3*np.cos(2*np.pi*3*time))
    data = measure(np.column_stack((mono,.7*mono)),plan)
    pairs = ~np.eye(len(centers),dtype=bool)
    minimum = float(data['correlation'][:,:,pairs].min())
    assert minimum >= plan['common_am_minimum_crossband_correlation'],minimum
    assert abs(data['modulation_peak_hz']-3).max() < plan['beat_peak_error_hz']
    controls.append(dict(name='known_common_3Hz_AM',minimum_crossband_correlation=minimum,summary=summarize(data)))

    for seed in plan['control_seeds']:
        rng = np.random.default_rng(seed)
        audio = rng.normal(size=(len(time),2))
        data = measure(audio,plan)
        direct_error = scalar_power_check(audio,data,plan)
        assert direct_error < plan['scalar_dft_relative_tolerance']
        surrogate,spectral_error = phase_surrogate(audio,seed+1)
        assert spectral_error < plan['surrogate_relative_spectral_tolerance']
        controls.append(dict(name='independent_gaussian',seed=seed,scalar_dft_relative_error=direct_error,
            surrogate_spectral_error=spectral_error,summary=summarize(data)))
    assert max(c['summary']['maximum_parseval_error'] for c in controls) < plan['parseval_absolute_tolerance']
    # Unit-amplitude chirp crosses a measurement boundary; observations must not
    # be mislabeled as an independently imposed engine-amplitude modulation.
    chirp = np.cos(2*np.pi*(1420*time+20*time*time))
    data = measure(np.column_stack((chirp,chirp)),plan)
    controls.append(dict(name='constant_amplitude_boundary_chirp',summary=summarize(data)))
    return controls
