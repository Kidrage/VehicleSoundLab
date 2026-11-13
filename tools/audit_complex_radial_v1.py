"""Audit all saved radial-fit steps and unchanged input/model, without re-solving."""
import argparse
import ast
import json
from pathlib import Path
import shutil
import sys

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
args = p.parse_args(); repo = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(args.workspace/'tools/ipm_deps'), str(args.workspace/'tools/qp_deps'),
    str(args.workspace/'tools/python_deps')]
import numpy as np
from drive_evidence_v1.sources import sha
from observed_topology_v1.fixtures import make
from quintic_phase_v1.model import QuinticAbsoluteModel
from correlated_observation_v1.marginal import MarginalAperture
from complex_radial_v1.audit import reconstruct
from complex_radial_v1.loss import cost as radial_cost
from absolute_amplitude_v1.amplitude import cost as scalar_cost
from aperture_model_v1.forward import real_rows
from aperture_model_v1.checks import assess
from joint_trust_v1.osqp_backend import linear_system
from interior_qp_v1.backend import inequalities


def load(path): return json.loads(path.read_text(encoding='utf-8'))


args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.complex-radial-audit/1', result='running', sources={}, trace=[],
    real_audio_read=False, model_exported=False, runtime_changed=False,
    nonlinear_estimator_rerun=False, quadratic_solver_rerun=False)
