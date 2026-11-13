"""Locate the failed full-rank assumption across unchanged observation stages."""
import argparse
import json
from pathlib import Path
import shutil
import sys

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
args = p.parse_args(); repo = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(args.workspace/'tools/python_deps')]
import numpy as np
from drive_evidence_v1.sources import sha
from phase_score_budget_v1.rank import inspect, controls
from complex_radial_v1.loss import hessian_apply
from quintic_phase_v1.model import QuinticAbsoluteModel
from correlated_observation_v1.marginal import MarginalAperture
from aperture_model_v1.forward import real_rows


def load(path): return json.loads(path.read_text(encoding='utf-8'))


def raw_jacobian(model, outer, amplitudes):
    m = model.original
    phase = m.phase_basis@outer[m.parts:m.parts+m.phase_count]
    angle = 2*np.pi*(m.time[:, None]+phase[:, None])*m.orders[None, :]+outer[None, :m.parts]
    carrier = np.exp(1j*angle); amplitude = model.full@amplitudes.T
    angle_columns = -amplitude*carrier.imag
    common = (angle_columns*(2*np.pi*m.orders[None, :])).sum(axis=1)
    return np.column_stack((angle_columns, common[:, None]*m.phase_basis,
        (carrier.real[:, :, None]*model.full[:, None, :]).reshape(len(m.time), -1)))


args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.phase-score-rank/1', result='running', sources={}, stages=[],
    real_audio_read=False, model_exported=False, runtime_changed=False, full_qualification=False,
    nonlinear_estimator_run=False, quadratic_solver_run=False, local_response_calculated=False)
try:
    prior = args.workspace/'references/analysis/phase_score_budget_v1/diagnosis1'
    failure = load(prior/'report.json')
    assert failure['result'] == 'failed' and '604/648' in failure['error']
    parent = args.workspace/'references/analysis/complex_radial_v1/fit1'
    paths = {Path(__file__), repo/'research/phase_score_budget_v1_rank_plan.json',
        repo/'tools/phase_score_budget_v1/rank.py'}
    for name, digest in failure['sources'].items():
        assert sha(repo/name) == sha(prior/'exact_sources'/name) == digest
        paths.add(repo/name)
    for path in paths:
        relative = path.relative_to(repo); dest = args.out/'exact_sources'/relative
        dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path, dest)
        report['sources'][relative.as_posix()] = sha(path)
    report['controls'] = controls(); print(json.dumps(dict(controls=True)), flush=True)
    plan = load(parent/'effective_plan.json'); variant = load(repo/'research/minority_phase_v1_plan.json')
    data = np.load(parent/'input.npz'); fitted = np.load(parent/'fit.npz'); fit_report = load(parent/'report.json')
    model = QuinticAbsoluteModel(data['time'], plan, variant, [])
    outer, amplitudes = model.unpack(fitted['parameters']); scales = np.asarray(fit_report['fit']['scales'])
    raw = raw_jacobian(model, outer, amplitudes)
    phase_indices = np.arange(model.parts, model.parts+model.original.phase_count)
    arrays = dict(phase_indices=phase_indices, scales=scales); derivative_errors = {}
    matrices = [('raw_samples', raw*scales[None, :])]
    for name in ('native', 'marginal'):
        if name == 'marginal': model.original.aperture = MarginalAperture(model.original.aperture)
        value, derivative = model.prediction(outer, amplitudes, True)
        actual = np.column_stack((derivative, model.design(outer)))
        direct = real_rows(model.original.aperture.apply(raw))
        error = float(abs(direct-actual).max()); assert error <= 1e-12
        derivative_errors[name] = error
        residual = value-real_rows(model.original.aperture.apply(data['audio'][:, 0]))
        weighted = hessian_apply(residual, actual*scales[None, :], plan['soft_l1_scale'], .5)
        matrices.extend(((name, actual*scales[None, :]), (name+'_radial', weighted)))
    for name, matrix in matrices:
        result = inspect(matrix, phase_indices)
        for key, value in result.items():
            if isinstance(value, np.ndarray): arrays[name+'_'+key] = value
        item = {key: value for key, value in result.items() if not isinstance(value, np.ndarray)}
        item.update(stage=name, shape=list(matrix.shape), nuisance_columns=648, phase_columns=84,
            nuisance_minimum=float(result['nuisance_singular'][-1]),
            conditional_phase_minimum=float(result['phase_singular'][-1]),
            full_minimum=float(result['full_singular'][-1]))
        report['stages'].append(item)
        print(json.dumps(dict(stage=name, nuisance_rank=item['nuisance_rank'],
            conditional_phase_rank=item['conditional_phase_rank'], full_rank=item['full_rank'])), flush=True)
    np.savez_compressed(args.out/'rank.npz', **arrays)
    report.update(result='rank_loss_localized_without_phase_response_or_model_change',
        previous_failure_sha256=sha(prior/'report.json'), parent_fit_sha256=sha(parent/'fit.npz'),
        parent_input_sha256=sha(parent/'input.npz'), observed_derivative_maximum_errors=derivative_errors,
        arrays_sha256=sha(args.out/'rank.npz'), rank_cutoff_unchanged=True,
        limits=['Numerical rank at stated machine cutoff and current scales, not exact physical identifiability',
            'Conditional phase singulars inspect only the supported nuisance span; no inverse or response',
            'Full-rank original assumption remains failed; bounds can constrain near-null coefficient directions',
            'No noise/omission causal conclusion, phase recovery, confidence model or sound DNA adoption'])
except Exception as exc:
    report.update(result='failed', error=repr(exc)); raise
finally:
    (args.out/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')
