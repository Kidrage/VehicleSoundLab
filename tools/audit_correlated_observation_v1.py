"""Audit unchanged waveform/input and complete certified marginal-metric fit trajectory."""
import argparse
import ast
import json
from pathlib import Path
import shutil
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--parent', type=Path, required=True)
parser.add_argument('--candidate', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(args.workspace/'tools/ipm_deps'), str(args.workspace/'tools/qp_deps'),
               str(args.workspace/'tools/python_deps')]
import numpy as np
from drive_evidence_v1.sources import sha
from observed_topology_v1.fixtures import make
from quintic_phase_v1.model import QuinticAbsoluteModel
from correlated_observation_v1.marginal import MarginalAperture
from correlated_observation_v1.trace import reconstruct
from aperture_model_v1.forward import real_rows
from aperture_model_v1.checks import assess
from absolute_amplitude_v1.amplitude import cost
from joint_trust_v1.osqp_backend import linear_system
from interior_qp_v1.backend import inequalities


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.correlated-observation-audit/1', result='running', sources={},
    trace=[], real_audio_read=False, nonlinear_estimator_rerun=False, quadratic_solver_rerun=False)
try:
    value = load(args.candidate/'report.json')
    assert value['result'] in ('dense_marginal_metric_rejected', 'dense_marginal_metric_passed_not_full_qualification')
    assert value['parent_report_sha256'] == sha(args.parent/'report.json')
    certificate_path = repo/'tools/audit_interior_qp_v1.py'
    old_audit = load(args.workspace/'references/analysis/interior_qp_v1/audit1/report.json')
    assert sha(certificate_path) == old_audit['sources']['tools/audit_interior_qp_v1.py']
    tree = ast.parse(certificate_path.read_text(encoding='utf-8'))
    function = next(row for row in tree.body if isinstance(row, ast.FunctionDef) and row.name == 'certificate')
    namespace = dict(np=np, linear_system=linear_system, inequalities=inequalities)
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(certificate_path), 'exec'), namespace)
    sources = {Path(__file__), certificate_path, repo/'tools/correlated_observation_v1/trace.py'}
    for relative, digest in value['sources'].items():
        assert sha(repo/relative) == sha(args.candidate/'exact_sources'/relative) == digest
        sources.add(repo/relative)
    for source in sources:
        relative = source.relative_to(repo)
        target = args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        report['sources'][relative.as_posix()] = sha(source)
    plan = load(args.candidate/'effective_plan.json')
    assert plan == load(args.parent/'effective_plan.json')
    settings = load(args.candidate/'effective_settings.json')
    assert settings == load(args.parent/'effective_settings.json')
    variant = load(repo/'research/minority_phase_v1_plan.json')
    inputs = np.load(args.candidate/'input.npz')
    original = np.load(args.parent/'input.npz')
    assert all(np.array_equal(inputs[key], original[key]) for key in ('time', 'audio', 'initial_parameters'))
    time, audio, initial = (inputs[key] for key in ('time', 'audio', 'initial_parameters'))
    topology = load(repo/'research/observed_topology_v1_plan.json')
    base = load(repo/topology['base_plan'])
    case = next(row for row in topology['added_cases'] if row['id'] == 'unknown_thirty_six')
    independent_time, independent_audio, truth, _ = make(case, base)
    assert np.array_equal(time, independent_time) and np.array_equal(audio, independent_audio)
    model, native = (QuinticAbsoluteModel(time, plan, variant, []) for _ in range(2))
    model.original.aperture = MarginalAperture(model.original.aperture)
    assert np.array_equal(model.original.phase_basis, native.original.phase_basis)
    assert np.array_equal(model.original.envelope_basis, native.original.envelope_basis)
    assert np.array_equal(model.original.samples(initial)[0], native.original.samples(initial)[0])
    assert np.array_equal(model.original.bounds(plan, variant), native.original.bounds(plan, variant))
    target = real_rows(model.original.aperture.apply(audio[:, 0]))
    def progress(row):
        if row['iteration']%5 == 0:
            print(json.dumps(dict(audited_step=row['iteration'])), flush=True)
    parameters, report['trace'] = reconstruct(model, initial, target, plan, settings,
        value['fit'], namespace['certificate'], progress)
    saved = np.load(args.candidate/'fit.npz')
    assert np.array_equal(parameters, saved['parameters'])
    _, phase, envelope = model.original.samples(parameters)
    assert np.array_equal(phase, saved['phase_correction'])
    assessment, positions, oracle = assess(audio, time, truth, phase, parameters,
        {**plan, 'heldout_orders': base['heldout_orders']})
    assert assessment == value['assessment']
    coordinates = np.load(args.candidate/'coordinates.npz')
    assert np.array_equal(positions, coordinates['positions']) and np.array_equal(oracle, coordinates['oracle_positions'])
    lower, upper = model.original.bounds(plan, variant)
    assert max(np.max(lower-parameters), np.max(parameters-upper)) <= 1e-9
    assert envelope.min() > 0 and np.diff(time+phase).min() > 0
    old = np.load(args.parent/'fit.npz')
    costs = []
    for label, fitted in (('native', old['parameters']), ('marginal', parameters)):
        for name, local_model in (('native', native), ('marginal', model)):
            local_target = real_rows(local_model.original.aperture.apply(audio[:, 0]))
            residual = local_model.original.prediction(fitted)-local_target
            costs.append(dict(parameters=label, observation=name,
                soft_l1_cost=cost(residual, plan['soft_l1_scale']),
                normalized_residual=float(np.linalg.norm(residual)/np.linalg.norm(local_target))))
    prior = args.workspace/'references/analysis/state_media_v1/final1'
    for name in ('C_files_sha256.json', 'voice_files_sha256.json'):
        assert all(sha(repo/path) == digest for path, digest in load(prior/name).items())
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    interior = (time >= 5)&(time < 35)
    figure, axis = plt.subplots(figsize=(10, 4), layout='constrained')
    for label, curve in (('Native-bin unweighted', old['phase_correction']), ('Marginal correlation metric', phase)):
        error = curve-truth
        error -= np.median(error[interior])
        axis.plot(time[interior], error[interior], label=label)
    for sign in (-1, 1):
        axis.axhline(sign*plan['rules']['maximum_point_phase_p95_cycles'], color='k', linestyle='--', linewidth=.7)
    axis.set(xlabel='Coarse-cycle coordinate', ylabel='Median-aligned phase error (cycles)')
    axis.legend()
    figure.savefig(args.out/'correlated_observation_phase.png', dpi=150)
    plt.close(figure)
    report.update(result='marginal_metric_original_QP_certificates_and_full_trace_reconstructed',
        candidate_report_sha256=sha(args.candidate/'report.json'), unchanged_input_model_bounds_initial=True,
        qp_certified=sum(row['certificate']['success'] for row in report['trace']),
        entire_trace_and_final_assessment_exact=True, cross_metric_costs=costs,
        plot_sha256=sha(args.out/'correlated_observation_phase.png'), C_H=540,
        moving35_and_voices_unchanged=True, full_qualification=False)
    print(json.dumps(dict(result=report['result'], qp_certified=report['qp_certified'],
        phase_p95=assessment['point_phase_p95_cycles'])), flush=True)
except Exception as exc:
    report.update(result='failed', error=repr(exc))
    raise
finally:
    (args.out/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n',
                                      encoding='utf-8', newline='\n')
