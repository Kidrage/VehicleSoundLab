"""Audit joint nuisance pairs against parent arrays and every original trust subproblem."""
import argparse
import json
from pathlib import Path
import shutil
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--native', type=Path, required=True)
parser.add_argument('--parent', type=Path, required=True)
parser.add_argument('--candidate', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(args.workspace/'tools/python_deps'))
import numpy as np
from drive_evidence_v1.sources import sha
from quintic_phase_v1.model import QuinticAbsoluteModel
from joint_nuisance_pair_v1.model import FixedClockModel, from_original
from joint_nuisance_pair_v1.audit import trace


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.joint-nuisance-pair-audit/1', result='running', sources={},
    real_audio_read=False, truth_used=False, heldout_used=False, phase_estimator_run=False,
    large_QPs_rerun=False, phase_estimator_qualified=False, model_exported=False, runtime_changed=False)
try:
    candidate = load(args.candidate/'report.json')
    assert candidate['result'] == 'finite_joint_nuisance_pairs_measured_not_global_minima'
    assert candidate['parent_report_sha256'] == sha(args.parent/'report.json')
    paths = {Path(__file__), repo/'tools/joint_nuisance_pair_v1/audit.py'}
    for relative, digest in candidate['sources'].items():
        assert sha(repo/relative) == sha(args.candidate/'exact_sources'/relative) == digest
        paths.add(repo/relative)
    for path in paths:
        relative = path.relative_to(repo)
        destination = args.out/'exact_sources'/relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        report['sources'][relative.as_posix()] = sha(path)
    for filename, key in [('input.npz', 'native_input_sha256'), ('effective_plan.json', 'native_plan_sha256'),
                          ('effective_settings.json', 'native_settings_sha256')]:
        assert sha(args.native/filename) == candidate[key]
    settings = load(args.native/'effective_settings.json')
    time = np.arange(256)/128
    angle = 2*np.pi*time[:, None]*np.array([1., 2.])[None, :]
    basis = (.5+.25*np.cos(2*np.pi*time))[:, None]
    specs = [
        ('orthogonal_interior', np.zeros((len(time), 0)), np.array([.4, -.2]), np.array([.4, -.2])),
        ('orthogonal_coefficient_bounds', np.zeros((len(time), 0)), np.array([1.3, -1.4]), np.array([1., -1.])),
        ('bilinear_phase_envelope', basis, np.array([.42, .18, .08]), np.array([.42, .18, .08]))]
    controls = []
    for (name, envelope, truth, expected), row in zip(specs, candidate['controls']['cases']):
        assert name == row['id']
        small = FixedClockModel(np.cos(angle[:, :1]), np.sin(angle[:, :1]), envelope, .25)
        initial = np.array([.4, .2, .1]) if envelope.shape[1] else np.zeros(2)
        actual, audit = trace(small, small.samples(truth), initial, row['fit'], settings)
        assert np.array_equal(actual, np.asarray(row['final_parameters']))
        assert float(abs(actual-expected).max()) == row['maximum_parameter_error'] <= 1e-7
        controls.append(dict(id=name, audit=audit, parameter_gate_passed=True))
    inputs = np.load(args.native/'input.npz')
    plan = load(args.native/'effective_plan.json')
    variant = load(repo/'research/minority_phase_v1_plan.json')
    original = QuinticAbsoluteModel(inputs['time'], plan, variant, [])
    target = original.original.samples(inputs['initial_parameters'])[0]
    cases = []
    for row in candidate['cases']:
        key = row['id']
        saved = np.load(args.candidate/(key+'.npz'))
        parent = np.load(args.parent/(key+'.npz'))
        assert sha(args.candidate/(key+'.npz')) == row['arrays_sha256']
        assert np.array_equal(saved['initial_parameters'], parent['parameters'])
        assert np.array_equal(saved['target'], target) and np.array_equal(saved['time'], inputs['time'])
        fixed, initial, indices = from_original(original, parent['parameters'])
        assert np.array_equal(initial, saved['initial_nuisance_parameters'])
        assert np.array_equal(indices, saved['nuisance_indices']) and len(indices) == 648
        def independent(x):
            parameters = parent['parameters'].copy()
            parameters[indices] = x
            values, derivative = original.original.samples(parameters, True)
            return values, derivative[:, indices]
        actual, audit = trace(fixed, target, initial, row['fit'], settings, independent)
        assert np.array_equal(actual, saved['nuisance_parameters'])
        parameters = parent['parameters'].copy()
        parameters[indices] = actual
        assert np.array_equal(parameters, saved['parameters'])
        waveform, phase, envelope = original.original.samples(parameters)
        assert np.array_equal(waveform, saved['waveform'])
        assert np.array_equal(phase, original.original.samples(parent['parameters'])[1])
        lower, upper = original.original.bounds(plan, variant)
        violation = float(max(0., (lower-parameters).max(), (parameters-upper).max()))
        assert violation == row['original_parameter_violation'] <= settings['maximum_primal_violation']
        assert envelope.min() == row['minimum_envelope'] > 0
        assert np.diff(inputs['time']+phase).min() == row['minimum_coordinate_step'] > 0
        assert float(np.linalg.norm(waveform-target)) == row['raw_difference_norm_after']
        cases.append(dict(id=key, audit=audit, final_parameters_and_waveforms_exact=True,
            common_phase_original_bounds_positive_monotonic_verified=True))
    prior = args.workspace/'references/analysis/bounded_envelope_pair_v1/final1'
    for filename in ('C_files_sha256.json', 'voice_files_sha256.json'):
        assert all(sha(repo/path) == digest for path, digest in load(prior/filename).items())
    report.update(result='joint_nuisance_all_trust_steps_certificates_controls_and_fixed_clocks_reconstructed',
        candidate_report_sha256=sha(args.candidate/'report.json'), cases=cases, controls=controls,
        C_H=540, voices_and_moving35_unchanged=True, all_actual40_steps_audited=True,
        limitations=candidate['limitations'])
    print(json.dumps(dict(result=report['result'], actual_steps=sum(len(row['audit']['rows']) for row in cases))), flush=True)
except Exception as exc:
    report.update(result='failed', error=repr(exc))
    raise
finally:
    (args.out/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')
