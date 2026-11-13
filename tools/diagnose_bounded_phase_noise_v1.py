"""Two fixed antithetic observation perturbations through the actual bounded fit."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import time as timer

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--parent', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(args.workspace/'tools/ipm_deps'), str(args.workspace/'tools/qp_deps'),
    str(args.workspace/'tools/python_deps')]
import numpy as np
import scipy
import clarabel
from drive_evidence_v1.sources import sha
from observed_topology_v1.fixtures import make
from quintic_phase_v1.model import QuinticAbsoluteModel
from aperture_model_v1.forward import real_rows
from aperture_model_v1.checks import assess
from joint_trust_v1.fit import estimate_with_model, scales_from_observation
from interior_qp_v1.certified import CertifiedObservedSolver
from bounded_phase_noise_v1.noise import estimate as estimate_noise
from bounded_phase_noise_v1.checks import controls


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')


args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.bounded-phase-noise-diagnosis/1', result='running', sources={}, cases=[],
    real_audio_read=False, real_source_permitted=False, qualification_changed=False,
    runtime_changed=False, sensitivity_is_qualification=False)
try:
    parent = load(args.parent/'report.json')
    assert parent['result'] == 'dense_diagnostic_rejected' and parent['qp_certified'] == 20
    report['parent_report_sha256'] = sha(args.parent/'report.json')
    setting_path = repo/'research/bounded_phase_noise_v1_plan.json'
    settings, chain = {}, []
    path = setting_path
    while True:
        value = load(path)
        chain.append((path, value))
        if path == repo/'research/joint_trust_precise_v1_plan.json':
            break
        path = repo/value['parent_plan']
    for _, value in reversed(chain):
        settings.update(value)
    sources = {Path(__file__)} | {path for path, _ in chain} | {repo/name for name in parent['sources']}
    sources.update((repo/'tools/bounded_phase_noise_v1').glob('*.py'))
    for name, digest in parent['sources'].items():
        assert sha(repo/name) == sha(args.parent/'exact_sources'/name) == digest
    for path in sources:
        relative = path.relative_to(repo)
        target = args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        report['sources'][relative.as_posix()] = sha(path)
    report['numeric_libraries'] = dict(numpy=np.__version__, scipy=scipy.__version__, clarabel=clarabel.__version__)
    assert report['numeric_libraries'] == parent['numeric_libraries']
    report['controls'] = controls(settings)
    save(args.out/'controls.json', report['controls'])
    topology = load(repo/'research/observed_topology_v1_plan.json')
    base, variant = load(repo/topology['base_plan']), load(repo/topology['minority_plan'])
    case = next(row for row in topology['added_cases'] if row['id'] == 'unknown_thirty_six')
    time, audio, truth, _ = make(case, base)
    plan = load(args.parent/'effective_plan.json')
    save(args.out/'effective_plan.json', plan)
    saved = np.load(args.parent/'fit.npz')
    assert np.array_equal(time, saved['time']) and np.array_equal(truth, saved['true_phase_correction'])
    initial = saved['initial_parameters']
    model = QuinticAbsoluteModel(time, plan, variant, [])
    target = real_rows(model.original.aperture.apply(audio[:, 0]))
    outer, absolute = model.unpack(initial)
    assert np.array_equal(np.asarray(parent['fit']['scales']),
        scales_from_observation(model, outer, absolute, target, plan['soft_l1_scale']))
    # Verify the original input too: the old mother trace is not a substitute
    # for source/target identity. Its first saved cost is reconstructed here.
    from absolute_amplitude_v1.amplitude import cost
    assert cost(model.prediction(outer, absolute)-target, plan['soft_l1_scale']) == parent['fit']['initial_cost']
    report['zero_case_reuse'] = dict(parent_report_sha256=sha(args.parent/'report.json'),
        estimator_sources_libraries_model_plan_time_initial_target_scales_exact=True,
        nonlinear_estimator_rerun=False, truth_used_for_initialization=False)
    report['noise_proxy'] = estimate_noise(audio[:, 0], settings['noise_proxy_nyquist_fraction'], settings['minimum_noise_bins'])
    rng = np.random.default_rng(settings['perturbation_seed'])
    perturbation = rng.normal(size=len(time))*report['noise_proxy']['standard_deviation']
    np.savez_compressed(args.out/'input.npz', time=time, original_observed_audio=audio,
        added_source_noise=perturbation, initial_parameters=initial)
    print(json.dumps(dict(status='controls_passed', observed_sigma_proxy=report['noise_proxy']['standard_deviation'],
        zero_fit_reused=True)), flush=True)
    phases = {}
    for sign in settings['perturbation_signs']:
        folder = args.out/('minus' if sign < 0 else 'plus')
        folder.mkdir()
        perturbed = audio.copy()
        perturbed[:, 0] += sign*perturbation
        target = real_rows(model.original.aperture.apply(perturbed[:, 0]))
        solver = CertifiedObservedSolver(target, plan['soft_l1_scale'])
        started = timer.perf_counter()
        def progress(row):
            save(folder/'progress.json', row)
            print(json.dumps(dict(sign=sign, iteration=row['iteration'], accepted=row['accepted'],
                qp_certified=row['qp']['success'], cost=row['candidate_cost'])), flush=True)
        parameters, phase, fit = estimate_with_model(model, perturbed, time, plan, variant,
            settings, initial, progress, qp_solver=solver)
        fit['seconds'] = timer.perf_counter()-started
        np.savez_compressed(folder/'fit.npz', parameters=parameters, phase_correction=phase)
        result = dict(sign=sign, fit=fit, qp_certified=sum(row['qp']['success'] for row in fit['history']))
        if fit['observation_supported']:
            result['assessment'], positions, oracle = assess(perturbed, time, truth, phase, parameters,
                {**plan, 'heldout_orders': base['heldout_orders']})
            np.savez_compressed(folder/'coordinates.npz', positions=positions, oracle_positions=oracle)
        phases[sign] = phase
        report['cases'].append(result)
        save(folder/'report.json', result)
        save(args.out/'progress_report.json', report)
    interior = (time >= 5)&(time < 35)
    def metrics(values):
        aligned = values-np.median(values[interior])
        return dict(p95_cycles=float(np.percentile(abs(aligned[interior]), 95)),
            RMS_cycles=float(np.sqrt(np.mean(aligned[interior]**2))))
    report['sensitivity'] = dict(
        minus_vs_zero=metrics(phases[-1]-saved['phase_correction']),
        plus_vs_zero=metrics(phases[1]-saved['phase_correction']),
        antisymmetric_response=metrics((phases[1]-phases[-1])/2),
        symmetric_drift=metrics((phases[1]+phases[-1])/2-saved['phase_correction']))
    report.update(result='bounded_antithetic_observation_sensitivity_measured',
        all_QPs_certified=all(row['qp_certified'] == row['fit']['iterations'] for row in report['cases']),
        original_phase_gate=plan['rules']['maximum_point_phase_p95_cycles'],
        limits=['Finite additional observed-noise response is not a real-recording uncertainty interval or an unavoidable-error bound',
            'Upper-band proxy assumes white noise; engine high-frequency texture/coloured noise are not calibrated by this diagnostic',
            'No perturbed candidate is selected as an estimator or a new vehicle timbre',
            'Both signs retain the same original bounds/controller/initialization; original dense positive and all17/full33/individual14kHz/original E remain required'])
    print(json.dumps(dict(result=report['result'], all_QPs_certified=report['all_QPs_certified'], sensitivity=report['sensitivity'])), flush=True)
except Exception as exc:
    report.update(result='failed', error=repr(exc))
    raise
finally:
    save(args.out/'report.json', report)
