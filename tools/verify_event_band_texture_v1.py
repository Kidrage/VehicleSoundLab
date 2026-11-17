"""Known-only frequency control, variance, affine power and fit verification."""
import argparse
from copy import deepcopy
from pathlib import Path
import shutil

import numpy as np
from scipy import signal

from audit_startup_contour_ensemble_v1 import powers
from event_authoring.contour_response import QuadraticResponse
from event_authoring.source_support import SupportProblem
from event_band_texture.profile import EDGES, TRAIN_SEEDS, fit_colour, validate, vector, with_vector
from event_band_texture.voice import carriers, basis, render
from event_band_texture.fit import Response, solve
from research_archive_v1 import load, save, sha


def prescribed():
    duration = .5
    modal = dict(gated=0, duration_seconds=duration, attack_seconds=.003, release_seconds=.02,
        sweep_seconds=0., level=.7, modes=[dict(hz=230., end_hz=230., amplitude=.03,
            phase=.2, decay_seconds=.5)], bands=[])
    shapes = [[.2,.6,1.,.4,.3,.8,.2,.05], [.8,.4,.2,.7,1.,.4,.2,.1],
              [1.,.9,.4,.2,.7,.4,.1,.05], [.8,.2,.6,.9,.3,.1,.3,.05]]
    bands = []
    for edges, shape in zip(EDGES, shapes):
        sos = signal.butter(4, edges, fs=48000, btype='bandpass', output='sos')
        _, h = signal.sosfreqz(sos, worN=65536)
        sigma = float(1/np.sqrt(np.mean(abs(h)**2)/3))
        bands.append(dict(hz=list(edges), sos=sos.tolist(), sigma=sigma,
            seconds=[0., .02, .05, .1, .2, .3, .4, duration],
            gain=(.12*np.array(shape)).tolist()))
    return validate(dict(schema='vsl.event-band-texture/1', sample_rate=48000, modal=modal, bands=bands))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    out = parser.parse_args().output
    out.mkdir(parents=True, exist_ok=False)
    repo = Path(__file__).resolve().parents[1]
    sources = [Path(__file__), repo/'research/startup_band_texture_v1_plan.json',
        *sorted((repo/'tools/event_band_texture').glob('*.py'))]
    for p in sources:
        dest = out/'exact_sources'/p.relative_to(repo)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dest)
    save(out/'report.json', dict(result='running', real_fit_performed=False))
    truth = prescribed()
    # A full source-colour design is also exercised without using a recording.
    f = np.fft.rfftfreq(2048, 1/48000)
    p = .1+np.exp(-.5*((f-900)/110)**2)+.6*np.exp(-.5*((f-7000)/500)**2)
    coloured = deepcopy(truth)
    designs = []
    for b, (low, high) in zip(coloured['bands'], EDGES):
        sos, sigma, radius = fit_colour(f, p, low, high)
        b.update(sos=sos.tolist(), sigma=sigma)
        designs.append(dict(hz=[low, high], pole_radius=radius))
    validate(coloured)
    stationary = carriers(coloured, 8*48000, TRAIN_SEEDS[0])
    variance = np.mean(stationary**2, axis=0)
    assert np.all(abs(10*np.log10(variance)) < .5), variance
    print('known source colours and stationary scale passed', flush=True)
    low = deepcopy(coloured)
    low['modal']['modes'] = []
    for i, b in enumerate(low['bands']):
        b['gain'] = [1. if i == 0 else 0.]*8
    wave = render(low, .5, TRAIN_SEEDS[0])
    energy = powers(wave, 1024).mean(axis=1)
    leakage = float(10*np.log10(energy[4]/energy[1]))
    assert leakage < -30, leakage
    # Independent direct summation versus affine waveform basis.
    seeds = TRAIN_SEEDS
    waves = [render(truth, .5, s) for s in seeds]
    release = render(truth, .65, seeds[0], release_at=.2)
    np.testing.assert_array_equal(release[:9600], waves[0][:9600])
    assert np.max(abs(release[10561:])) == 0
    natural = render(truth, .65, seeds[0])
    np.testing.assert_array_equal(natural[:24000], waves[0])
    assert np.max(abs(natural[24000:])) == 0
    affine = basis(truth, .5, seeds[0])@np.r_[vector(truth), 1.]
    np.testing.assert_allclose(affine, waves[0], atol=1e-14, rtol=1e-13)
    target = np.mean([powers(w, 240)[1:5] for w in waves], axis=0)
    reference = target/target.mean(axis=1)[:, None]
    targets = np.mean([powers(w, 1024).mean(axis=1) for w in waves], axis=0)
    flat = with_vector(truth, np.full(32, .06))
    legacy = []
    for seed in seeds:
        curve = powers(render(flat, .5, seed), 240)[1:5]
        normalized = curve/curve.mean(axis=1)[:, None]
        legacy.append(np.sqrt(np.mean((normalized-reference)**2, axis=1)).tolist())
    response = Response(truth, .5)
    predicted = QuadraticResponse.power(response.temporal, vector(truth))
    actual = np.array([powers(w, 240)[1:5] for w in waves])
    np.testing.assert_allclose(predicted, actual, atol=3e-15, rtol=3e-11)
    problem = SupportProblem(response, vector(flat), reference, list(range(4)), targets, legacy)
    values = np.linspace(.03, .1, 32)
    _, gradient, _, jacobian = problem.evaluate(values)
    ng, nj = np.empty_like(gradient), np.empty_like(jacobian)
    for i in range(32):
        step = np.zeros(32)
        step[i] = 1e-6
        plus, minus = problem.evaluate(values+step), problem.evaluate(values-step)
        ng[i] = (plus[0]-minus[0])/2e-6
        nj[:, i] = (plus[2]-minus[2])/2e-6
    np.testing.assert_allclose(gradient, ng, atol=5e-6, rtol=4e-5)
    np.testing.assert_allclose(jacobian, nj, atol=8e-6, rtol=4e-5)
    print('independent FFT/affine response and derivatives passed', flush=True)
    candidate, fitted = solve(flat, reference, list(range(4)), targets, legacy, .5)
    assert fitted['optimizer_terminated'] and fitted['minimum_constraint'] >= -1e-7, fitted
    assert fitted['objective'] < fitted['initial_objective']*.8, fitted
    refused = []
    for label, change in [('unstable', lambda b: b['bands'][0]['sos'][0].__setitem__(5, 1.1)),
                          ('PCM_field', lambda b: b.__setitem__('samples', [0.])),
                          ('unordered_time', lambda b: b['bands'][0]['seconds'].__setitem__(2, 0.)),
                          ('negative_gain', lambda b: b['bands'][0]['gain'].__setitem__(0, -.1))]:
        invalid = deepcopy(truth)
        change(invalid)
        try:
            validate(invalid)
        except ValueError:
            refused.append(label)
        else:
            raise AssertionError('Invalid profile accepted: '+label)
    runtime = load(Path('E:/VehicleSoundLab/references/analysis/A_exterior_startup_v1/selection1/runtime.json'))
    assert len(runtime) == 459 and all(sha(repo/name) == digest for name, digest in runtime.items())
    save(out/'candidate.json', candidate)
    save(out/'report.json', dict(result='passed', real_fit_performed=False,
        stationary_variance=variance.tolist(), source_colours=designs, low_to_high_leakage_db=leakage,
        affine_max_error=float(np.max(abs(affine-waves[0]))),
        power_max_error=float(np.max(abs(predicted-actual))),
        gradient_max_error=float(np.max(abs(gradient-ng))),
        constraint_J_max_error=float(np.max(abs(jacobian-nj))), known_fit=fitted,
        explicit_release_and_natural_end_silence=True,
        refusals=refused, runtime_files_unchanged=459, goal_complete=False, timbre_accepted=False))
    print('known band texture passed; no real source fit or runtime change', flush=True)


if __name__ == '__main__':
    main()
