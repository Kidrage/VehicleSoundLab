"""Exact local controls, inverse controls and analytic-tail qualification."""
import itertools
import numpy as np
from scipy import signal
from .response import kernels, matrices, support
from .budget import summarize, allocate, prediction


def run():
    taps = [np.array([.7, -.2]), np.array([.3, .6])]
    observers = [np.array([.8, .3]), np.array([-.25, .5])]
    time = np.arange(12)
    g = np.column_stack((1+.3*np.sin(.9*time), .8+.2*np.cos(.4*time)))
    origins = np.arange(3, 11); main = np.column_stack((.1+.2*np.cos(origins*.31), -.04+.15*np.sin(origins*.59)))
    response = [kernels(origins, g[:, i], h, observers) for i, h in enumerate(taps)]
    cov = sum(matrices(h)[0] for h in response)
    operator = np.stack([matrices(h)[1] for h in response], axis=-1)
    maximum = 0.
    for label, levels, weights, kappa in [('binary', [-1., 1.], [.5, .5], -2.),
        ('Gaussian_moments', [-np.sqrt(3), 0., np.sqrt(3)], [1/6, 2/3, 1/6], 0.),
        ('sparse', [-np.sqrt(6), 0., np.sqrt(6)], [1/12, 5/6, 1/12], 3.)]:
        raw = np.zeros((3, 8))
        pairs = [(0, 0), (0, 1), (1, 1)]
        for index, at in enumerate(origins):
            addresses = [(s, i) for s in range(at-2, at+1) for i in range(2)]
            draws = np.array(list(itertools.product(range(len(levels)), repeat=6)))
            probability = np.prod(np.asarray(weights)[draws], axis=1)
            e = np.asarray(levels)[draws]; output = np.tile(main[index], (len(draws), 1))
            for b in range(2):
                for u in range(2):
                    for k in range(2):
                        for i in range(2):
                            output[:, b] += observers[b][u]*g[at-u, i]*taps[i][k]*e[:, addresses.index((at-u-k, i))]
            for p, (b, c) in enumerate(pairs):
                x, y = output[:, b], output[:, c]
                raw[p] += [probability@(x**j*y**k)/len(origins) for j, k in [(1,0),(0,1),(2,0),(0,2),(1,1),(2,1),(1,2),(2,2)]]
        from idle_wave_budget_v1.moments import pooled
        for p, (b, c) in enumerate(pairs):
            observed = pooled(main[:, b], main[:, c], cov[:, b, b], cov[:, c, c], cov[:, b, c], operator[:, b, c].sum(axis=1)*kappa)
            error = float(abs(raw[p]-observed['raw']).max()); maximum = max(maximum, error)
            assert error < 1e-12, (label, b, c, error)
    operator4 = np.eye(4)+.1
    state = dict(operator=np.zeros((10,4)), gaussian=np.zeros(10), denominator=np.ones(10))
    state['operator'][[0,4,7,9]] = operator4
    for expected in [np.array([1., 2., 3., 4.]), np.array([-1., 2., 3., 4.])]:
        source = prediction(state, expected); result = allocate(state, source)
        assert abs(np.asarray(result['kappa'])-expected).max() < 1e-12
        assert result['generative'] == bool(np.all(expected >= 0))
    state['operator'][:, 1] = state['operator'][:, 0]
    assert allocate(state, np.ones(10))['status'] == 'rank_deficient_UNKNOWN'
    sos = np.array([[.1,.2,.1,1.,-1.2,.4]])
    impulse, bound = support(sos)
    full = np.zeros(65536); full[0] = 1; full = signal.sosfilt(sos, full)
    assert abs(full[len(impulse):]).sum() <= bound['tail_L1_bound']
    try: support(np.array([[.1,.2,.1,1.,-1.8,.81]]))
    except ValueError: pass
    else: raise AssertionError('Repeated-pole hypothesis must not use distinct-pole bound')
    return dict(maximum_raw_error=maximum, all3_exact_ensembles=True,
                positive_negative_and_rank_controls=True, stable_tail_and_repeated_rejection=True)
