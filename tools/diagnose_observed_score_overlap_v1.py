"""Trace frozen observed initialization and exact cross-window score covariance."""
import argparse
import json
from pathlib import Path
import shutil
import sys

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
args = p.parse_args(); repo = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(args.workspace/'tools/ipm_deps'), str(args.workspace/'tools/qp_deps'), str(args.workspace/'tools/python_deps')]
import numpy as np
from drive_evidence_v1.sources import sha
from aperture_model_v1.forward import Aperture
from correlated_observation_v1.marginal import MarginalAperture
from quintic_phase_v1.model import QuinticAbsoluteModel
from positive_band_envelope_v1.model import BandModel
from observed_score_overlap_v1.checks import controls
from observed_score_overlap_v1.measure import phase_samples, measure


def load(path): return json.loads(path.read_text(encoding='utf-8'))
def save(path, value): path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')


args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.observed-score-overlap/1', result='running', sources={}, cases=[],
    real_audio_read=False, truth_read=False, heldout_used=False, estimator_rerun=False,
    model_exported=False, runtime_changed=False, full_qualification=False)
try:
    source = {Path(__file__), repo/'research/observed_score_overlap_v1_plan.json',
        repo/'research/minority_phase_v1_plan.json', repo/'tools/drive_evidence_v1/sources.py'}
    for name in ('observed_score_overlap_v1', 'aperture_model_v1', 'minority_phase_v1',
            'positive_band_envelope_v1', 'quintic_phase_v1', 'absolute_amplitude_v1',
            'complex_radial_v1', 'correlated_observation_v1', 'native_observation_v1'):
        source.update((repo/'tools'/name).glob('*.py'))
    for path in source:
        relative = path.relative_to(repo); target = args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path, target)
        report['sources'][relative.as_posix()] = sha(path)
    # Small controls complete before any actual observed state is read.
    report['controls'] = controls(); save(args.out/'controls.json', report['controls'])
    root = args.workspace/'references/analysis'
    names = ['complex_radial_v1/fit1', 'correlated_observation_v1/fit1', 'native_observation_v1/fit1',
        'interior_qp_v1/fit1', 'quintic_phase_v1/dense1', 'absolute_amplitude_v1/dense1',
        'guard_observation_v1/band1', 'guard_observation_v1/dense1', 'observed_topology_v1/validate2']
    chain = []; previous = None
    for name in names:
        path = root/name/'report.json'; value = load(path)
        if previous is not None: assert previous['parent_report_sha256'] == sha(path)
        chain.append(dict(path=str(path.relative_to(args.workspace).as_posix()), sha256=sha(path), result=value['result']))
        previous = value
    report['parent_report_chain'] = chain
    parent = root/names[0]; saved = np.load(parent/'input.npz')
    time, audio, initial = (saved[k] for k in ('time', 'audio', 'initial_parameters'))
    final = np.load(parent/'fit.npz')['parameters']; plan = load(parent/'effective_plan.json')
    variant = load(repo/'research/minority_phase_v1_plan.json')
    model = QuinticAbsoluteModel(time, plan, variant, []).original
    report['input_identities'] = []
    for name, filename in ((names[1], 'input.npz'), (names[2], 'input.npz'),
            (names[3], 'fit.npz'), (names[4], 'fit.npz')):
        path = root/name/filename; data = np.load(path)
        assert np.array_equal(initial, data['initial_parameters'])
        report['input_identities'].append(dict(path=path.relative_to(args.workspace).as_posix(),
            sha256=sha(path), array='initial_parameters', exact=True))
    quintic = np.load(root/names[4]/'fit.npz'); old = np.load(root/names[5]/'fit.npz')['parameters']
    assert np.array_equal(quintic['previous_parameters'], old)
    old_plan = load(root/names[5]/'effective_plan.json'); old_model = BandModel(time, old_plan, variant, [])
    old_phase = old_model.samples(old)[1]; new_phase = model.samples(initial)[1]
    error = new_phase-old_phase
    migration = load(root/names[4]/'report.json')['initialization']
    maximum, rms = float(abs(error).max()), float(np.sqrt(np.mean(error**2)))
    assert maximum == migration['maximum_phase_migration_error'] and rms == migration['rms_phase_migration_error']
    report['initialization'] = dict(previous_parameters_equal_absolute_final=True,
        reused_quintic_initial_not_its_final=True, fresh_clock_initializer=False,
        migration_maximum_cycles=maximum, migration_rms_cycles=rms,
        migration_is_error_cause_proof=False)
    start = 2*model.parts; direction = final[start:start+model.phase_count]-initial[start:start+model.phase_count]
    assert np.linalg.norm(direction) > 0
    np.savez_compressed(args.out/'input.npz', time=time, audio=audio,
        initial_parameters=initial, final_parameters=final, phase_control_direction=direction)
    save(args.out/'effective_plan.json', plan)
    report['original_input_sha256'] = sha(parent/'input.npz')
    report['original_final_sha256'] = sha(parent/'fit.npz')
    report['arrays_read'] = ['time', 'audio', 'initial_parameters', 'parameters', 'previous_parameters']
    for state, parameters in (('initial', initial), ('final', final)):
        samples, derivative = phase_samples(model, parameters)
        for metric, operator in (('native', Aperture(len(time), plan)),
                ('marginal', MarginalAperture(Aperture(len(time), plan)))):
            result, arrays = measure(operator, samples, derivative, audio[:, 0], plan['soft_l1_scale'], direction)
            tag = state+'_'+metric
            keep = {k: v for k, v in arrays.items() if k not in
                ('residual', 'projected_phase_derivative', 'weighted_phase_derivative')}
            np.savez_compressed(args.out/(tag+'.npz'), **keep)
            report['cases'].append(dict(id=tag, arrays_sha256=sha(args.out/(tag+'.npz')), **result))
            print(json.dumps(dict(id=tag, median_ratio=result['diagonal_full_over_independent_median'],
                direction_ratio=result['directional_full_over_independent'])), flush=True)
    report.update(result='frozen_observed_initialization_and_exact_score_overlap_measured',
        scores_are_fitted_phase_uncertainty=False, independent_windows_assumed=False,
        original_phase_failure_explained=False, full_goal_complete=False,
        limits=['Local source-white-noise sensitivity of a frozen score, not a bounded fitted-parameter covariance',
            'No nuisance elimination, inverse, confidence interval, physical RPM, audio or perceptual conclusion',
            'No claim that a migrated initialization or score correlation caused the original phase error'])
except Exception as exc:
    report.update(result='failed', error=repr(exc)); raise
finally: save(args.out/'report.json', report)
