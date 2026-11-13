"""Same exact column span, different ordering: test the full numerical projector."""
import numpy as np
from .adjoint import native_adjoint


def compare(first, second, signals, tolerance):
    # Residual projection avoids cancellation in sqrt(1-cos(angle)**2).
    overlap = first.T@second
    left = second-first@overlap
    right = first-second@overlap.T
    subspace_error = float(max(abs(left).max(), abs(right).max()))
    rows = []
    for label, signal in signals:
        one = first@(first.T@signal)
        two = second@(second.T@signal)
        rows.append(dict(id=label, first_captured_fraction=float((one@one)/(signal@signal)),
            second_captured_fraction=float((two@two)/(signal@signal)),
            relative_source_projection_difference=float(np.linalg.norm(one-two)/np.linalg.norm(signal))))
    maximum = max(row['relative_source_projection_difference'] for row in rows)
    return dict(passed=bool(max(subspace_error, maximum) <= tolerance),
        tolerance=tolerance, maximum_subspace_residual_element=subspace_error,
        maximum_relative_source_projection_difference=maximum, signals=rows)


def check(model, initial, saved_basis, plan):
    outer, controls = model.unpack(initial)
    _, phase = model.prediction(outer, controls, True)
    observed = np.column_stack((phase, model.design(outer)))
    raw = native_adjoint(model.original.aperture, observed, len(model.original.time))
    raw /= np.linalg.norm(raw, axis=0)[None, :]
    # A permutation changes neither exact column space nor its orthogonal projector.
    reverse, singular, _ = np.linalg.svd(raw[:, ::-1], full_matrices=False)
    assert len(singular) == observed.shape[1] and singular.min() > 0
    time = model.original.time
    signals = [(f'tone_{order}', .2*np.cos(2*np.pi*order*time+.31))
               for order in (3., 3.1, 8.37, 9.13, 10., 15.)]
    rng = np.random.default_rng(701284)
    signals.append(('independent_source_white', rng.normal(size=len(time))))
    tolerance = plan['rules']['maximum_forward_check_error']
    result = compare(saved_basis, reverse, signals, tolerance)
    # Independently specified, well-conditioned analytic span verifies the check.
    columns = np.column_stack((np.sin(2*np.pi*3*time), np.cos(2*np.pi*3*time),
                               np.sin(2*np.pi*5*time)))
    transform = np.array([[1., .25, -.125], [0., 1., .5], [0., 0., 1.]])
    first = np.linalg.svd(columns, full_matrices=False)[0]
    second = np.linalg.svd((columns@transform)[:, ::-1], full_matrices=False)[0]
    control = compare(first, second, signals, tolerance)
    assert control['passed']
    result.update(reversed_columns=raw.shape[1], retained_columns=reverse.shape[1],
        reverse_singular_values=singular.tolist(),
        reverse_condition=float(singular.max()/singular.min()),
        analytic_full_rank_control=control, no_fit_or_truth_or_heldout_access=True)
    return result, reverse
