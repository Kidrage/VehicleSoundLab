"""Known-first checks; never runs a real-recording contour solve."""
import argparse
from copy import deepcopy
from pathlib import Path
import shutil

import numpy as np
from scipy import signal

from event_authoring.contour_ensemble import (EnsembleResponse, ContourProblem,
    gains, with_gains, solve, validate_candidate, TEMPORAL_EDGES)
from event_authoring.contour_response import QuadraticResponse
from event_authoring.model import synth
from event_authoring.native import Renderer, controls
from event_authoring.response_ensemble import TRAIN_SEEDS, HELD_OUT_SEEDS, band_powers
from event_authoring.response_fit import EDGES
from event_authoring.temporal_fit import band_curves
from research_archive_v1 import load, save, sha


def known_profile(gated, cutoff):
    p = dict(gated=gated, duration_seconds=1. if gated else .24, attack_seconds=.002,
        release_seconds=.02, sweep_seconds=.05, level=.7,
        modes=[dict(hz=hz, end_hz=hz*1.08, amplitude=.1, phase=.2,
                    decay_seconds=.4, attack_seconds=.001) for hz in (130., 740., 2800., 6550.)],
        bands=[dict(hz=hz, q=1.3, amplitude=.04, attack_seconds=.002,
                    decay_seconds=.5) for hz in (140., 680., 2700., 6400.)],
        contours=[dict(low_hz=lo, high_hz=hi, seconds=[0., .035, .08, .15, .24],
                       gain=[.2, .7, 1., .1, .4]) for lo, hi in ((60, 300), (1200, 4500))])
    if cutoff:
        p['noise_lowpass_hz'] = cutoff
    return p


