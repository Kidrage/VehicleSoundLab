"""Known copies and independently drawn detail with the same carrier spectrum."""
import numpy as np
from .match import match, passes


def check(rate, gates):
    rng = np.random.default_rng(231804)
    frames, margin = 3*rate, round(.75*rate)
    time = np.arange(frames+2*margin)/rate
    shared = sum(.08*np.cos(2*np.pi*frequency*time+.13*k)
                 for k, frequency in enumerate((120., 240., 480., 960.)))
    independent = rng.normal(0, .08, (len(time), 2))
    first = shared[:, None]*np.array([[1., .8]])+independent
    shift = 817
    template = first[margin:margin+frames]
    copied = np.zeros_like(first)
    copied[shift:] = first[:-shift]
    copied = copied*np.array([[.8, .72]])+np.array([[.013, -.021]])
    exact, _ = match(template, copied, rate, margin)
    assert exact['integer_lag_samples'] == shift and passes(exact, gates)
    noisy, _ = match(template, copied+rng.normal(0, .004, copied.shape), rate, margin)
    assert noisy['integer_lag_samples'] == shift and passes(noisy, gates)
    separate = shared[:, None]*np.array([[1., .8]])+rng.normal(0, .08, first.shape)
    different, _ = match(template, separate, rate, margin)
    assert not passes(different, gates)
    for row in (exact, noisy, different):
        assert row['FFT_vs_direct_vs_scalar_maximum_error'] <= 1e-12
    return dict(passed=True, known_copy=exact, known_copy_with_independent_added_noise=noisy,
        same_carriers_independent_detail=different, controls_only=True,
        no_match_does_not_prove_independence=True)
