"""Exact finite ensembles distinguish marginal from simultaneous concentration."""
import itertools
import numpy as np
from .moments import joint, independent_expectation


def fixtures():
    output = {}
    z = [-np.sqrt(3.), 0., np.sqrt(3.)]
    zw = [1/6, 2/3, 1/6]
    p = .25
    for shared in [False, True]:
        samples, weights = [], []
        for marks in itertools.product([0, 1], repeat=1 if shared else 4):
            wm = np.prod([p if b else 1-p for b in marks])
            for indices in itertools.product(range(3), repeat=4):
                b = np.repeat(marks, 4) if shared else np.asarray(marks)
                samples.append(b * np.array([z[i] for i in indices]) / np.sqrt(p))
                weights.append(wm * np.prod([zw[i] for i in indices]))
        expected = np.full((4, 4), 3. if shared else 0.)
        np.fill_diagonal(expected, 9.)
        output['shared_marks' if shared else 'independent_marks'] = dict(
            x=np.array(samples), weights=np.array(weights), expected=expected)
    # Four independent innovations, two taps each, mixed into four observations.
    h = np.array([[[.8,.3],[.2,-.1],[.1,.4],[.3,.2]],
                  [[.4,-.1],[.5,.2],[.2,.3],[.1,-.2]],
                  [[.1,.5],[.2,.1],[.7,-.2],[.3,.4]],
                  [[.2,.1],[.1,.3],[.2,-.1],[.8,.2]]])
    latent = np.array(list(itertools.product([-1.,1.], repeat=8)))
    x = latent @ h.reshape(4, 8).T
    output['independent_FIR'] = dict(x=x, weights=np.ones(len(x))/len(x), responses=h,
        expected_cumulant=independent_expectation(h, np.full(4, -2.)))
    return output


def check(data):
    summary = {}
    for name, fixture in data.items():
        result = joint(fixture['x'], fixture['weights'])
        key = 'normalized' if 'expected' in fixture else 'cumulant'
        expected = fixture.get('expected', fixture.get('expected_cumulant'))
        error = float(abs(np.array(result[key]) - expected).max())
        assert error < 1e-12, (name, error)
        if name != 'independent_FIR':
            assert np.allclose(result['covariance'], np.eye(4), atol=1e-12)
        scaled = joint(fixture['x'] * np.array([-.137, 2., .6, -3.]), fixture['weights'])
        assert np.allclose(scaled['normalized'], result['normalized'], atol=1e-12)
        summary[name] = dict(error=error, observation=result)
    return summary
