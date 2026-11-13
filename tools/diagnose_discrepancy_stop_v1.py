"""Evaluate one observed-noise discrepancy rule on an independently audited prefix."""
import argparse
import json
from pathlib import Path
import shutil
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--parent', type=Path, required=True)
parser.add_argument('--noise', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(args.workspace/'tools/python_deps'))
import numpy as np
from drive_evidence_v1.sources import sha
from quintic_phase_v1.model import QuinticAbsoluteModel
from aperture_model_v1.forward import real_rows
from aperture_model_v1.checks import assess
from smooth_envelope_v1.covariance import covariance_trace
from bounded_phase_noise_v1.noise import estimate
from bounded_phase_noise_v1.discrepancy import first_crossing, controls


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')


args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.discrepancy-stop-diagnosis/1', result='running', sources={},
    real_audio_read=False, real_source_permitted=False, qualification_changed=False,
    nonlinear_estimator_rerun=False, quadratic_solver_rerun=False, runtime_changed=False)
try:
    parent, noise = load(args.parent/'report.json'), load(args.noise/'report.json')
    audit = load(args.parent.parent/'audit1/report.json')
    assert audit['entire_trace_exact'] and audit['qp_certified'] == 20
    assert noise['parent_report_sha256'] == sha(args.parent/'report.json')
    sources = {Path(__file__), repo/'research/discrepancy_stop_v1_plan.json',
        repo/'tools/bounded_phase_noise_v1/discrepancy.py', repo/'tools/smooth_envelope_v1/covariance.py'}
    for folder, value in ((args.parent, parent), (args.noise, noise)):
        for relative, digest in value['sources'].items():
            assert sha(repo/relative) == sha(folder/'exact_sources'/relative) == digest
            sources.add(repo/relative)
    for path in sources:
        relative = path.relative_to(repo)
        target = args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        report['sources'][relative.as_posix()] = sha(path)
    settings = load(repo/'research/discrepancy_stop_v1_plan.json')
    assert settings['noise_multiplier'] == 1.
    report['controls'] = controls()
    report['parent_report_sha256'] = sha(args.parent/'report.json')
    report['noise_report_sha256'] = sha(args.noise/'report.json')
    plan = load(args.parent/'effective_plan.json')
    variant = load(repo/'research/minority_phase_v1_plan.json')
    original = np.load(args.parent/'fit.npz')
    observed = np.load(args.noise/'input.npz')
    assert np.array_equal(original['time'], observed['time'])
    assert np.array_equal(original['initial_parameters'], observed['initial_parameters'])
    time, audio = observed['time'], observed['original_observed_audio']
    model = QuinticAbsoluteModel(time, plan, variant, [])
    target = real_rows(model.original.aperture.apply(audio[:, 0]))
    noise_plan = load(repo/'research/bounded_phase_noise_v1_plan.json')
    proxy = estimate(audio[:, 0], noise_plan['noise_proxy_nyquist_fraction'], noise_plan['minimum_noise_bins'])
    assert proxy == noise['noise_proxy']
    def candidates():
        outer, amplitudes = model.unpack(original['initial_parameters'])
        yield dict(iteration=0, accepted=True, outer=outer, amplitudes=amplitudes,
            observed_residual=model.prediction(outer, amplitudes)-target)
        for row in parent['fit']['history']:
            if row['accepted']:
                outer = np.asarray(row['candidate_outer'])
                amplitudes = np.asarray(row['candidate_absolute_amplitudes'])
                yield dict(iteration=row['iteration'], accepted=True, outer=outer, amplitudes=amplitudes,
                    observed_residual=model.prediction(outer, amplitudes)-target)
    trace = covariance_trace(model.original.aperture)
    selected, evidence = first_crossing(candidates(), proxy['variance'], trace)
    report.update(selection=evidence, noise_proxy=proxy, aperture_covariance_trace=trace)
    assert selected is not None, 'No discrepancy crossing in the original finite trace'
    parameters = model.pack(selected['outer'], selected['amplitudes'])
    _, phase, envelope = model.original.samples(parameters)
    lower, upper = model.original.bounds(plan, variant)
    violation = float(max(np.max(lower-parameters), np.max(parameters-upper), 0.))
    assert violation <= 1e-9 and envelope.min() > 0 and np.diff(time+phase).min() > 0
    # Fixture truth and heldout identities are first accessed after the observed
    # stopping prefix has been fixed. They never enter first_crossing.
    base = load(repo/'research/aperture_model_v1_plan.json')
    assessment, positions, oracle = assess(audio, time, original['true_phase_correction'], phase, parameters,
        {**plan, 'heldout_orders': base['heldout_orders']})
    np.savez_compressed(args.out/'selected.npz', parameters=parameters, phase_correction=phase,
        positions=positions, oracle_positions=oracle)
    report.update(result='discrepancy_prefix_passed_not_full_qualification' if assessment['qualified'] else 'discrepancy_prefix_rejected',
        assessment=assessment, normalized_projection_residual=float(np.linalg.norm(selected['observed_residual'])/np.linalg.norm(target)),
        original_parameter_bound_violation=violation, selected_after_observed_only_decision=True,
        expected_energy_not_confidence_bound=True, full_qualification=False,
        limits=['One predeclared mean-noise-energy crossing is not a calibrated real-audio confidence procedure',
            'This is an exact prefix selection of the original fit, not a fresh nonlinear solve or a multiplier sweep',
            'All17/full33/individual14kHz/original E remain required; no new real model/C/audio'])
    print(json.dumps({key: report[key] for key in ('result', 'selection', 'assessment')}), flush=True)
except Exception as exc:
    report.update(result='failed', error=repr(exc))
    raise
finally:
    save(args.out/'report.json', report)
