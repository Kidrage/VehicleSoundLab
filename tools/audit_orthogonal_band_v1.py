"""Rebuild the two known-control trajectories and all40 QP certificates, no fits."""
import argparse
import ast
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
from quintic_phase_v1.model import QuinticAbsoluteModel
from correlated_observation_v1.marginal import MarginalAperture
from aperture_model_v1.forward import real_rows
from joint_trust_v1.osqp_backend import linear_system
from interior_qp_v1.backend import inequalities
from complex_radial_v1.audit import reconstruct
from orthogonal_band_v1.operator import OrthogonalBand


def load(path): return json.loads(path.read_text(encoding='utf-8'))
def save(path, value): path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')


args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.orthogonal-band-audit/1', result='running', sources={}, cases=[],
    real_audio_read=False, model_exported=False, runtime_changed=False,
    nonlinear_estimator_rerun=False, quadratic_solver_rerun=False)
try:
    root = args.workspace/'references/analysis/orthogonal_band_v1'
    candidate = load(root/'fit1/report.json'); baseline = load(root/'baseline1/report.json')
    assert candidate['result'] == 'known_rapid_control_rejected_dense_not_started'
    assert baseline['result'] == 'matched_parent_control_rejected'
    assert baseline['parent_report_sha256'] == sha(root/'fit1/report.json')
    report['reports_sha256'] = {name: sha(root/name/'report.json') for name in ('fit1', 'baseline1')}
    path = repo/'tools/audit_interior_qp_v1.py'
    prior = load(args.workspace/'references/analysis/interior_qp_v1/audit1/report.json')
    assert sha(path) == prior['sources']['tools/audit_interior_qp_v1.py']
    tree = ast.parse(path.read_text(encoding='utf-8'))
    function = next(row for row in tree.body if isinstance(row, ast.FunctionDef) and row.name == 'certificate')
    namespace = dict(np=np, linear_system=linear_system, inequalities=inequalities)
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), 'exec'), namespace)
    sources = {Path(__file__), path, repo/'tools/complex_radial_v1/audit.py'}
    for name in ('fit1', 'baseline1'):
        for file, digest in load(root/name/'report.json')['sources'].items():
            assert sha(repo/file) == sha(root/name/'exact_sources'/file) == digest
            sources.add(repo/file)
    for path in sources:
        relative = path.relative_to(repo); dest = args.out/'exact_sources'/relative
        dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path, dest)
        report['sources'][relative.as_posix()] = sha(path)
    known = root/'fit1/known'; expected = np.load(known/'input.npz')
    paired = np.load(root/'baseline1/input.npz')
    assert all(np.array_equal(expected[k], paired[k]) for k in ('time', 'audio', 'initial_parameters'))
    assert baseline['exact_same_input_sha256'] == sha(known/'input.npz')
    time, audio, initial = (expected[k] for k in ('time', 'audio', 'initial_parameters'))
    plan, settings = load(known/'effective_plan.json'), load(known/'effective_settings.json')
    assert plan == load(root/'baseline1/effective_plan.json') and settings == load(root/'baseline1/effective_settings.json')
    variant = load(repo/'research/minority_phase_v1_plan.json')
    common = QuinticAbsoluteModel(time, plan, variant, [])
    assert not np.any(initial[2*common.parts:])
    operator = OrthogonalBand(len(time), plan)
    matrix = operator.factor*(np.cos(2*np.pi*operator.orders[:, None]*time)-1j*np.sin(2*np.pi*operator.orders[:, None]*time))
    zero = np.zeros_like(initial)
    _, linear = common.original.samples(zero, True)
    coefficient_design = real_rows(matrix@linear[:, :2*common.parts])
    linear_residual = coefficient_design@initial[:2*common.parts]-real_rows(matrix@audio[:, 0])
    ls_gradient = float(abs(coefficient_design.T@linear_residual).max())
    assert ls_gradient < 1e-12
    # The independent assessment/source construction is not imported from the generator.
    truth = .045*np.exp(-((time-19)/1.2)**2)-.03*np.exp(-((time-21)/.9)**2); truth -= truth[0]
    source = np.zeros_like(audio)
    for k, order in enumerate(plan['source_orders']):
        amplitude = .045 if order in (2, 3, 5, 7) else .022*(1+.15*np.cos(.31*k))
        envelope = 1+.06*np.sin(2*np.pi*(.024+.0002*k)*time+.19*k)
        complex_source = amplitude*envelope*np.exp(1j*(2*np.pi*order*(time+truth)+.37*order+.013*order**2))
        source[:, 0] += complex_source.real
        source[:, 1] += .82*(complex_source*np.exp(1j*(.17+.021*order))).real
    source_error = float(abs(source-audio).max()); assert source_error < 1e-12
    inside = (time >= 5)&(time < 35)
    plot_curves = []
    for label, folder in (('orthogonal', known), ('marginal', root/'baseline1')):
        model = QuinticAbsoluteModel(time, plan, variant, [])
        model.original.aperture = OrthogonalBand(len(time), plan) if label == 'orthogonal' else MarginalAperture(model.original.aperture)
        target = real_rows(model.original.aperture.apply(audio[:, 0]))
        fitted = load(folder/'fit.json')
        def progress(row):
            if row['iteration'] % 5 == 0: print(json.dumps(dict(case=label, audited_step=row['iteration'])), flush=True)
        parameters, trace, scale_error = reconstruct(model, initial, target, plan, settings, fitted, namespace['certificate'], progress)
        saved = np.load(folder/'fit.npz')
        assert np.array_equal(parameters, saved['parameters'])
        samples, phase, envelope = model.original.samples(parameters)
        assert np.array_equal(phase, saved['phase_correction'])
        error = phase-truth; error -= np.median(error[inside])
        p95 = float(np.percentile(abs(error[inside]), 95))
        root_error = float(np.percentile(abs(np.gradient(phase, time)-np.gradient(truth, time))[inside]/(1+np.gradient(truth, time))[inside], 95))
        assessment = candidate['known'] if label == 'orthogonal' else baseline['assessment']
        assert p95 == assessment.get('phase_p95_cycles') and root_error == assessment.get('root_relative_p95')
        actual_phase = np.load(folder/'assessment.npz')
        assert np.array_equal(truth, actual_phase['true_phase']) and np.array_equal(error, actual_phase['phase_error'])
        low, high = model.original.bounds(plan, variant)
        assert max(np.max(low-parameters), np.max(parameters-high)) <= 1e-9
        supported = bool(fitted['normalized_projection_residual'] <= variant['maximum_normalized_projection_residual'] and
            fitted['remaining_carriers'] >= variant['minimum_remaining_carriers'] and envelope.min() > 0 and np.diff(time+phase).min() > 0)
        assert supported == fitted['observation_supported']
        direct_error = float(abs(matrix@samples-operator.apply(samples)).max())
        assert direct_error < 1e-12
        report['cases'].append(dict(id=label, trace=trace, independent_scale_relative_error=scale_error,
            independent_operator_maximum_error=direct_error, phase_p95_cycles=p95, root_relative_p95=root_error,
            certified_QPs=sum(x['certificate']['success'] for x in trace), steps=len(trace),
            accepted_steps=sum(x['accepted'] for x in trace), observation_supported=supported,
            original_phase_gate_passed=bool(p95 <= plan['rules']['maximum_point_phase_p95_cycles'])))
        plot_curves.append((label, phase, error))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6))
    axes[0].plot(time, truth, label='Known rapid phase', color='black')
    for label, phase, error in plot_curves:
        axes[0].plot(time, phase, label=label)
        axes[1].plot(time[inside], error[inside], label=label)
    for sign in (-1, 1): axes[1].axhline(sign*.0001, color='black', linestyle='--', linewidth=.7)
    axes[0].set(xlabel='Coarse-cycle coordinate', ylabel='Phase correction (cycles)')
    axes[1].set(xlabel='Original interior coordinate', ylabel='Median-aligned phase error (cycles)')
    for ax in axes: ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(args.out/'known_phase.png', dpi=150); plt.close(fig)
    report.update(result='both_known_controls_rejected_all40_steps_independently_rebuilt',
        exact_same_input_and_physical_initial=True, initial_observed_LS_gradient_maximum=ls_gradient,
        independent_complex_source_maximum_error=source_error, plot_sha256=sha(args.out/'known_phase.png'),
        original_dense_started=False, initialization_sole_cause_proved=False,
        old_warm_start_vs_fresh_start_not_same_experiment=True, full_goal_complete=False)
except Exception as exc:
    report.update(result='failed', error=repr(exc)); raise
finally: save(args.out/'report.json', report)
