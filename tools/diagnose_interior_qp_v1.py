"""Qualify an independent QP backend, replay saved problems, then same-model fit."""
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
parser.add_argument('--stage', choices=['replay', 'fit'], required=True)
parser.add_argument('--replay', type=Path)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(args.workspace/'tools/ipm_deps'), str(args.workspace/'tools/qp_deps'),
    str(args.workspace/'tools/python_deps')]
import numpy as np
import scipy
import clarabel
from drive_evidence_v1.sources import sha
from observed_topology_v1.fixtures import make
from aperture_model_v1.forward import real_rows
from aperture_model_v1.checks import assess
from absolute_amplitude_v1.amplitude import cost
from quintic_phase_v1.model import QuinticAbsoluteModel
from joint_trust_v1.constraints import Region
from joint_trust_v1.fit import estimate_with_model, scales_from_observation
from interior_qp_v1.backend import solve
from interior_qp_v1.checks import controls


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')


args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.interior-qp-diagnosis/1', stage=args.stage, result='running', sources={},
    real_audio_read=False, real_source_permitted=False, qualification_changed=False, runtime_changed=False)
try:
    parent = load(args.parent/'report.json')
    assert parent['result'] == 'dense_diagnostic_rejected' and parent['fit']['iterations'] == 20
    report['parent_report_sha256'] = sha(args.parent/'report.json')
    settings_path = repo/'research/interior_qp_v1_plan.json'
    configuration = load(settings_path)
    trust_path = repo/configuration['parent_plan']
    settings = {**load(trust_path), **configuration}
    sources = {Path(__file__), settings_path, trust_path, repo/'tools/offline_ipm_requirements.txt'}
    sources.update((repo/'tools/interior_qp_v1').glob('*.py'))
    sources.update(repo/name for name in parent['sources'])
    for relative, digest in parent['sources'].items():
        assert sha(repo/relative) == sha(args.parent/'exact_sources'/relative) == digest
    for path in sources:
        relative = path.relative_to(repo)
        target = args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        report['sources'][relative.as_posix()] = sha(path)
    install = args.workspace/'tools/ipm_install_report.json'
    shutil.copy2(install, args.out/'ipm_install_report.json')
    report['ipm_install_report_sha256'] = sha(install)
    report['numeric_libraries'] = dict(numpy=np.__version__, scipy=scipy.__version__, clarabel=clarabel.__version__)
    topology = load(repo/'research/observed_topology_v1_plan.json')
    base = load(repo/topology['base_plan'])
    variant = load(repo/topology['minority_plan'])
    case = next(row for row in topology['added_cases'] if row['id'] == 'unknown_thirty_six')
    time, audio, truth, _ = make(case, base)
    plan = load(args.parent/'effective_plan.json')
    save(args.out/'effective_plan.json', plan)
    saved = np.load(args.parent/'fit.npz')
    assert np.array_equal(time, saved['time']) and np.array_equal(truth, saved['true_phase_correction'])
    model = QuinticAbsoluteModel(time, plan, variant, parent['fit']['selected_indices'])
    target = real_rows(model.original.aperture.apply(audio[:, 0]))
    initial = saved['initial_parameters']
    if args.stage == 'replay':
        report['controls'] = controls(plan, variant, settings)
        save(args.out/'controls.json', report['controls'])
        print(json.dumps(dict(status='independent_controls_passed', analytic=4, polytope=2)), flush=True)
        scales = np.asarray(parent['fit']['scales'])
        outer0, absolute0 = model.unpack(initial)
        assert np.array_equal(scales, scales_from_observation(model, outer0, absolute0, target, plan['soft_l1_scale']))
        report['replays'] = []
        for iteration in configuration['replay_iterations']:
            row = parent['fit']['history'][iteration-1]
            if iteration == 1:
                outer, absolute = outer0, absolute0
            else:
                previous = parent['fit']['history'][iteration-2]
                assert previous['accepted']
                outer = np.asarray(previous['candidate_outer'])
                absolute = np.asarray(previous['candidate_absolute_amplitudes'])
            predicted, derivative = model.prediction(outer, absolute, True)
            residual = predicted-target
            assert cost(residual, plan['soft_l1_scale']) == row['before_cost']
            matrix = np.column_stack((derivative, model.design(outer)))*scales[None, :]
            ratio = residual/plan['soft_l1_scale']
            curvature = (1+ratio**2)**(-1.5)
            gram = matrix.T@(curvature[:, None]*matrix)
            gradient = matrix.T@(residual/np.sqrt(1+ratio**2))
            region = Region(model, outer, absolute, scales, row['radius'], settings)
            old_step = np.asarray(row['qp']['primal_solution'])
            old_objective = float(.5*old_step@gram@old_step+gradient@old_step)
            assert old_objective == row['qp']['objective']
            new_step, certificate = solve(gram, gradient, region, settings)
            candidate_outer, candidate_absolute, effective, feasible = region.retract(new_step)
            candidate_cost = cost(model.prediction(candidate_outer, candidate_absolute)-target, plan['soft_l1_scale'])
            evidence = dict(iteration=iteration, radius=row['radius'], prior_QP=row['qp'],
                new_QP=certificate, prior_objective=old_objective, new_objective=certificate['objective'],
                retraction=feasible, nonlinear_candidate_cost=candidate_cost,
                nonlinear_before_cost=row['before_cost'],
                candidate_outer=candidate_outer.tolist(), candidate_absolute_amplitudes=candidate_absolute.tolist())
            report['replays'].append(evidence)
            save(args.out/f'replay_{iteration}.json', evidence)
            assert certificate['success'] and feasible['feasible']
            assert certificate['objective'] <= old_objective+max(1e-12, abs(old_objective)*1e-6)
            print(json.dumps(dict(iteration=iteration, success=certificate['success'],
                iterations=certificate['iterations'], stationarity=certificate['normalized_dual_stationarity'],
                prior_objective=old_objective, new_objective=certificate['objective'],
                nonlinear_cost=candidate_cost)), flush=True)
        report.update(result='independent_controls_and_actual_subproblem_replays_certified',
            nonlinear_estimator_run=False, truth_used_by_solver=False, heldout_used_by_solver=False)
    else:
        assert args.replay is not None
        replay = load(args.replay/'report.json')
        assert replay['result'] == 'independent_controls_and_actual_subproblem_replays_certified'
        assert replay['parent_report_sha256'] == report['parent_report_sha256']
        assert replay['numeric_libraries'] == report['numeric_libraries']
        assert all(sha(repo/name) == digest for name, digest in replay['sources'].items())
        report['certified_replay_report_sha256'] = sha(args.replay/'report.json')
        report['controls_reused_without_rerun'] = True
        started = timer.perf_counter()
        def progress(row):
            save(args.out/'progress.json', row)
            print(json.dumps(dict(iteration=row['iteration'], accepted=row['accepted'],
                candidate_cost=row['candidate_cost'], radius=row['radius'],
                qp_certified=row['qp']['success'], qp_iterations=row['qp']['iterations'],
                stationarity=row['qp']['normalized_dual_stationarity'])), flush=True)
        parameters, phase, report['fit'] = estimate_with_model(model, audio, time, plan, variant,
            settings, initial, progress, qp_solver=solve)
        report['fit']['seconds'] = timer.perf_counter()-started
        np.savez_compressed(args.out/'fit.npz', time=time, initial_parameters=initial,
            parameters=parameters, phase_correction=phase, true_phase_correction=truth)
        assert np.array_equal(initial, saved['initial_parameters'])
        if report['fit']['observation_supported']:
            report['assessment'], positions, oracle = assess(audio, time, truth, phase, parameters,
                {**plan, 'heldout_orders': base['heldout_orders']})
            np.savez_compressed(args.out/'coordinates.npz', positions=positions, oracle_positions=oracle)
        certified_count = sum(row['qp']['success'] for row in report['fit']['history'])
        report.update(result='dense_diagnostic_passed_not_full_qualification' if report.get('assessment', {}).get('qualified')
            else 'dense_diagnostic_rejected', qp_certified=certified_count,
            qp_uncertified=report['fit']['iterations']-certified_count, nonlinear_estimator_run=True)
        print(json.dumps(dict(result=report['result'], qp_certified=certified_count,
            phase_p95=report.get('assessment', {}).get('point_phase_p95_cycles'), seconds=report['fit']['seconds'])), flush=True)
except Exception as exc:
    report.update(result='failed', error=repr(exc))
    raise
finally:
    save(args.out/'report.json', report)
