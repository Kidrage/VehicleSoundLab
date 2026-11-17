"""Known-only six-band coverage, controllability and feasible-start checks."""
import argparse
from copy import deepcopy
from pathlib import Path
import shutil

import numpy as np

from audit_startup_contour_ensemble_v1 import powers
from event_authoring.measure import observe
from event_authoring.source_support import SupportProblem
from event_authoring.contour_response import QuadraticResponse
from event_spectral_source.filters import EDGES, colour, stationary_matrix
from event_spectral_source.profile import TRAIN_SEEDS, validate, vector, with_vector
from event_spectral_source.voice import innovations, basis, render
from event_spectral_source.measure import curves, observations
from event_spectral_source.design import design
from event_spectral_source.fit import Response, Coordinates, solve
from research_archive_v1 import load, save, sha


def prescribed():
    duration = .65
    time = [0., .025, .06, .12, .24, .37, .52, duration]
    shapes = [[.25,.8,1.,.4,.2,.7,.3,.1], [.8,.4,.2,.9,.8,.3,.5,.1],
              [1.,.7,.3,.2,.7,.4,.1,.05], [.8,.2,.6,.9,.3,.1,.3,.05]]
    modal = dict(gated=0, duration_seconds=duration, attack_seconds=.003, release_seconds=.025,
        sweep_seconds=0., level=.7, bands=[],
        modes=[dict(hz=f, end_hz=f, amplitude=a, phase=.2, decay_seconds=.5)
               for f, a in [(32.,.08),(190.,.08),(670.,.08),(2700.,.08),(7200.,.04),(17000.,.04)]],
        contours=[dict(low_hz=lo, high_hz=hi, seconds=time.copy(), gain=shape.copy())
                  for (lo, hi), shape in zip(((0,300),(300,1200),(1200,4500),(4500,24000)),shapes)])
    frequency = np.fft.rfftfreq(2048, 1/48000)
    psd = .2+np.exp(-.5*((frequency-900)/200)**2)+.5*np.exp(-.5*((frequency-7000)/500)**2)
    bands = []
    for i, (low, high) in enumerate(EDGES):
        band, _ = colour(frequency, psd, low, high)
        band.update(seconds=time.copy(), gain=(.025*np.array(shapes[i % 4])).tolist())
        bands.append(band)
    return validate(dict(schema='vsl.event-spectral-source/1', sample_rate=48000, modal=modal, bands=bands))


