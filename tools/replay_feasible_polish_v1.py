"""One feasible fallback on each saved latest failed QP; no IPM/nonlinear rerun."""
import argparse
import json
from pathlib import Path
import shutil
import sys

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
args = p.parse_args(); repo = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(args.workspace/'tools'/x) for x in ('ipm_deps', 'qp_deps', 'python_deps')]
import numpy as np
from drive_evidence_v1.sources import sha
from quintic_phase_v1.model import QuinticAbsoluteModel
from orthogonal_band_v1.operator import OrthogonalBand
from aperture_model_v1.forward import real_rows
from joint_trust_v1.constraints import Region
from joint_trust_v1.osqp_backend import linear_system
from radial_majorizer_v1.geometry import quadratic
from interior_qp_v1.backend import inequalities
from unit_box_qp_v1.solver import metrics, certified
from feasible_polish_v1.active_set import polish
from feasible_polish_v1.checks import controls


def load(path): return json.loads(path.read_text(encoding='utf-8'))
def save(path, value): path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')


args.out.mkdir(parents=True, exist_ok=False)
r = dict(schema='vsl.feasible-polish-replay/1', result='running', sources={}, replays=[],
    truth_read=False, real_audio_read=False, IPM_rerun=False, nonlinear_fit=False,
    model_exported=False, runtime_changed=False)
try:
    parent = args.workspace/'references/analysis/unit_box_qp_v1/fit1'
    observed, fitted = load(parent/'report.json'), load(parent/'fit.json')
    assert observed['result'] == 'known_unit_box_rejected'
    sources = {Path(__file__), repo/'research/feasible_polish_v1_plan.json'}
    sources.update((repo/'tools/feasible_polish_v1').glob('*.py'))
    for name, digest in observed['sources'].items():
        assert sha(repo/name) == sha(parent/'exact_sources'/name) == digest
        sources.add(repo/name)
    for path in sources:
        rel = path.relative_to(repo); dest = args.out/'exact_sources'/rel
        dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path, dest)
        r['sources'][rel.as_posix()] = sha(path)
    r['parent_report_sha256'], r['parent_fit_sha256'] = sha(parent/'report.json'), sha(parent/'fit.json')
    settings = load(parent/'effective_settings.json')
    r['controls'] = controls(settings)
    save(args.out/'effective_settings.json', settings)
    print(json.dumps(dict(controls='seven_passed')), flush=True)
    inputs = np.load(parent/'input.npz')
    time, audio, initial = (inputs[k] for k in ('time', 'audio', 'initial_parameters'))
    plan = load(parent/'effective_plan.json'); variant = load(repo/'research/minority_phase_v1_plan.json')
    model = QuinticAbsoluteModel(time, plan, variant, [])
    model.original.aperture = OrthogonalBand(len(time), plan)
    outer, amplitude = model.unpack(initial); scales = np.asarray(fitted['scales'])
    target = real_rows(model.original.aperture.apply(audio[:, 0]))
    failed = [row['iteration'] for row in fitted['history'] if not row['qp']['success']]
    assert failed == [5, 11, 12]
    for row in fitted['history']:
        if row['iteration'] in failed:
            prediction, derivative = model.prediction(outer, amplitude, True)
            design = np.column_stack((derivative, model.design(outer)))*scales[None, :]
            gram, g, weighted, rhs = quadratic(prediction-target, design, row['stage_scale'])
            region = Region(model, outer, amplitude, scales, row['radius'], settings)
            matrix, lower, upper = linear_system(region)
            rows, bounds, _, _ = inequalities(matrix, lower, upper)
            coarse = row['qp']['coarse_attempt']; initial_step = np.array(coarse['primal_solution'])
            case = args.out/('step'+str(row['iteration'])); case.mkdir()
            np.savez_compressed(case/'input.npz', gram=gram, gradient=g, weighted=weighted, rhs=rhs,
                matrix=matrix.toarray(), lower=lower, upper=upper, radius=row['radius'], initial=initial_step)
            save(case/'old_failed_QP.json', row['qp'])
            x, z, details = polish(gram, g, weighted, rhs, rows, bounds, initial_step, settings)
            y, q = metrics(gram, g, matrix, lower, upper, x, z, coarse['objective_scale'])
            passed = bool(details['success'] and certified(q, settings))
            q.update(success=passed, native_success=passed, status='SolvedFeasibleActiveSet' if passed else 'FeasibleActiveSetUncertified',
                status_value=int(passed), objective_scale=coarse['objective_scale'],
                primal_solution=x.tolist(), dual_solution=y.tolist(), inequality_dual=z.tolist(),
                active_set_polish=details, iterations=details['iterations'], original_limits_unchanged=True,
                external_hessian_regularization=False, truth_used=False, heldout_used=False)
            save(case/'new_QP.json', q)
            item = dict(iteration=row['iteration'], radius=row['radius'], success=passed, iterations=q['iterations'],
                input_sha256=sha(case/'input.npz'), new_QP_sha256=sha(case/'new_QP.json'),
                stationarity=q['normalized_dual_stationarity'], primal=q['constraint_violation'],
                dual_sign=q['inequality_dual_sign_violation'], complementarity=q['maximum_complementarity'],
                maximum_path_primal=max(a['certificate']['primal'] for a in details['history']))
            r['replays'].append(item); print(json.dumps(item), flush=True)
        if row['accepted']:
            outer, amplitude = np.asarray(row['candidate_outer']), np.asarray(row['candidate_absolute_amplitudes'])
    passed = all(row['success'] for row in r['replays'])
    r.update(result='all3_saved_QPs_feasibly_certified' if passed else 'feasible_polish_replay_rejected',
        all3_passed=passed, original_dense_started=False, full_goal_complete=False,
        limits=['Saved fixed QPs only; no new nonlinear trajectory or real DNA qualification',
            'Original finite20 fallback and full certificates retained; no truth-guided selection or tolerance change'])
except Exception as exc:
    r.update(result='failed', error=repr(exc)); raise
finally:
    save(args.out/'report.json', r)