try:
    root = args.workspace/'references/analysis/complex_radial_v1'
    candidate = root/'fit1'; controls = root/'controls1'
    parent = args.workspace/'references/analysis/correlated_observation_v1/fit1'
    value = load(candidate/'report.json'); old_report = load(parent/'report.json')
    assert value['result'] in ('dense_radial_rejected', 'dense_radial_passed_not_full_qualification')
    assert value['parent_report_sha256'] == sha(parent/'report.json')
    assert value['controls_report_sha256'] == sha(controls/'report.json')
    certificate_path = repo/'tools/audit_interior_qp_v1.py'
    prior_audit = load(args.workspace/'references/analysis/interior_qp_v1/audit1/report.json')
    assert sha(certificate_path) == prior_audit['sources']['tools/audit_interior_qp_v1.py']
    tree = ast.parse(certificate_path.read_text(encoding='utf-8'))
    function = next(row for row in tree.body if isinstance(row, ast.FunctionDef) and row.name == 'certificate')
    namespace = dict(np=np, linear_system=linear_system, inequalities=inequalities)
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(certificate_path), 'exec'), namespace)
    sources = {Path(__file__), certificate_path, repo/'tools/complex_radial_v1/audit.py'}
    for folder in (candidate, controls):
        for name, digest in load(folder/'report.json')['sources'].items():
            assert sha(repo/name) == sha(folder/'exact_sources'/name) == digest
            sources.add(repo/name)
    for path in sources:
        relative = path.relative_to(repo); dest = args.out/'exact_sources'/relative
        dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path, dest)
        report['sources'][relative.as_posix()] = sha(path)
    plan = load(candidate/'effective_plan.json'); settings = load(candidate/'effective_settings.json')
    assert plan == load(parent/'effective_plan.json') and settings == load(parent/'effective_settings.json')
    variant = load(repo/'research/minority_phase_v1_plan.json')
    inputs = np.load(candidate/'input.npz'); original = np.load(parent/'input.npz')
    assert all(np.array_equal(inputs[k], original[k]) for k in ('time', 'audio', 'initial_parameters'))
    time, audio, initial = (inputs[k] for k in ('time', 'audio', 'initial_parameters'))
    topology = load(repo/'research/observed_topology_v1_plan.json'); base = load(repo/topology['base_plan'])
    case = next(row for row in topology['added_cases'] if row['id'] == 'unknown_thirty_six')
    independent_time, independent_audio, truth, _ = make(case, base)
    assert np.array_equal(time, independent_time) and np.array_equal(audio, independent_audio)
    model, native = (QuinticAbsoluteModel(time, plan, variant, []) for _ in range(2))
    model.original.aperture = MarginalAperture(model.original.aperture)
    assert np.array_equal(model.original.samples(initial)[0], native.original.samples(initial)[0])
    assert np.array_equal(model.original.bounds(plan, variant), native.original.bounds(plan, variant))
    target = real_rows(model.original.aperture.apply(audio[:, 0]))
    def progress(row):
        if row['iteration'] % 5 == 0:
            print(json.dumps(dict(audited_step=row['iteration'])), flush=True)
    parameters, report['trace'], scale_error = reconstruct(model, initial, target, plan, settings,
        value['fit'], namespace['certificate'], progress)
    saved = np.load(candidate/'fit.npz')
    assert np.array_equal(parameters, saved['parameters'])
    _, phase, envelope = model.original.samples(parameters)
    assert np.array_equal(phase, saved['phase_correction'])
    assessment, positions, oracle = assess(audio, time, truth, phase, parameters,
        {**plan, 'heldout_orders': base['heldout_orders']})
    assert assessment == value['assessment']
    coordinates = np.load(candidate/'coordinates.npz')
    assert np.array_equal(positions, coordinates['positions']) and np.array_equal(oracle, coordinates['oracle_positions'])
    lower, upper = model.original.bounds(plan, variant)
    assert max(np.max(lower-parameters), np.max(parameters-upper)) <= 1e-9
    remaining = sum(np.hypot(parameters[k], parameters[k+model.parts]) >= plan['rules']['minimum_carrier_amplitude']
        for k in range(model.parts) if k not in model.original.selected)
    assert remaining == value['fit']['remaining_carriers']
    assert float(envelope.min()) == value['fit']['minimum_envelope']
    assert float(envelope.max()) == value['fit']['maximum_envelope']
    minimum_step = float(np.diff(time+phase).min())
    assert minimum_step == value['fit']['minimum_coordinate_step']
    supported = bool(value['fit']['normalized_projection_residual'] <= variant['maximum_normalized_projection_residual']
        and remaining >= variant['minimum_remaining_carriers'] and envelope.min() > 0 and minimum_step > 0)
    assert supported == value['fit']['observation_supported']
    assert value['result'] == ('dense_radial_passed_not_full_qualification' if supported and assessment['qualified'] else 'dense_radial_rejected')
    old = np.load(parent/'fit.npz'); costs = []
    for label, fitted in (('initial', initial), ('scalar_fit', old['parameters']), ('radial_fit', parameters)):
        residual = model.original.prediction(fitted)-target
        costs.append(dict(parameters=label, scalar_cost=scalar_cost(residual, plan['soft_l1_scale']),
            radial_cost=radial_cost(residual, plan['soft_l1_scale']),
            normalized_residual=float(np.linalg.norm(residual)/np.linalg.norm(target))))
    previous = args.workspace/'references/analysis/F2_variation_projection_v1/final1'
    for name in ('C_files_sha256.json', 'voice_files_sha256.json'):
        assert all(sha(repo/path) == digest for path, digest in load(previous/name).items())
    report.update(result='radial_geometry_all_QP_certificates_and_entire_fit_trace_reconstructed',
        fit_report_sha256=sha(candidate/'report.json'), controls_report_sha256=sha(controls/'report.json'),
        parent_report_sha256=sha(parent/'report.json'), entire_trace_and_final_assessment_exact=True,
        unchanged_input_model_bounds_initial=True, independent_scale_relative_error=scale_error,
        qp_certified=sum(row['certificate']['success'] for row in report['trace']), cross_objective_costs=costs,
        phase_p95=dict(scalar=old_report['assessment']['point_phase_p95_cycles'], radial=assessment['point_phase_p95_cycles']),
        C_H=540, moving35_and_voices_unchanged=True, full_qualification=False,
        limits=['Independent 2x2 block geometry, exact executed helper used for bitwise KKT replay',
            'No nonlinear or QP re-solves; known truth/heldouts used only for post-fit assessment',
            'Objective values under different metrics cannot be compared as an improvement',
            'Cross-window correlation and out-of-band mismatch remain; no real DNA or listening acceptance'])
    print(json.dumps(dict(result=report['result'], qp_certified=report['qp_certified'], phase_p95=report['phase_p95'])), flush=True)
except Exception as exc:
    report.update(result='failed', error=repr(exc)); raise
finally:
    (args.out/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')
