"""One observed-noise-budget common-phase candidate, with all original gates."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import time as timer

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--parent', type=Path, required=True)
parser.add_argument('--noise', type=Path, required=True)
parser.add_argument('--start', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(args.workspace/'tools/ipm_deps'), str(args.workspace/'tools/qp_deps'),
    str(args.workspace/'tools/python_deps')]
import numpy as np
import scipy
import clarabel
from drive_evidence_v1.sources import sha
from quintic_phase_v1.model import QuinticAbsoluteModel
from aperture_model_v1.checks import assess
from aperture_model_v1.forward import real_rows
from smooth_envelope_v1.covariance import covariance_trace
from bounded_phase_noise_v1.noise import estimate as estimate_noise
from noise_budget_phase_v1.roughness import build, controls as roughness_controls
from noise_budget_phase_v1.conic import controls as conic_controls
from noise_budget_phase_v1.fit import estimate


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')


args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.noise-budget-phase-diagnosis/1', result='running', sources={},
    real_audio_read=False, real_source_permitted=False, qualification_changed=False,
    runtime_changed=False, model_exported=False, audio_exported=False)
try:
    parent, noise, start = (load(path/'report.json') for path in (args.parent, args.noise, args.start))
    start_audit = load(args.start.parent/'discrepancy_audit1/report.json')
    assert start_audit['candidate_report_sha256'] == sha(args.start/'report.json')
    assert start_audit['observed_only_crossing_exact'] and start_audit['selected_parameters_phase_and_assessment_exact']
    assert noise['parent_report_sha256'] == start['parent_report_sha256'] == sha(args.parent/'report.json')
    settings, chain = {}, []
    path = repo/'research/noise_budget_phase_v1_plan.json'
    while True:
        value = load(path)
        chain.append((path, value))
        if path == repo/'research/joint_trust_precise_v1_plan.json':
            break
        path = repo/value['parent_plan']
    for _, value in reversed(chain):
        settings.update(value)
    sources = {Path(__file__)} | {path for path, _ in chain}
    sources.update((repo/'tools/noise_budget_phase_v1').glob('*.py'))
    sources.add(repo/'tools/smooth_envelope_v1/covariance.py')
    for folder, value in ((args.parent, parent), (args.noise, noise), (args.start, start)):
        for relative, digest in value['sources'].items():
            assert sha(repo/relative) == sha(folder/'exact_sources'/relative) == digest
            sources.add(repo/relative)
    for path in sources:
        relative = path.relative_to(repo)
        target = args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        report['sources'][relative.as_posix()] = sha(path)
    report['numeric_libraries'] = dict(numpy=np.__version__, scipy=scipy.__version__, clarabel=clarabel.__version__)
    assert report['numeric_libraries'] == parent['numeric_libraries']
    report['controls'] = dict(roughness=roughness_controls(), conic=conic_controls(settings))
    save(args.out/'controls.json', report['controls'])
    observed = np.load(args.noise/'input.npz')
    saved = np.load(args.parent/'fit.npz')
    initial = np.load(args.start/'selected.npz')['parameters']
    assert np.array_equal(observed['time'], saved['time'])
    time, audio = observed['time'], observed['original_observed_audio']
    plan = load(args.parent/'effective_plan.json')
    variant = load(repo/'research/minority_phase_v1_plan.json')
    model = QuinticAbsoluteModel(time, plan, variant, [])
    noise_plan = load(repo/'research/bounded_phase_noise_v1_plan.json')
    proxy = estimate_noise(audio[:, 0], noise_plan['noise_proxy_nyquist_fraction'], noise_plan['minimum_noise_bins'])
    assert proxy == noise['noise_proxy'] and settings['noise_energy_multiplier'] == 1.
    noise_radius = float(np.sqrt(proxy['variance']*covariance_trace(model.original.aperture)))
    assert abs(noise_radius**2/start['selection']['expected_noise_energy']-1) < 1e-12
    outer, amplitude = model.unpack(initial)
    roughness, roughness_evidence = build(plan, model, outer)
    np.savez_compressed(args.out/'input.npz', time=time, audio=audio, initial_parameters=initial,
        roughness=roughness, noise_radius=np.array(noise_radius))
    save(args.out/'effective_plan.json', plan)
    save(args.out/'effective_settings.json', settings)
    report.update(parent_report_sha256=sha(args.parent/'report.json'),
        noise_report_sha256=sha(args.noise/'report.json'), start_report_sha256=sha(args.start/'report.json'),
        start_audit_sha256=sha(args.start.parent/'discrepancy_audit1/report.json'),
        observed_noise_proxy=proxy, noise_radius=noise_radius, roughness=roughness_evidence,
        initialization='Frozen first discrepancy crossing chosen from observations only',
        objective='minimum integrated squared common-phase third derivative within observed noise energy')
    print(json.dumps(dict(status='independent_controls_passed', noise_radius=noise_radius,
        original_initial_phase_p95=start['assessment']['point_phase_p95_cycles'])), flush=True)
    def progress(row):
        save(args.out/'progress.json', row)
        print(json.dumps(dict(iteration=row['iteration'], accepted=row['accepted'],
            conic_certified=row['subproblem']['success'], native=row['subproblem']['native_status'],
            roughness=row['candidate_roughness'], noise_violation=row['candidate_noise_violation'])), flush=True)
    started = timer.perf_counter()
    parameters, phase, fit = estimate(model, audio, plan, variant, settings, initial,
        roughness, noise_radius, progress)
    fit['seconds'] = timer.perf_counter()-started
    report['fit'] = fit
    np.savez_compressed(args.out/'fit.npz', parameters=parameters, phase_correction=phase)
    # Fixture phase and spectral heldout identities are used only now, after
    # the observation-only candidate and all its control decisions are fixed.
    base = load(repo/'research/aperture_model_v1_plan.json')
    assessment, positions, oracle = assess(audio, time, saved['true_phase_correction'], phase, parameters,
        {**plan, 'heldout_orders': base['heldout_orders']})
    report['assessment'] = assessment
    np.savez_compressed(args.out/'coordinates.npz', positions=positions, oracle_positions=oracle)
    qualified = assessment['qualified'] and fit['observation_supported'] and fit['noise_budget_feasible']
    report.update(result='dense_noise_budget_candidate_passed_not_full_qualification' if qualified else 'dense_noise_budget_candidate_rejected',
        all_conic_subproblems_certified=fit['conic_subproblems_certified'] == fit['iterations'],
        full_qualification=False, original_gates_unchanged=True,
        limits=['The noise budget is expected white-noise energy, not real-engine noise calibration or a confidence bound',
            'Minimum common-phase jerk changes the estimator objective, not the original phase/amplitude model or evaluation gates',
            'Finite dual-merit SQP steps do not prove nonlinear/global convergence',
            'Original failed dense positive/all17/full33/individual14kHz/original E remain required; no new real model/C/audio'])
    print(json.dumps(dict(result=report['result'], certified=fit['conic_subproblems_certified'],
        iterations=fit['iterations'], phase_p95=assessment['point_phase_p95_cycles'],
        noise_ratio=fit['final_noise_ratio'])), flush=True)
except Exception as exc:
    report.update(result='failed', error=repr(exc))
    raise
finally:
    save(args.out/'report.json', report)
