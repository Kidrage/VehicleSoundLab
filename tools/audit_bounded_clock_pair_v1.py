"""Reconstruct finite pairs, independent Gaussian distances and the retained JSON failure."""
import argparse
import json
import math
from pathlib import Path
import shutil
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--native', type=Path, required=True)
parser.add_argument('--candidate', type=Path, required=True)
parser.add_argument('--failed', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(args.workspace/'tools/python_deps'))
import numpy as np
from scipy.stats import norm
from drive_evidence_v1.sources import sha
from quintic_phase_v1.model import QuinticAbsoluteModel
from bounded_clock_pair_v1.pair import construct
from bounded_clock_pair_v1.checks import check


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def native_numbers(value):
    if isinstance(value, dict):
        return {key: native_numbers(item) for key, item in value.items()}
    if isinstance(value, list):
        return [native_numbers(item) for item in value]
    return value.item() if isinstance(value, np.generic) else value


args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.bounded-clock-pair-audit/1', result='running', sources={},
    real_audio_read=False, truth_used=False, heldout_used=False, nonlinear_estimator_run=False,
    linear_pair_construction_replayed=True, phase_estimator_qualified=False,
    model_exported=False, runtime_changed=False)
try:
    candidate = load(args.candidate/'report.json')
    assert candidate['result'] == 'finite_bounded_clock_pairs_measured_not_phase_qualification'
    assert sha(args.native/'input.npz') == candidate['native_input_sha256']
    assert sha(args.native/'effective_plan.json') == candidate['native_plan_sha256']
    paths = {Path(__file__)}
    for relative, digest in candidate['sources'].items():
        assert sha(repo/relative) == sha(args.candidate/'exact_sources'/relative) == digest
        paths.add(repo/relative)
    for path in paths:
        relative = path.relative_to(repo)
        target = args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        report['sources'][relative.as_posix()] = sha(path)
    plan = load(args.native/'effective_plan.json')
    inputs = np.load(args.native/'input.npz')
    model = QuinticAbsoluteModel(inputs['time'], plan, load(repo/'research/minority_phase_v1_plan.json'), [])
    rows, saved, construction = construct(model, inputs['initial_parameters'], plan)
    assert construction == candidate['construction']
    saved_input = np.load(args.candidate/'pairs.npz')
    failed_input = np.load(args.failed/'pairs.npz')
    assert set(saved) == set(saved_input.files) == set(failed_input.files)
    assert all(np.array_equal(value, saved_input[key]) and np.array_equal(value, failed_input[key])
               for key, value in saved.items())
    current_controls = check(model, inputs['initial_parameters'], plan, rows, saved)
    assert current_controls == candidate['controls']
    old_path = args.failed/'exact_sources/tools/bounded_clock_pair_v1/checks.py'
    original_source = old_path.read_text(encoding='utf-8')
    assert original_source.replace('columns=rank)', 'columns=int(rank))') == (repo/'tools/bounded_clock_pair_v1/checks.py').read_text(encoding='utf-8')
    namespace = dict(__name__='bounded_clock_pair_v1.old_checks', __package__='bounded_clock_pair_v1')
    exec(compile(original_source, str(old_path), 'exec'), namespace)
    old_controls = namespace['check'](model, inputs['initial_parameters'], plan, rows, saved)
    assert native_numbers(old_controls) == current_controls
    try:
        json.dumps(old_controls)
    except TypeError as exc:
        failure = dict(type=type(exc).__name__, message=str(exc))
    else:
        raise AssertionError('Preserved NumPy-integer serialization failure did not reproduce')
    assert not (args.failed/'report.json').exists()
    recovered = load(args.failed/'recovered_failure.json')
    assert recovered['recovered_metadata'] and not recovered['original_report_saved']
    for name, digest in recovered['numeric_artifacts_retained'].items():
        assert sha(args.failed/name) == digest
    independent = []
    for row, key, published in zip(rows, ('minus', 'plus'), candidate['cases']):
        assert all(row[name] == published[name] for name in row)
        difference = saved[key+'_waveform']-saved['base_waveform']
        squared = math.fsum(float(value*value) for value in difference)
        distance = math.sqrt(squared)/published['known_raw_white_sigma']
        distance_error = abs(distance-published['fixed_pair_raw_Gaussian_distance'])
        probability_error = abs(float(norm.logcdf(-distance/2))-published['fixed_pair_equal_prior_log_binary_error'])
        assert distance_error <= 1e-12 and probability_error <= 1e-12
        independent.append(dict(sign=row['sign'], scalar_raw_Gaussian_distance=distance,
            norm_implementation_error=distance_error, log_probability_implementation_error=probability_error))
    prior = args.workspace/'references/analysis/model_score_v1/final1'
    for name in ('C_files_sha256.json', 'voice_files_sha256.json'):
        assert all(sha(repo/path) == digest for path, digest in load(prior/name).items())
    report.update(result='finite_pairs_controls_and_original_serialization_failure_independently_reconstructed',
        candidate_report_sha256=sha(args.candidate/'report.json'), pairs_and_controls_exact=True,
        failed_attempt_all_arrays_exact=True, preserved_failure_reproduced=failure,
        independent_Gaussian_checks=independent, C_H=540, voices_and_moving35_unchanged=True,
        limitations=['Diagnostic pair coefficient solves only; no actual common-phase recovery or global identifiability guarantee',
            'Original absent report is explicitly recovered failure metadata, not an original successful result'])
    print(json.dumps(dict(result=report['result'], independent_checks=independent, failure=failure)), flush=True)
except Exception as exc:
    report.update(result='failed', error=repr(exc))
    raise
finally:
    (args.out/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n',
                                      encoding='utf-8', newline='\n')
