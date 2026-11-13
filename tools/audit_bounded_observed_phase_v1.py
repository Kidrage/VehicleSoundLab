"""Audit finite observed direction, preserved test repair, and all40 bounded steps."""
import argparse
import ast
import importlib.util
import json
import math
from pathlib import Path
import shutil
import sys

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
args = p.parse_args(); repo = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(args.workspace/'tools/python_deps')]
import numpy as np
from drive_evidence_v1.sources import sha
from bounded_observed_phase_v1.direction import construct
from bounded_observed_phase_v1.checks import controls
from quintic_phase_v1.model import QuinticAbsoluteModel
from joint_nuisance_pair_v1.model import from_original
from joint_nuisance_pair_v1.audit import trace


def load(path): return json.loads(path.read_text(encoding='utf-8'))


args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.bounded-observed-phase-audit/1', result='running', sources={}, cases=[],
    real_audio_read=False, truth_used=False, heldout_used=False, nonlinear_fits_rerun=False,
    large_QPs_rerun=False, model_exported=False, runtime_changed=False, full_qualification=False)
try:
    root = args.workspace/'references/analysis/bounded_observed_phase_v1'
    failure = load(root/'pair1/report.json'); value = load(root/'pair2/report.json')
    assert failure['result'] == 'failed' and failure['error'] == 'AssertionError()' and not failure['cases']
    assert value['result'] == 'finite_observed_direction_compensated_not_phase_qualification'
    assert value['controls']['passed'] and value['direction']['both_targets_feasible']
    checks_name = 'tools/bounded_observed_phase_v1/checks.py'
    for name, digest in failure['sources'].items():
        assert sha(root/'pair1/exact_sources'/name) == digest
        if name != checks_name: assert sha(repo/name) == digest
    old = (root/'pair1/exact_sources'/checks_name).read_text(encoding='utf-8')
    new = (repo/checks_name).read_text(encoding='utf-8')
    first = 'steep[:, 0]*.5).min() > 0'; second = 'steep[:, 0]).min() == 0'
    assert old.count(first) == old.count(second) == 1
    repaired = old.replace(first, 'steep[:, 0]*.25).min() > 0').replace(second, 'steep[:, 0]*.5).min() == 0')
    assert ast.dump(ast.parse(repaired)) == ast.dump(ast.parse(new)) and old != new
    spec = importlib.util.spec_from_file_location('bounded_observed_phase_v1.failed_checks', root/'pair1/exact_sources'/checks_name)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    try: module.controls()
    except AssertionError: original_failed_control_replayed = True
    else: raise AssertionError('Original incorrect control did not fail')
    assert controls() == value['controls']
    paths = {Path(__file__), repo/'research/bounded_observed_phase_v1_control_repair.json',
        repo/'tools/joint_nuisance_pair_v1/audit.py'}
    for name, digest in value['sources'].items():
        assert sha(repo/name) == sha(root/'pair2/exact_sources'/name) == digest
        paths.add(repo/name)
    for path in paths:
        relative = path.relative_to(repo); dest = args.out/'exact_sources'/relative
        dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path, dest)
        report['sources'][relative.as_posix()] = sha(path)
    report['historical_source_versions'] = {checks_name: dict(pair1_sha256=failure['sources'][checks_name],
        current_sha256=sha(repo/checks_name), repair='Only the two known-control scalar multipliers differ; AST checked')}
    parent = args.workspace/'references/analysis/complex_radial_v1/fit1'
    rank_dir = args.workspace/'references/analysis/phase_score_budget_v1/rank1'
    assert value['parent_fit_sha256'] == sha(parent/'fit.npz') and value['parent_input_sha256'] == sha(parent/'input.npz')
    assert value['rank_report_sha256'] == sha(rank_dir/'report.json') and value['rank_arrays_sha256'] == sha(rank_dir/'rank.npz')
    assert value['arrays_sha256'] == sha(root/'pair2/direction.npz')
    data = np.load(root/'pair2/direction.npz'); input_data = np.load(parent/'input.npz')
    fitted = np.load(parent/'fit.npz'); ranked = np.load(rank_dir/'rank.npz')
    assert np.array_equal(data['base_parameters'], fitted['parameters']) and np.array_equal(data['time'], input_data['time'])
    plan = load(parent/'effective_plan.json'); settings = load(parent/'effective_settings.json')
    variant = load(repo/'research/minority_phase_v1_plan.json')
    time = data['time']; original = QuinticAbsoluteModel(time, plan, variant, []); m = original.original
    interior = (time >= 5)&(time < 35); first = 2*m.parts; stop = first+m.phase_count
    phase_indices = np.arange(m.parts, m.parts+m.phase_count)
    supplied = ranked['marginal_radial_weakest_phase_direction']*ranked['scales'][phase_indices]
    direction, curve, geometry = construct(time, m.phase_basis, fitted['parameters'][first:stop], supplied,
        plan['phase_control_bound_cycles'], interior, 2*plan['rules']['maximum_point_phase_p95_cycles'])
    assert geometry == value['direction'] and np.array_equal(direction, data['direction'])
    assert np.array_equal(curve, data['unit_phase_curve'])
    scalar_curve = np.array([math.fsum(float(a*b) for a, b in zip(row, direction)) for row in m.phase_basis])
    curve_error = float(abs(curve-scalar_curve).max()); assert curve_error <= 1e-12
    current = fitted['parameters'][first:stop]; current_phase = m.phase_basis@current
    for row in geometry['cases']:
        d = row['sign']*direction; motion = m.phase_basis@d
        # One independent system of linear inequalities on positive ray scale.
        coefficient = np.r_[d, -d, -np.diff(motion)]
        right = np.r_[plan['phase_control_bound_cycles']-current,
            plan['phase_control_bound_cycles']+current, np.diff(time+current_phase)]
        eligible = coefficient > 0; limit = float(np.min(right[eligible]/coefficient[eligible]))
        assert abs(limit-row['maximum_scale']) <= 1e-12
        assert np.max(coefficient*row['target_scale']-right) <= 1e-12
        assert np.diff(time+current_phase+row['target_scale']*motion).min() > 0
    target, base_phase, _ = m.samples(fitted['parameters'])
    assert np.array_equal(target, data['target_waveform']) and np.array_equal(base_phase, data['base_phase'])
    masks = dict(early=time < 5, interior=interior, late=time >= 35)
    assert np.all(sum(mask.astype(int) for mask in masks.values()) == 1)
    for row in value['cases']:
        key = row['id']; initial_parameters = data[key+'_initial_parameters']
        expected = fitted['parameters'].copy()
        expected[first:stop] += row['geometry']['sign']*geometry['target_scale']*direction
        assert np.array_equal(expected, initial_parameters)
        fixed, initial, indices = from_original(original, initial_parameters)
        assert np.array_equal(indices, data[key+'_nuisance_indices']) and len(indices) == 648
        def independent(x):
            full = initial_parameters.copy(); full[indices] = x
            samples, jacobian = m.samples(full, True)
            return samples, jacobian[:, indices]
        final, checked = trace(fixed, target, initial, row['fit'], settings, independent)
        assert np.array_equal(final, data[key+'_nuisance_parameters'])
        parameters = initial_parameters.copy(); parameters[indices] = final
        assert np.array_equal(parameters, data[key+'_parameters'])
        waveform, phase, envelope = m.samples(parameters)
        before = data[key+'_initial_waveform']
        assert np.array_equal(waveform, data[key+'_waveform']) and np.array_equal(phase, m.samples(initial_parameters)[1])
        lower, upper = m.bounds(plan, variant)
        violation = float(max(0., (lower-parameters).max(), (parameters-upper).max()))
        assert violation == row['original_parameter_violation_after'] <= 1e-9
        assert float(envelope.min()) == row['minimum_envelope_after'] > 0
        assert float(np.linalg.norm(waveform-target)) == row['raw_difference_after']
        assert float(np.linalg.norm(before-target)) == row['raw_difference_before']
        partitions = {}
        for label, signal in (('before', before-target), ('after', waveform-target)):
            energy = {name: float(signal[mask]@signal[mask]) for name, mask in masks.items()}
            total = float(signal@signal)
            assert abs(sum(energy.values())-total) <= 1e-12*max(1., total)
            partitions[label] = dict(energy=energy, total=total,
                interior_energy_fraction=energy['interior']/total,
                region_norms={name: math.sqrt(v) for name, v in energy.items()})
        report['cases'].append(dict(id=key, audit=checked, all_parameters_samples_fixed_phase_exact=True,
            original_bounds_positive_envelope_monotonic=True, partitions=partitions))
        print(json.dumps(dict(audited_case=key, steps=len(checked['rows']),
            after_interior_energy_fraction=partitions['after']['interior_energy_fraction'])), flush=True)
    prior = args.workspace/'references/analysis/phase_score_budget_v1/final1'
    for filename in ('C_files_sha256.json', 'voice_files_sha256.json'):
        assert all(sha(repo/name) == digest for name, digest in load(prior/filename).items())
    report.update(result='observed_finite_ray_repair_and_all40_bounded_steps_independently_audited',
        candidate_report_sha256=sha(root/'pair2/report.json'), failure_report_sha256=sha(root/'pair1/report.json'),
        old_failed_control_replayed=original_failed_control_replayed, repair_only_two_assertion_multipliers=True,
        scalar_phase_curve_maximum_error=curve_error, all_actual40_steps_audited=True, C_H=540,
        voices_and_moving35_unchanged=True,
        limits=['One observed direction and finite local compensation, not a global minimum or all-direction identifiability',
            'Raw-sample model target is not the original recording and uses no noise/truth/heldout input',
            'Energy partitions are diagnostic; original compensation fit still used ALL samples',
            'Old joint solver controls were identity-verified and reused, not rerun or counted as new tests'])
except Exception as exc:
    report.update(result='failed', error=repr(exc)); raise
finally:
    (args.out/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')
