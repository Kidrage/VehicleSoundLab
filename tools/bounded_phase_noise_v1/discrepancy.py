"""Observation-only, first-crossing discrepancy prefix selector."""
import numpy as np


def first_crossing(candidates, variance, covariance_trace):
    if not np.isfinite(variance) or variance <= 0 or not np.isfinite(covariance_trace) or covariance_trace <= 0:
        raise ValueError('A positive finite observed noise budget is required')
    budget = variance*covariance_trace
    examined = []
    for candidate in candidates:
        if not candidate['accepted']:
            continue
        residual = np.asarray(candidate['observed_residual'])
        if residual.ndim != 1 or not np.isfinite(residual).all():
            raise ValueError('The observed residual must be a finite vector')
        energy = float(residual@residual)
        examined.append(dict(iteration=candidate['iteration'], residual_energy=energy))
        if energy <= budget:
            return candidate, dict(selected_iteration=candidate['iteration'], expected_noise_energy=budget,
                examined=examined, reached=True, truth_used=False, heldout_used=False,
                confidence_interval=False)
    return None, dict(selected_iteration=None, expected_noise_energy=budget, examined=examined,
        reached=False, truth_used=False, heldout_used=False, confidence_interval=False)


def controls():
    def candidate(i, residual, accepted=True):
        return dict(iteration=i, observed_residual=np.asarray(residual), accepted=accepted)
    selected, evidence = first_crossing(iter([candidate(0, [2]), candidate(1, [0], False),
        candidate(2, [.5]), candidate(3, [.1])]), .25, 1.)
    assert selected['iteration'] == 2 and len(evidence['examined']) == 2
    assert first_crossing([candidate(0, [1])], .1, 1.)[0] is None
    def lazy():
        yield candidate(0, [0])
        raise AssertionError('Selector read a future candidate after crossing')
    assert first_crossing(lazy(), .1, 1.)[0]['iteration'] == 0
    for variance, trace in ((0., 1.), (1., -1.), (float('nan'), 1.)):
        try:
            first_crossing([], variance, trace)
        except ValueError:
            pass
        else:
            raise AssertionError('Invalid noise budget was accepted')
    return dict(passed=True, rejected_candidates_ignored=True, first_crossing_inclusive=True,
        no_future_candidate_read=True, no_crossing_explicit=True, invalid_budgets_rejected=True)