def verify_known(out, repo):
    truth = prescribed()
    matrix = stationary_matrix(truth['bands'])
    np.testing.assert_allclose(matrix.sum(axis=0), 1., atol=2e-12)
    assert np.all(np.diag(matrix) > .65)
    stationary = innovations(truth, 8*48000, TRAIN_SEEDS[0])
    variance = np.mean(stationary**2, axis=0)
    assert np.all(abs(10*np.log10(variance)) < 1.), variance
    waves = [render(truth, .65, s) for s in TRAIN_SEEDS]
    for wave in waves:
        _, measured = curves(wave)
        np.testing.assert_allclose(measured, powers(wave, 240), atol=1e-15, rtol=2e-12)
    affine = basis(truth, .65, TRAIN_SEEDS[0])@np.r_[vector(truth), 1.]
    np.testing.assert_allclose(affine, waves[0], atol=2e-14, rtol=2e-12)
    release = render(truth, .8, TRAIN_SEEDS[0], release_at=.2)
    np.testing.assert_array_equal(release[:9600], waves[0][:9600])
    assert np.max(abs(release[10801:])) == 0
    ended = render(truth, .8, TRAIN_SEEDS[0])
    np.testing.assert_array_equal(ended[:len(waves[0])], waves[0])
    assert np.max(abs(ended[len(waves[0]):])) == 0
    # Opposite channels retain full acoustic power in the source initializer.
    source = np.column_stack((waves[0], -waves[0]))
    bg = np.full_like(source, 1e-8)
    _, arrays = observe(source, bg)
    time, measured = observations(source, bg)
    designed, budget = design(truth['modal'], arrays, time, measured, .65)
    assert len(vector(designed)) == 80 and np.isfinite(vector(designed)).all()
    assert designed['modal']['modes'] == truth['modal']['modes']
    assert all(np.array_equal(np.asarray(d['gain']), .8*np.asarray(o['gain'])) for d,o in
               zip(designed['modal']['contours'],truth['modal']['contours']))
    # Modal and noise controls are independent and source-free.
    zero_noise = deepcopy(truth)
    for b in zero_noise['bands']:
        b['gain'] = [0.]*8
    zero_modes = deepcopy(truth)
    for c in zero_modes['modal']['contours']:
        c['gain'] = [0.]*8
    np.testing.assert_allclose(render(zero_noise,.65,TRAIN_SEEDS[0])+render(zero_modes,.65,TRAIN_SEEDS[0]),
                               waves[0],atol=2e-14,rtol=2e-12)
    print('six-band coverage, initializer, independent budgets, finite source/release checks passed', flush=True)
    target = np.mean([powers(w,240)[1:5] for w in waves], axis=0)
    reference = target/target.mean(axis=1)[:, None]
    targets = np.mean([powers(w,1024).mean(axis=1) for w in waves], axis=0)
    flat = deepcopy(truth)
    for c in flat['modal']['contours']:
        c['gain'] = [.45]*len(c['gain'])
    for b in flat['bands']:
        b['gain'] = [.015]*8
    legacy = []
    for seed in TRAIN_SEEDS:
        curve = powers(render(flat,.65,seed),240)[1:5]
        legacy.append(np.sqrt(np.mean((curve/curve.mean(axis=1)[:,None]-reference)**2,axis=1)))
    response = Response(truth,.65)
    predicted = QuadraticResponse.power(response.temporal,vector(truth))
    actual = np.array([powers(w,240)[1:5] for w in waves])
    np.testing.assert_allclose(predicted,actual,atol=5e-15,rtol=4e-11)
    problem = SupportProblem(response,vector(flat),reference,list(range(4)),targets,legacy)
    coordinate = Coordinates(problem,flat)
    z = vector(truth)/coordinate.scale*.9+.1
    _, grad, _, jac = coordinate.evaluate(z)
    ng,nj = np.empty_like(grad),np.empty_like(jac)
    for i in range(len(z)):
        step = np.zeros(len(z));step[i]=1e-6
        plus,minus=coordinate.evaluate(z+step),coordinate.evaluate(z-step)
        ng[i]=(plus[0]-minus[0])/2e-6
        nj[:,i]=(plus[2]-minus[2])/2e-6
    np.testing.assert_allclose(grad,ng,atol=3e-7,rtol=5e-5)
    np.testing.assert_allclose(jac,nj,atol=5e-7,rtol=5e-5)
    candidate,fit=solve(flat,reference,list(range(4)),targets,legacy,.65)
    assert fit['phaseI']['feasible'] and fit['phaseII_executed'],fit
    assert fit['minimum_constraint']>=-1e-7,fit
    assert fit['objective']<fit['initial_objective']*.8,fit
    save(out/'known-candidate.json',candidate)
    print('affine independent FFT/J and prescribed feasible PhaseI/II passed',flush=True)
    # Irreducible constant mode and negligible controllable innovations: a
    # genuine unsupported target must stop before objective optimization.
    impossible=deepcopy(truth)
    impossible['modal']['contours']=[]
    for b in impossible['bands']:
        b['sigma']=1e-20
    _,refused=solve(impossible,reference,list(range(4)),targets*1e-6,legacy,.65,seeds=TRAIN_SEEDS[:1])
    assert not refused['phaseI']['feasible'] and not refused['phaseII_executed'],refused
    invalid=[]
    for label,change in [('PCM',lambda p:p.__setitem__('samples',[0.])),
        ('unstable',lambda p:p['bands'][0]['sos'][0].__setitem__(5,1.1)),
        ('gain',lambda p:p['modal']['contours'][0]['gain'].__setitem__(0,-.1))]:
        p=deepcopy(truth);change(p)
        try:validate(p)
        except ValueError:invalid.append(label)
        else:raise AssertionError('Invalid spectral profile accepted: '+label)
    runtime=load(Path('E:/VehicleSoundLab/references/analysis/A_exterior_startup_v1/selection1/runtime.json'))
    assert len(runtime)==459 and all(sha(repo/name)==digest for name,digest in runtime.items())
    return dict(result='passed',real_fit_performed=False,stationary_variance=variance.tolist(),
        spectral_coverage_matrix=matrix.tolist(),source_design=budget,known_fit=fit,infeasible_stop=refused,
        invalid_refused=invalid,affine_error_FS=float(np.max(abs(affine-waves[0]))),
        power_error=float(np.max(abs(predicted-actual))),gradient_error=float(np.max(abs(grad-ng))),
        constraint_J_error=float(np.max(abs(jac-nj))),finite_release_end_pass=True,
        modal_noise_controls_independent=True,opposite_channels_preserve_power=True,
        runtime_voice_files_unchanged=459,goal_complete=False,timbre_accepted=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    out=parser.parse_args().output
    out.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1]
    for p in [Path(__file__),repo/'research/event_spectral_budget_v1_plan.json',
              *sorted((repo/'tools/event_spectral_source').glob('*.py'))]:
        dest=out/'exact_sources'/p.relative_to(repo);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
    try:
        report=verify_known(out,repo)
    except Exception as error:
        save(out/'report.json',dict(result='failed',error=repr(error),real_fit_performed=False,
                                    goal_complete=False,timbre_accepted=False))
        raise
    save(out/'report.json',report)
    print('known six-band and modal-budget verification passed; no real fit or C change',flush=True)


if __name__=='__main__':main()
