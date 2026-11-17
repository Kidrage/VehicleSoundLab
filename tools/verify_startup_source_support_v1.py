"""Known-only support design, new objective/Jacobians and bounded-solve checks."""
import argparse
from copy import deepcopy
from pathlib import Path
import shutil

import numpy as np

from event_authoring.contour_ensemble import EnsembleResponse, gains, with_gains, baseline_errors
from event_authoring.contour_response import QuadraticResponse
from event_authoring.contour_all_bands import observations
from event_authoring.measure import observe
from event_authoring.model import synth
from event_authoring.native import Renderer, controls
from event_authoring.response_ensemble import TRAIN_SEEDS, band_powers
from event_authoring.source_support import (design, noise_basis, noise_objective,
    SupportProblem, joint_solve, HELD_OUT_SEEDS)
from event_authoring.temporal_fit import band_curves
from research_archive_v1 import load, save, sha


def prescribed():
    edges = ((60, 300), (300, 1200), (1200, 4500), (4500, 14000))
    frequencies = (150., 680., 2700., 6900.)
    shape = ([.2, .8, 1., .2, .6, .1], [.5, .2, .8, .9, .3, .1],
             [.9, .7, .2, .8, .4, .1], [1., .2, .4, .7, .2, .1])
    return dict(gated=0, duration_seconds=.24, attack_seconds=.001, release_seconds=.015,
        sweep_seconds=0., level=.7,
        modes=[dict(hz=f, end_hz=f, amplitude=.05, phase=.3, decay_seconds=.5) for f in frequencies],
        bands=[dict(hz=f, q=2.5, amplitude=.04, attack_seconds=.001, decay_seconds=.5) for f in frequencies],
        contours=[dict(low_hz=lo, high_hz=hi, seconds=[0., .03, .06, .12, .18, .24], gain=list(s))
                  for (lo, hi), s in zip(edges, shape)])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    out = parser.parse_args().output
    out.mkdir(parents=True, exist_ok=False)
    repo = Path(__file__).resolve().parents[1]
    for p in [Path(__file__), repo/'research/startup_source_support_v1_plan.json',
              *sorted((repo/'tools/event_authoring').glob('*.py'))]:
        dest = out/'exact_sources'/p.relative_to(repo)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dest)
    truth = prescribed()
    # Modal energy is an affine constant in the noise-amplitude calibration.
    gram = noise_basis(truth, .24, seeds=TRAIN_SEEDS[:2])
    assert np.max(gram[:, :, -1, -1]) > 1e-6
    amplitude = np.array([.03, .07, .04, .02])
    modified = deepcopy(truth)
    for b, a in zip(modified['bands'], amplitude):
        b['amplitude'] = float(a)
    predicted = QuadraticResponse.power(gram, amplitude)
    actual = np.array([band_powers(synth(modified, seed=s, seconds=.24)) for s in TRAIN_SEEDS[:2]])
    np.testing.assert_allclose(predicted, actual, atol=3e-15, rtol=4e-11)
    targets = actual.mean(axis=0)
    residual, jacobian = noise_objective(gram, targets, amplitude)
    numeric = np.empty_like(jacobian)
    for i in range(4):
        direction = np.zeros(4)
        direction[i] = 1e-6
        numeric[:, i] = (noise_objective(gram, targets, amplitude+direction)[0]-
                         noise_objective(gram, targets, amplitude-direction)[0])/(2e-6)
    np.testing.assert_allclose(jacobian, numeric, rtol=3e-5, atol=3e-7)
    waves = [synth(truth, seed=s, seconds=.24) for s in TRAIN_SEEDS]
    target = np.mean([band_curves(w)[1] for w in waves], axis=0)
    targets = np.mean([band_powers(w) for w in waves], axis=0)
    reference = target/np.maximum(target.mean(axis=1), 1e-30)[:, None]
    original = with_gains(truth, np.full(len(gains(truth)), .5))
    legacy = baseline_errors(original, reference, .24, TRAIN_SEEDS)
    response = EnsembleResponse(truth, .24)
    problem = SupportProblem(response, gains(original), reference, list(range(4)), targets, legacy)
    values = np.linspace(.2, 1.1, len(gains(truth)))
    _, gradient, _, jacobian = problem.evaluate(values)
    numeric_gradient = np.empty_like(gradient)
    numeric_jacobian = np.empty_like(jacobian)
    for i in range(len(values)):
        direction = np.zeros(len(values))
        direction[i] = 1e-6
        plus, minus = problem.evaluate(values+direction), problem.evaluate(values-direction)
        numeric_gradient[i] = (plus[0]-minus[0])/(2e-6)
        numeric_jacobian[:, i] = (plus[2]-minus[2])/(2e-6)
    np.testing.assert_allclose(gradient, numeric_gradient, rtol=3e-5, atol=3e-7)
    np.testing.assert_allclose(jacobian, numeric_jacobian, rtol=4e-5, atol=5e-7)
    # Source statistics, bounds and original preservation; no real recording.
    source = np.column_stack((waves[0], -waves[0]))
    bg = np.full_like(source, 1e-8)
    _, arrays = observe(source, bg)
    time, observed, rows = observations(source, bg)
    assert all(row['selected'] for row in rows)
    designed, support = design(original, arrays, time, observed, rows, .24)
    assert designed['modes'] == original['modes']
    assert all(2 <= b['q'] <= 12 and lo <= b['hz'] < hi for b, (lo, hi) in zip(designed['bands'],
        ((60, 300), (300, 1200), (1200, 4500), (4500, 14000))))
    assert len(designed['contours']) == 4 and all(2 <= len(c['gain']) <= 8 for c in designed['contours'])
    candidate, report = joint_solve(original, original, target, rows, targets, .24)
    assert report['training_qualified'] and report['useful'], report
    assert report['relative_legacy_shape_improvement'] > .5
    held = []
    for s in HELD_OUT_SEEDS:
        c, _ = Renderer(repo).render(candidate, 'catch', controls(dict(seconds=.39, seed=s)))
        py = np.pad(synth(candidate, seed=s, seconds=.39), (0, len(c)-11520))
        error = float(np.max(abs(c-py)))
        assert error < 3e-7
        held.append(dict(seed=s, C_python_max_error_FS=error))
    rejected = []
    for bad in (dict(rows[0], selected=False),):
        weak = deepcopy(rows)
        weak[0] = bad
        try:
            design(original, arrays, time, observed, weak, .24)
        except ValueError:
            rejected.append('weak_band')
        else:
            raise AssertionError('Unreliable source group must be rejected')
    runtime = load(Path('E:/VehicleSoundLab/references/analysis/A_exterior_startup_v1/selection1/runtime.json'))
    assert len(runtime) == 459 and all(sha(repo/name) == digest for name, digest in runtime.items())
    save(out/'report.json', dict(result='passed', real_fit_performed=False,
        noise_power_max_error=float(np.max(abs(predicted-actual))),
        noise_J_error=float(np.max(abs(numeric-noise_objective(gram, actual.mean(axis=0), amplitude)[1]))),
        joint_gradient_error=float(np.max(abs(gradient-numeric_gradient))),
        joint_J_error=float(np.max(abs(jacobian-numeric_jacobian))),
        known_training=report, known_C=held, source_design=support, refused=rejected,
        old_profile_untouched=all(g == .5 for g in gains(original)), runtime_files_unchanged=459,
        goal_complete=False, timbre_accepted=False))
    print('known support design, affine calibration, analytic Jacobians, feasible solve, C and refusal passed', flush=True)


if __name__ == '__main__':
    main()
