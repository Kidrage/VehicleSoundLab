"""Compare raw/aperture local noise sensitivity; analytic diagnosis, never a fit."""
import argparse
import json
from pathlib import Path
import shutil
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--candidate', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(args.workspace/'tools/python_deps'))
import numpy as np
from drive_evidence_v1.sources import sha
from quintic_phase_v1.model import QuinticAbsoluteModel
from observed_topology_v1.fixtures import make
from aperture_model_v1.forward import real_rows
from smooth_envelope_v1.covariance import adjoint


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.quintic-observation-diagnosis/1', result='running', sources={},
    real_audio_read=False, real_source_permitted=False, qualification_changed=False,
    may_initialize_estimator=False, analytic_truth_used_only_for_diagnosis=True,
    nonlinear_estimator_rerun=False, linear_projection_solves=True)
try:
    parent = load(args.candidate/'report.json')
    assert parent['result'] in ('dense_diagnostic_rejected', 'dense_diagnostic_passed_not_full_qualification')
    report['candidate_report_sha256'] = sha(args.candidate/'report.json')
    sources = {Path(__file__), repo/'tools/smooth_envelope_v1/covariance.py'}
    sources.update(repo/name for name in parent['sources'])
    for relative, digest in parent['sources'].items():
        assert sha(repo/relative) == sha(args.candidate/'exact_sources'/relative) == digest
    for path in sources:
        relative = path.relative_to(repo)
        target = args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        report['sources'][relative.as_posix()] = sha(path)
    topology = load(repo/'research/observed_topology_v1_plan.json')
    base = load(repo/topology['base_plan'])
    variant = load(repo/topology['minority_plan'])
    case = next(row for row in topology['added_cases'] if row['id'] == 'unknown_thirty_six')
    time, audio, truth, _ = make(case, base)
    _, clean, _, _ = make({**case, 'noise': 0.}, base)
    _, source, _, _ = make({**case, 'noise': 0.}, {**base, 'heldout_orders': []})
    plan = load(args.candidate/'effective_plan.json')
    saved = np.load(args.candidate/'fit.npz')
    assert np.array_equal(time, saved['time']) and np.array_equal(truth, saved['true_phase_correction'])
    model = QuinticAbsoluteModel(time, plan, variant, [])
    m = model.original
    oracle_root = args.workspace/'references/analysis/guard_observation_v1/band_oracle1'
    oracle_report = load(oracle_root/'report.json')
    assert oracle_report['may_initialize_estimator'] is False
    oracle = np.load(oracle_root/'oracle_amplitudes.npz')
    budget_root = args.workspace/'references/analysis/joint_trust_v1/noise_budget3'
    budget_report = load(budget_root/'report.json')
    assert budget_report['may_initialize_estimator'] is False
    budget = np.load(budget_root/'diagnostic_arrays.npz')
    assert np.array_equal(time, budget['time']) and np.array_equal(truth, budget['true_phase'])
    # This curve was already computed using analytic truth in the frozen
    # representation diagnosis. It is not an estimator initialization.
    phase_controls = np.linalg.lstsq(m.phase_basis, budget['quintic_known_phase_approximation'], rcond=None)[0]
    assert abs(m.phase_basis@phase_controls-budget['quintic_known_phase_approximation']).max() < 1e-12
    assert abs(phase_controls).max() <= model.phase_bound
    old_parts = len(plan['source_orders'])
    coefficients = oracle['parameters'][:2*old_parts]
    angles = np.arctan2(-coefficients[old_parts:], coefficients[:old_parts])
    outer = np.r_[angles, phase_controls]
    controls = oracle['absolute_controls']
    parameters = model.pack(outer, controls)
    low, high = m.bounds(plan, variant)
    assert max(np.max(low-parameters), np.max(parameters-high)) <= 1e-9
    cosine, sine, anchor_phase = model.carrier(outer)
    amplitude = model.full@controls.T
    samples = (amplitude*cosine).sum(axis=1)
    slope = -amplitude*sine
    sample_phase = (slope*2*np.pi*m.orders).sum(axis=1)[:, None]*m.phase_basis
    sample_outer = slope
    sample_amplitude = (cosine[:, :, None]*model.full[:, None, :]).reshape(len(time), -1)
    sample_nuisance = np.column_stack((sample_outer, sample_amplitude))
    prediction, outer_jacobian = model.prediction(outer, controls, True)
    aperture = m.aperture
    project = lambda array: real_rows(aperture.apply(array))
    assert abs(project(sample_phase)-outer_jacobian[:, m.parts:]).max() < 1e-12
    assert abs(project(sample_outer)-outer_jacobian[:, :m.parts]).max() < 1e-12
    assert abs(project(sample_amplitude)-model.design(outer)).max() < 1e-12
    assert abs(project(samples)-prediction).max() < 1e-12
    components = np.column_stack((samples-source[:, 0], -(clean-source)[:, 0], -(audio-clean)[:, 0]))
    assert abs(components.sum(axis=1)-(samples-audio[:, 0])).max() < 1e-14
    interior = (time >= 5)&(time < 35)
    centered_basis = m.phase_basis[interior]-m.phase_basis[interior].mean(axis=0)
    sigma = case['noise']*case.get('gain', 1.)
    arrays = dict(time=time, true_phase=truth, anchor_phase=anchor_phase, parameters=parameters,
        actual_phase=saved['phase_correction'], raw_component_residuals=components)
    cases = []
    for kind in ('aperture', 'raw_samples'):
        if kind == 'aperture':
            common, nuisance, residuals = project(sample_phase), project(sample_nuisance), project(components)
        else:
            common, nuisance, residuals = sample_phase, sample_nuisance, components
        u, s, _ = np.linalg.svd(nuisance, full_matrices=False)
        keep = s > s[0]*1e-10
        q = u[:, keep]
        profiled = common-q@(q.T@common)
        pu, ps, pv = np.linalg.svd(profiled, full_matrices=False)
        active = ps > ps[0]*1e-10
        influence = (pv[active].T/ps[active])@pu[:, active].T
        influence -= (influence@q)@q.T
        changes = -influence@residuals
        phase_changes = m.phase_basis@changes
        raw_dual = adjoint(aperture, influence.T, len(time)) if kind == 'aperture' else influence.T
        covariance = sigma**2*(raw_dual.T@raw_dual)
        variance = np.einsum('ij,jk,ik->i', centered_basis, covariance, centered_basis)
        assert variance.min() >= -1e-18
        expected_rms = float(np.sqrt(np.maximum(variance, 0).mean()))
        direct_noise = -influence@residuals[:, 2]
        via_adjoint = raw_dual.T@(audio-clean)[:, 0]
        dual_error = float(abs(direct_noise-via_adjoint).max())
        assert dual_error < 1e-9
        component_rows = []
        for index, label in enumerate(('model_approximation', 'omitted_lines', 'fixture_noise')):
            change = phase_changes[:, index]-np.median(phase_changes[interior, index])
            component_rows.append(dict(component=label, residual_norm=float(np.linalg.norm(residuals[:, index])),
                local_phase_p95_cycles=float(np.percentile(abs(change[interior]), 95)),
                maximum_unbounded_phase_control_delta=float(abs(changes[:, index]).max()),
                original_phase_control_bound_exceeded=bool(abs(phase_controls+changes[:, index]).max() > model.phase_bound)))
        combined = anchor_phase+phase_changes.sum(axis=1)-truth
        combined -= np.median(combined[interior])
        row = dict(kind=kind, observation_rows=len(common), nuisance_columns=nuisance.shape[1],
            nuisance_rank=int(keep.sum()), common_phase_rank=int(active.sum()),
            profiled_phase_condition=float(ps[0]/max(ps[-1], 1e-30)),
            expected_mean_centered_noise_phase_RMS_cycles=expected_rms,
            independent_noise_adjoint_error=dual_error, components=component_rows,
            combined_linear_phase_p95_cycles=float(np.percentile(abs(combined[interior]), 95)),
            combined_original_phase_bound_exceeded=bool(abs(phase_controls+changes.sum(axis=1)).max() > model.phase_bound),
            quantitative_prediction_of_actual_bounded_estimator=False)
        cases.append(row)
        arrays[kind+'_phase_changes'] = phase_changes
        arrays[kind+'_phase_singular_values'] = ps
        arrays[kind+'_phase_covariance'] = covariance
        print(json.dumps(row), flush=True)
    np.savez_compressed(args.out/'diagnostic_arrays.npz', **arrays)
    report.update(result='diagnosed_raw_and_aperture_local_sensitivity_no_estimator_change', cases=cases,
        amplitude_oracle_report_sha256=sha(oracle_root/'report.json'),
        known_phase_budget_report_sha256=sha(budget_root/'report.json'),
        known_noise_sigma=sigma, original_phase_gate=plan['rules']['maximum_point_phase_p95_cycles'],
        rcond=1e-10, residual_decomposition_exact=True, common_sample_derivative_projection_checked=True,
        limits=['All analytic source/noise/phase/oracle amplitudes are diagnosis only, never actual initialization or selection',
            'Local unweighted minimum-norm sensitivities ignore robust loss, nonlinear changes and active bounds',
            'Unbounded linear steps can leave the original phase bounds; their magnitudes are not attainable actual error or evidence of unavoidable failure',
            'Raw sample comparison contains omitted source lines; it is not an approved replacement objective or fit',
            'Expected mean-centered RMS is not the median-aligned phase-p95 qualification gate or real uncertainty',
            'The original failed dense positive, all17/full33/individual14kHz/original E remain required'])
except Exception as exc:
    report.update(result='failed', error=repr(exc))
    raise
finally:
    (args.out/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')
