"""Known amplitude-unit stress test, no real source or held-out observations."""
import argparse
from copy import deepcopy
from pathlib import Path
import shutil

import numpy as np

from audit_startup_contour_ensemble_v1 import powers
from event_authoring.source_support import SupportProblem
from event_band_texture.fit import Response, Coordinates, solve_conditioned
from event_band_texture.profile import TRAIN_SEEDS, vector, with_vector
from event_band_texture.voice import render
from verify_event_band_texture_v1 import prescribed
from research_archive_v1 import save


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    out = parser.parse_args().output
    out.mkdir(parents=True, exist_ok=False)
    repo = Path(__file__).resolve().parents[1]
    for path in [Path(__file__), repo/'tools/verify_event_band_texture_v1.py',
                 repo/'research/event_texture_conditioning_v1_plan.json',
                 *sorted((repo/'tools/event_band_texture').glob('*.py'))]:
        dest = out/'exact_sources'/path.relative_to(repo)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
    rows = []
    evaluations = []
    for scale in (1., 1e-4):
        truth = prescribed()
        truth['modal']['level'] *= scale
        waves = [render(truth, .5, seed) for seed in TRAIN_SEEDS]
        target = np.mean([powers(w, 240)[1:5] for w in waves], axis=0)
        reference = target/target.mean(axis=1)[:, None]
        targets = np.mean([powers(w, 1024).mean(axis=1) for w in waves], axis=0)
        # Equivalent waveform and physical amplitude units: put the common
        # scale into the source mode and noise gains, not a cosmetic output gain.
        truth['modal']['level'] /= scale
        for mode in truth['modal']['modes']:
            mode['amplitude'] *= scale
        truth = with_vector(truth, vector(truth)*scale)
        flat = with_vector(truth, np.full(32, .06*scale))
        legacy = []
        for seed in TRAIN_SEEDS:
            curve = powers(render(flat, .5, seed), 240)[1:5]
            legacy.append(np.sqrt(np.mean((curve/curve.mean(axis=1)[:, None]-reference)**2, axis=1)))
        response = Response(truth, .5)
        problem = SupportProblem(response, vector(flat), reference, list(range(4)), targets, legacy)
        coordinate = Coordinates(problem, vector(flat))
        z = np.linspace(.6, 1.5, 32)
        evaluated = coordinate.evaluate(z)
        raw = problem.evaluate(z*coordinate.scale)
        assert evaluated[0] == raw[0]
        np.testing.assert_array_equal(evaluated[2], raw[2])
        np.testing.assert_allclose(evaluated[1], raw[1]*coordinate.scale, atol=0, rtol=0)
        evaluations.append(evaluated)
        candidate, fit = solve_conditioned(flat, reference, list(range(4)), targets, legacy, .5)
        assert fit['optimizer_terminated'] and fit['minimum_constraint'] >= -1e-7, fit
        assert fit['objective'] < fit['initial_objective']*.8, fit
        rows.append(dict(waveform_scale=scale, fit=fit))
        save(out/('candidate-'+str(scale)+'.json'), candidate)
    errors = []
    for a, b in zip(*evaluations):
        errors.append(float(np.max(abs(np.asarray(a)-np.asarray(b)))))
        np.testing.assert_allclose(a, b, atol=3e-9, rtol=3e-9)
    save(out/'report.json', dict(result='passed', real_fit_performed=False,
        scales=rows, objective_gradient_constraint_J_scale_invariance_error=errors,
        no_source_or_held_out_used=True, identical_physical_bounds=True,
        goal_complete=False, timbre_accepted=False))
    print('normal and1e-4 known amplitude units preserve objective/J/feasible profiles; both solves pass', flush=True)


if __name__ == '__main__':
    main()
