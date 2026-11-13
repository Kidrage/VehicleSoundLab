"""Frozen fitted-state phase influence, not a new estimator or model."""
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
from phase_score_budget_v1.checks import controls
from phase_score_budget_v1.projection import profile
from complex_radial_v1.loss import geometry, gradient, hessian_apply
from quintic_phase_v1.model import QuinticAbsoluteModel
from correlated_observation_v1.marginal import MarginalAperture
from correlated_observation_v1.decomposition import analytic_components
from aperture_model_v1.forward import real_rows


def load(path): return json.loads(path.read_text(encoding='utf-8'))
def scalar(value): return value.tolist() if isinstance(value, np.ndarray) else value


args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.phase-score-budget-diagnosis/1', result='running', sources={}, metrics=[],
    real_audio_read=False, nonlinear_estimator_run=False, quadratic_solver_run=False,
    model_exported=False, runtime_changed=False, full_qualification=False, local_responses_adopted=False)
try:
    parent = args.workspace/'references/analysis/complex_radial_v1/fit1'
    previous = load(parent/'report.json')
    assert previous['result'] == 'dense_radial_rejected'
    paths = {Path(__file__), repo/'research/phase_score_budget_v1_plan.json',
        repo/'tools/correlated_observation_v1/decomposition.py',
        *sorted((repo/'tools/phase_score_budget_v1').glob('*.py'))}
    for name, digest in previous['sources'].items():
        assert sha(repo/name) == sha(parent/'exact_sources'/name) == digest
        paths.add(repo/name)
    for path in paths:
        relative = path.relative_to(repo); dest = args.out/'exact_sources'/relative
        dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path, dest)
        report['sources'][relative.as_posix()] = sha(path)
    report['controls'] = controls()
    print(json.dumps(dict(controls=report['controls']['passed'])), flush=True)
    # Only after the frozen fitted parameters and independent controls exist:
    # reveal analytic components for this post-fit diagnostic, never estimation.
    plan = load(parent/'effective_plan.json'); variant = load(repo/'research/minority_phase_v1_plan.json')
    data = np.load(parent/'input.npz'); fitted = np.load(parent/'fit.npz')
    time, audio = data['time'], data['audio']; parameters = fitted['parameters']
    topology = load(repo/'research/observed_topology_v1_plan.json'); base = load(repo/topology['base_plan'])
    case = next(row for row in topology['added_cases'] if row['id'] == 'unknown_thirty_six')
    source, omitted, noise = analytic_components(time, plan['source_orders'], base['heldout_orders'], case)
    closure = float(abs(source+omitted+noise-audio).max()); assert closure <= 1e-12
    interior = (time >= 5)&(time < 35); scale = plan['soft_l1_scale']
    scales = np.asarray(previous['fit']['scales'])
    model = QuinticAbsoluteModel(time, plan, variant, [])
    outer, amplitudes = model.unpack(parameters)
    _, phase = model.prediction(outer, amplitudes, True)
    cosine = model.carrier(outer)[0]
    wave = ((model.full@amplitudes.T)*cosine).sum(axis=1)
    raw_parts = np.column_stack((wave-source[:, 0], -omitted[:, 0], -noise[:, 0]))
    phase_indices = np.arange(model.parts, model.parts+model.original.phase_count)
    arrays = dict(time=time, parameters=parameters, scales=scales, raw_components=raw_parts,
        phase_correction=fitted['phase_correction'])
    labels = ['model_minus_known_source', 'negative_omitted_sources', 'negative_fixture_noise', 'total']
    for name in ('native', 'marginal'):
        if name == 'marginal': model.original.aperture = MarginalAperture(model.original.aperture)
        aperture = model.original.aperture
        value, derivative = model.prediction(outer, amplitudes, True)
        matrix = np.column_stack((derivative, model.design(outer)))*scales[None, :]
        target = real_rows(aperture.apply(audio[:, 0])); residual = value-target
        components = real_rows(aperture.apply(raw_parts))
        projection_closure = float(abs(components.sum(axis=1)-residual).max()); assert projection_closure <= 1e-12
        components = np.column_stack((components, residual))
        v = geometry(residual, scale)[1]; rows = np.r_[v, v]
        score_parts = rows[:, None]*components
        assert np.linalg.norm(score_parts[:, -1]-gradient(residual, scale)) <= 1e-12
        weighted = hessian_apply(residual, matrix, scale, .5)
        rhs = hessian_apply(residual, score_parts, scale, -.5)
        result = profile(weighted, phase_indices, rhs)
        assert np.max(result['relative_normal_equations']) <= 1e-12
        changes = result['phase_changes']*scales[phase_indices, None]
        curves = model.original.phase_basis@changes
        superposition = float(np.linalg.norm(curves[:, :3].sum(axis=1)-curves[:, 3])/
            max(sum(np.linalg.norm(curves[:, k]) for k in range(3)), 1e-30))
        assert superposition <= 1e-12
        observations = []
        for column, label in enumerate(labels):
            centered = curves[:, column]-np.median(curves[interior, column])
            observations.append(dict(component=label, raw_observation_norm=float(np.linalg.norm(components[:, column])),
                score_rhs_norm=float(np.linalg.norm(rhs[:, column])),
                profiled_rhs_norm=float(result['profiled_rhs_norm'][column]),
                profiled_score_norm=float(np.linalg.norm(result['profiled_score'][:, column])),
                local_phase_p95_cycles=float(np.percentile(abs(centered[interior]), 95)),
                maximum_local_phase_control=float(abs(changes[:, column]).max()),
                normal_relative=float(result['relative_normal_equations'][column])))
        summary = {key: scalar(result[key]) for key in ('nuisance_rank', 'phase_rank', 'cutoff',
            'phase_condition', 'nuisance_condition', 'relative_normal_equations')}
        summary.update(metric=name, observations=observations, projection_closure=projection_closure,
            superposition_relative_error=superposition, fixed_parameters=True,
            nuisance_rank_margin=float(result['nuisance_singular'][-1]/result['cutoff']),
            phase_rank_margin=float(result['phase_singular'][-1]/result['cutoff']))
        report['metrics'].append(summary)
        for key in ('phase_changes', 'all_changes', 'profiled_score', 'phase_singular', 'nuisance_singular'):
            arrays[name+'_'+key] = result[key]
        arrays[name+'_phase_curves'] = curves
        print(json.dumps(dict(metric=name, phase_p95=[x['local_phase_p95_cycles'] for x in observations],
            ranks=[result['nuisance_rank'], result['phase_rank']])), flush=True)
    np.savez_compressed(args.out/'diagnosis.npz', **arrays)
    report.update(result='frozen_state_component_scores_and_local_phase_responses_diagnosed',
        parent_report_sha256=sha(parent/'report.json'), parent_fit_sha256=sha(parent/'fit.npz'),
        parent_input_sha256=sha(parent/'input.npz'), raw_closure=closure, labels=labels,
        diagnosis_sha256=sha(args.out/'diagnosis.npz'), truth_used_as_fit_initialization=False,
        heldout_carriers_fitted=False, linear_diagnostic_only=True,
        limits=['Known post-fit analytic decomposition only; no corrected estimator or model',
            'Unconstrained local Gauss-Newton responses ignore active bounds and nonlinear second derivatives',
            'Residual Hessian and weights frozen for superposition; components are not independent random variables',
            'Median-centered component curves do not sum; total is summed before centering',
            'Native/marginal comparison uses same radial fitted parameters, not two optimized solutions',
            'No causal attribution, calibrated uncertainty, achievable phase accuracy or real source separation'])
except Exception as exc:
    report.update(result='failed', error=repr(exc)); raise
finally:
    (args.out/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')
