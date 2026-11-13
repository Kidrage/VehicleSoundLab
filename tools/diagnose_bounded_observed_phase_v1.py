"""One observed finite phase direction, original bounds, conditional nuisance fits."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import time as timer

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
args = p.parse_args(); repo = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(args.workspace/'tools/ipm_deps'), str(args.workspace/'tools/qp_deps'),
    str(args.workspace/'tools/python_deps')]
import numpy as np
from drive_evidence_v1.sources import sha
from bounded_observed_phase_v1.direction import construct, phase_size
from bounded_observed_phase_v1.checks import controls
from quintic_phase_v1.model import QuinticAbsoluteModel
from joint_nuisance_pair_v1.model import from_original
from joint_nuisance_pair_v1.fit import fit


def load(path): return json.loads(path.read_text(encoding='utf-8'))
def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')


args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.bounded-observed-phase/1', result='running', sources={}, cases=[],
    real_audio_read=False, truth_used=False, heldout_used=False, phase_estimator_run=False,
    nonlinear_nuisance_fits_run=False, model_exported=False, runtime_changed=False, full_qualification=False)
try:
    rank_dir = args.workspace/'references/analysis/phase_score_budget_v1/rank1'
    rank = load(rank_dir/'report.json')
    parent = args.workspace/'references/analysis/complex_radial_v1/fit1'
    old_joint = args.workspace/'references/analysis/joint_nuisance_pair_v1/pair1'
    joint = load(old_joint/'report.json')
    assert rank['result'] == 'rank_loss_localized_without_phase_response_or_model_change'
    assert sha(rank_dir/'rank.npz') == rank['arrays_sha256']
    assert joint['result'] == 'finite_joint_nuisance_pairs_measured_not_global_minima' and joint['controls']['passed']
    old_audit = load(args.workspace/'references/analysis/joint_nuisance_pair_v1/audit1/report.json')
    assert old_audit['all_actual40_steps_audited'] and old_audit['candidate_report_sha256'] == sha(old_joint/'report.json')
    paths = {Path(__file__), repo/'research/bounded_observed_phase_v1_plan.json',
        *sorted((repo/'tools/bounded_observed_phase_v1').glob('*.py'))}
    for folder, value in ((rank_dir, rank), (old_joint, joint)):
        for name, digest in value['sources'].items():
            assert sha(repo/name) == sha(folder/'exact_sources'/name) == digest
            paths.add(repo/name)
    for path in paths:
        relative = path.relative_to(repo); dest = args.out/'exact_sources'/relative
        dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path, dest)
        report['sources'][relative.as_posix()] = sha(path)
    report['controls'] = controls()
    inputs = np.load(parent/'input.npz'); frozen = np.load(parent/'fit.npz'); data = np.load(rank_dir/'rank.npz')
    assert sha(parent/'fit.npz') == rank['parent_fit_sha256'] and sha(parent/'input.npz') == rank['parent_input_sha256']
    time = inputs['time']; parameters = frozen['parameters']
    plan = load(parent/'effective_plan.json'); settings = load(parent/'effective_settings.json')
    variant = load(repo/'research/minority_phase_v1_plan.json')
    original = QuinticAbsoluteModel(time, plan, variant, [])
    m = original.original; first = 2*m.parts; stop = first+m.phase_count
    indices = np.arange(m.parts, m.parts+m.phase_count)
    assert np.array_equal(data['phase_indices'], indices)
    supplied = data['marginal_radial_weakest_phase_direction']*data['scales'][indices]
    interior = (time >= 5)&(time < 35)
    direction, curve, geometry = construct(time, m.phase_basis, parameters[first:stop], supplied,
        plan['phase_control_bound_cycles'], interior, 2*plan['rules']['maximum_point_phase_p95_cycles'])
    report.update(direction=geometry, rank_report_sha256=sha(rank_dir/'report.json'), rank_arrays_sha256=sha(rank_dir/'rank.npz'),
        parent_fit_sha256=sha(parent/'fit.npz'), parent_input_sha256=sha(parent/'input.npz'),
        reused_joint_controls_and40step_audit=True, reused_joint_audit_sha256=sha(args.workspace/'references/analysis/joint_nuisance_pair_v1/audit1/report.json'),
        original_joint_tests_rerun=False)
    target, base_phase, _ = m.samples(parameters)
    lower, upper = m.bounds(plan, variant)
    arrays = dict(time=time, base_parameters=parameters, base_phase=base_phase, direction=direction,
        unit_phase_curve=curve, target_waveform=target)
    print(json.dumps(dict(controls=True, target_feasible=geometry['both_targets_feasible'],
        target_scale=geometry['target_scale'], limits=[r['maximum_scale'] for r in geometry['cases']])), flush=True)
    for case in geometry['cases']:
        key = 'minus' if case['sign'] < 0 else 'plus'
        candidate = parameters.copy(); candidate[first:stop] += case['sign']*geometry['target_scale']*direction
        waveform, phase, envelope = m.samples(candidate)
        measured = phase_size(phase-base_phase, interior)
        assert abs(measured-geometry['target_interior_p95']) <= 1e-12
        row = dict(id=key, geometry=case, measured_phase_difference_p95=measured,
            original_parameter_violation=float(max(0., (lower-candidate).max(), (candidate-upper).max())),
            minimum_envelope=float(envelope.min()), minimum_coordinate_increment=float(np.diff(time+phase).min()))
        arrays[key+'_initial_parameters'] = candidate
        arrays[key+'_initial_waveform'] = waveform
        if geometry['both_targets_feasible']:
            fixed, initial, nuisance_indices = from_original(original, candidate)
            assert np.array_equal(fixed.samples(initial), waveform) and fixed.size == 648
            def progress(item):
                save(args.out/(key+'_progress.json'), item)
                print(json.dumps(dict(case=key, iteration=item['iteration'], accepted=item['accepted'],
                    cost=item['candidate_cost'], certified=item['subproblem']['certificate']['success'])), flush=True)
            started = timer.perf_counter()
            fitted, result = fit(fixed, target, initial, settings, progress)
            completed = candidate.copy(); completed[nuisance_indices] = fitted
            output, same_phase, final_envelope = m.samples(completed)
            assert np.array_equal(phase, same_phase) and np.array_equal(fixed.samples(fitted), output)
            violation = float(max(0., (lower-completed).max(), (completed-upper).max()))
            row.update(fit=result, seconds=timer.perf_counter()-started,
                original_parameter_violation_after=violation, minimum_envelope_after=float(final_envelope.min()),
                raw_difference_before=float(np.linalg.norm(waveform-target)), raw_difference_after=float(np.linalg.norm(output-target)),
                common_phase_fixed=True, feasible=bool(violation <= 1e-9 and final_envelope.min() > 0 and np.diff(time+phase).min() > 0))
            arrays[key+'_parameters'] = completed; arrays[key+'_waveform'] = output
            arrays[key+'_nuisance_indices'] = nuisance_indices; arrays[key+'_nuisance_parameters'] = fitted
            report['nonlinear_nuisance_fits_run'] = True
        report['cases'].append(row)
    np.savez_compressed(args.out/'direction.npz', **arrays)
    report.update(result='finite_observed_direction_compensated_not_phase_qualification' if geometry['both_targets_feasible'] else
        'observed_weak_direction_target_infeasible_no_compensation_run',
        arrays_sha256=sha(args.out/'direction.npz'), direction_or_strength_reselected=False,
        limits=['One frozen observed conditional singular-vector direction, not a recovered/physical clock',
            'Target infeasibility is not proof that every finite phase direction is identifiable',
            'If fitted: finite local bounded nuisance response is not global minimum or estimator recovery',
            'No known phase/noise/heldout input; target is the same observed fitted-model waveform',
            'Original dense36/all17/full33/individual14k/originalE gates remain unpassed'])
    print(json.dumps(dict(result=report['result'])), flush=True)
except Exception as exc:
    report.update(result='failed', error=repr(exc)); raise
finally: save(args.out/'report.json', report)