def direct_gram_power(wave, hop, edges):
    f, _, power = signal.spectrogram(wave, 48000, window='hann', nperseg=2048,
        noverlap=2048-hop, detrend=False, scaling='density', mode='psd')
    return np.array([power[(f >= lo) & (f < hi)].sum(axis=0)*(f[1]-f[0]) for lo, hi in edges])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    out = parser.parse_args().output
    out.mkdir(parents=True, exist_ok=False)
    repo = Path(__file__).resolve().parents[1]
    sources = [Path(__file__), repo/'tools/event_authoring/contour_ensemble.py',
               repo/'research/startup_contour_ensemble_v1_plan.json',
               *sorted((repo/'tools/event_authoring').glob('*.py'))]
    for path in set(sources):
        destination = out/'exact_sources'/path.relative_to(repo)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
    renderer = Renderer(repo)
    checks = []
    for gated, cutoff in ((0, 0.), (1, 8000.)):
        p = known_profile(gated, cutoff)
        response = EnsembleResponse(p, .24, seeds=TRAIN_SEEDS[:2], retain_waveforms=True)
        values = np.linspace(.15, 1.25, response.count)
        candidate = with_gains(p, values)
        assert np.mean(response.bases[:, :, -1]**2) > 1e-6
        waveform_errors, power_errors, native_errors = [], [], []
        for index, seed in enumerate(response.seeds):
            wave = synth(candidate, seed=seed, seconds=.24)
            error = float(np.max(abs(wave-response.waveform(index, values))))
            assert error < 3e-14
            waveform_errors.append(error)
            for name, hop, edges in (('temporal', 240, TEMPORAL_EDGES), ('spectral', 1024, EDGES)):
                measured = direct_gram_power(wave, hop, edges)
                if name == 'spectral':
                    measured = measured.mean(axis=1)
                predicted = QuadraticResponse.power(getattr(response, name), values)[index]
                np.testing.assert_allclose(predicted, measured, rtol=4e-11, atol=4e-15)
                power_errors.append(float(np.max(abs(predicted-measured))))
            c, _ = renderer.render(candidate, 'crank' if gated else 'catch',
                controls(dict(seed=seed, seconds=.39, hold_seconds=.24)))
            py = synth(candidate, seed=seed, seconds=len(c)/48000,
                       release_at=.24 if gated else None)
            py = np.pad(py, (0, len(c)-len(py)))
            cerror = float(np.max(abs(c-py)))
            assert cerror < 3e-7
            native_errors.append(cerror)
        reference = QuadraticResponse.power(response.temporal, gains(p)).mean(axis=0)
        reference = reference/np.maximum(reference.mean(axis=-1), 1e-30)[:, None]
        targets = QuadraticResponse.power(response.spectral, gains(p)).mean(axis=0)
        problem = ContourProblem(response, gains(p), reference, list(range(4)), targets)
        _, gradient, _, jacobian = problem.evaluate(values)
        numeric_gradient = np.empty(response.count)
        numeric_jacobian = np.empty_like(jacobian)
        eps = 1e-6
        for i in range(response.count):
            direction = np.zeros(response.count)
            direction[i] = eps
            plus, minus = problem.evaluate(values+direction), problem.evaluate(values-direction)
            numeric_gradient[i] = (plus[0]-minus[0])/(2*eps)
            numeric_jacobian[:, i] = (plus[2]-minus[2])/(2*eps)
        np.testing.assert_allclose(gradient, numeric_gradient, rtol=2e-5, atol=2e-7)
        np.testing.assert_allclose(jacobian, numeric_jacobian, rtol=3e-5, atol=3e-7)
        checks.append(dict(gated=gated, cutoff=cutoff, affine_constant_nonzero=True,
            max_waveform_error_FS=max(waveform_errors), max_power_error=max(power_errors),
            max_C_error_FS=max(native_errors),
            gradient_error=float(np.max(abs(gradient-numeric_gradient))),
            constraint_J_error=float(np.max(abs(jacobian-numeric_jacobian)))))
        print('known affine, Hann power and Jacobians passed', gated, cutoff, flush=True)

    truth = known_profile(0, 0.)
    truth['modes'] = truth['modes'][:1]+truth['modes'][2:3]
    truth['bands'] = []
    truth['sweep_seconds'] = 0.
    truth['contours'][1]['gain'] = [.5, 1., .3, .8, .1]
    original = with_gains(truth, np.full(len(gains(truth)), .5))
    truth_waves = [synth(truth, seed=seed, seconds=.24) for seed in TRAIN_SEEDS]
    target = np.mean([band_curves(w)[1] for w in truth_waves], axis=0)
    targets = np.mean([band_powers(w) for w in truth_waves], axis=0)
    bands = [dict(hz=list(edge), selected=i in (0, 2)) for i, edge in enumerate(TEMPORAL_EDGES)]
    candidate, report = solve(original, target, bands, targets, .24)
    save(out/'known-candidate-before-validation.json', candidate)
    fixed_sha = sha(out/'known-candidate-before-validation.json')
    qualified = validate_candidate(original, candidate, target, bands, targets, .24, report)
    assert qualified['qualified'], qualified
    assert qualified['relative_improvement'] > .5
    assert sha(out/'known-candidate-before-validation.json') == fixed_sha
    # Explicit impossible spectral request is refused without changing parameters.
    impossible = targets*1e12
    refused = validate_candidate(original, original, target, bands, impossible, .24,
        dict(useful=True, training_qualified=True, qualified=False))
    assert not refused['qualified']
    # No mutation of an existing source profile or replacement of an old solver.
    assert gains(original).tolist() == [.5]*len(gains(original))
    for bad in ({**original, 'contours': []},):
        try:
            EnsembleResponse(bad, .24)
        except ValueError:
            pass
        else:
            raise AssertionError('Missing existing contours must be rejected')
    runtime = load(Path('E:/VehicleSoundLab/references/analysis/A_exterior_startup_v1/selection1/runtime.json'))
    assert len(runtime) == 459 and all(sha(repo/name) == digest for name, digest in runtime.items())
    save(out/'report.json', dict(result='passed', known_math=checks, known_solve=qualified,
        impossible_spectral_target_refused=True, old_profile_not_mutated=True,
        runtime_voice_files_unchanged=459, actual_renderer_sha256=renderer.identity,
        real_material_fit_run=False, goal_complete=False, timbre_accepted=False))
    print('known solve/refusal/runtime checks passed; no real material fit', flush=True)


if __name__ == '__main__':
    main()
