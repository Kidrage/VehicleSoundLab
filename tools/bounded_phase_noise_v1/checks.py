"""Independent white-noise/line/sweep controls for the observational proxy."""
import numpy as np
from .noise import estimate


def controls(settings):
    frames = 5120
    time = np.arange(frames)/128
    sigma = .00025
    rows = []
    for index, label in enumerate(('white', 'offgrid_lines', 'rapid_chirp')):
        rng = np.random.default_rng(81364+index)
        observed = sigma*rng.normal(size=frames)
        if label == 'offgrid_lines':
            observed += .4*np.cos(2*np.pi*3.141*time+.2)+.12*np.sin(2*np.pi*15.17*time)
        if label == 'rapid_chirp':
            observed += .4*np.cos(2*np.pi*(6*time+.05*time**2))
        result = estimate(observed, settings['noise_proxy_nyquist_fraction'], settings['minimum_noise_bins'])
        error = abs(result['standard_deviation']/sigma-1)
        assert error < .2
        rows.append(dict(id=label, known_sigma=sigma, proxy=result, relative_sigma_error=float(error)))
    try:
        estimate(np.ones(64), settings['noise_proxy_nyquist_fraction'], settings['minimum_noise_bins'])
    except ValueError:
        rejected = True
    else:
        rejected = False
    assert rejected
    return dict(passed=True, cases=rows, insufficient_support_rejected=True,
        limits=['These controls do not calibrate high-frequency engine texture or real coloured noise'])
