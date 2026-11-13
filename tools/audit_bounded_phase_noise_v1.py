"""Rebuild both bounded perturbation traces without nonlinear/QP refitting."""
import argparse
import ast
import json
from pathlib import Path
import shutil
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--candidate', type=Path, required=True)
parser.add_argument('--parent', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(args.workspace/'tools/ipm_deps'), str(args.workspace/'tools/qp_deps'),
    str(args.workspace/'tools/python_deps')]
import numpy as np
from drive_evidence_v1.sources import sha
from observed_topology_v1.fixtures import make
from quintic_phase_v1.model import QuinticAbsoluteModel
from aperture_model_v1.forward import real_rows
from aperture_model_v1.checks import assess
from absolute_amplitude_v1.amplitude import cost
from joint_trust_v1.constraints import Region
from joint_trust_v1.osqp_backend import linear_system
from joint_trust_v1.fit import scales_from_observation
from interior_qp_v1.backend import inequalities


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def settings_from(path):
    values = []
    while True:
        value = load(path)
        values.append(value)
        if path == repo/'research/joint_trust_precise_v1_plan.json':
            break
        path = repo/value['parent_plan']
    result = {}
    for value in reversed(values):
        result.update(value)
    return result


args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.bounded-phase-noise-audit/1', result='running', sources={}, cases=[],
    real_audio_read=False, real_source_permitted=False, qualification_changed=False,
    nonlinear_estimator_rerun=False, quadratic_solver_rerun=False)
try:
    value = load(args.candidate/'report.json')
    assert value['result'] == 'bounded_antithetic_observation_sensitivity_measured'
    assert value['parent_report_sha256'] == sha(args.parent/'report.json')
    report['candidate_report_sha256'] = sha(args.candidate/'report.json')
    # Reuse the already audited original certificate reconstructor verbatim.
    # Extract its one pure function, avoiding that CLI's top-level execution.
    certificate_path = repo/'tools/audit_interior_qp_v1.py'
    previous = load(args.workspace/'references/analysis/interior_qp_v1/audit1/report.json')
    assert sha(certificate_path) == previous['sources']['tools/audit_interior_qp_v1.py']
    tree = ast.parse(certificate_path.read_text(encoding='utf-8'))
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'certificate')
    namespace = dict(np=np, linear_system=linear_system, inequalities=inequalities)
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(certificate_path), 'exec'), namespace)
    certificate = namespace['certificate']
    sources = {Path(__file__), certificate_path} | {repo/name for name in value['sources']}
    for name, digest in value['sources'].items():
        assert sha(repo/name) == sha(args.candidate/'exact_sources'/name) == digest
    for path in sources:
        relative = path.relative_to(repo)
        target = args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        report['sources'][relative.as_posix()] = sha(path)
    settings = settings_from(repo/'research/bounded_phase_noise_v1_plan.json')
    topology = load(repo/'research/observed_topology_v1_plan.json')
    base, variant = load(repo/topology['base_plan']), load(repo/topology['minority_plan'])
    case = next(row for row in topology['added_cases'] if row['id'] == 'unknown_thirty_six')
    time, audio, truth, _ = make(case, base)
    plan = load(args.candidate/'effective_plan.json')
    assert plan == load(args.parent/'effective_plan.json')
    inputs = np.load(args.candidate/'input.npz')
    old = np.load(args.parent/'fit.npz')
    assert np.array_equal(time, inputs['time']) and np.array_equal(audio, inputs['original_observed_audio'])
    assert np.array_equal(inputs['initial_parameters'], old['initial_parameters'])
    sigma = value['noise_proxy']['standard_deviation']
    assert np.array_equal(inputs['added_source_noise'], np.random.default_rng(settings['perturbation_seed']).normal(size=len(time))*sigma)
    # Independently recompute the estimator's proxy from a full complex FFT.
    window = np.sin(np.pi*np.arange(len(time))/len(time))**2
    frequency = np.fft.fftfreq(len(time))
    selected = (frequency >= .5*settings['noise_proxy_nyquist_fraction'])&(frequency < .5)
    full = np.fft.fft(audio[:, 0]*window)
    independent_variance = float(np.median(abs(full[selected])**2)/np.sum(window**2)/np.log(2.))
    assert abs(independent_variance/value['noise_proxy']['variance']-1) < 1e-10
    report['proxy_full_complex_FFT_relative_error'] = abs(independent_variance/value['noise_proxy']['variance']-1)
    model = QuinticAbsoluteModel(time, plan, variant, [])
    phases = {}
    for item in value['cases']:
        sign, fit = item['sign'], item['fit']
        folder = args.candidate/('minus' if sign < 0 else 'plus')
        saved = np.load(folder/'fit.npz')
        perturbed = audio.copy()
        perturbed[:, 0] += sign*inputs['added_source_noise']
        target = real_rows(model.original.aperture.apply(perturbed[:, 0]))
        outer, absolute = model.unpack(inputs['initial_parameters'])
        scales = np.asarray(fit['scales'])
        assert np.array_equal(scales, scales_from_observation(model, outer, absolute, target, plan['soft_l1_scale']))
        radius = settings['initial_radius']
        trace = []
        for row in fit['history']:
            assert radius == row['radius']
            predicted, derivative = model.prediction(outer, absolute, True)
            matrix = np.column_stack((derivative, model.design(outer)))*scales[None, :]
            residual = predicted-target
            assert cost(residual, plan['soft_l1_scale']) == row['before_cost']
            ratio = residual/plan['soft_l1_scale']
            curvature = (1+ratio**2)**(-1.5)
            gram = matrix.T@(curvature[:, None]*matrix)
            gradient = matrix.T@(residual/np.sqrt(1+ratio**2))
            region = Region(model, outer, absolute, scales, radius, settings)
            checked = certificate(row['qp'], gram, gradient, region, np.sqrt(curvature)[:, None]*matrix)
            new_outer, new_absolute, effective, feasible = region.retract(np.asarray(row['qp']['primal_solution']))
            assert feasible == row['feasibility']
            assert np.array_equal(new_outer, np.asarray(row['candidate_outer']))
            assert np.array_equal(new_absolute, np.asarray(row['candidate_absolute_amplitudes']))
            candidate = cost(model.prediction(new_outer, new_absolute)-target, plan['soft_l1_scale'])
            predicted_reduction = float(-gradient@effective-.5*effective@gram@effective)
            actual = row['before_cost']-candidate
            ratio = actual/predicted_reduction if predicted_reduction > 0 else None
            assert candidate == row['candidate_cost'] and predicted_reduction == row['predicted_reduction']
            assert actual == row['actual_reduction'] and ratio == row['ratio']
            accepted = bool(feasible['feasible'] and predicted_reduction > 0 and actual > 0 and ratio >= settings['acceptance_ratio'])
            assert accepted == row['accepted']
            if accepted:
                outer, absolute = new_outer, new_absolute
            if not accepted or ratio < .25:
                radius *= .25
            elif ratio > .75 and abs(effective).max() > .8*radius:
                radius = min(2*radius, settings['maximum_radius'])
            trace.append(dict(iteration=row['iteration'], accepted=accepted, certificate=checked,
                candidate_objective_retraction_radius_exact=True))
        assert radius == fit['final_radius']
        assert np.array_equal(model.pack(outer, absolute), saved['parameters'])
        _, phase, envelope = model.original.samples(saved['parameters'])
        assert np.array_equal(phase, saved['phase_correction'])
        assessment, positions, oracle = assess(perturbed, time, truth, phase, saved['parameters'],
            {**plan, 'heldout_orders': base['heldout_orders']})
        assert assessment == item['assessment']
        coordinates = np.load(folder/'coordinates.npz')
        assert np.array_equal(positions, coordinates['positions']) and np.array_equal(oracle, coordinates['oracle_positions'])
        low, high = model.original.bounds(plan, variant)
        assert max(np.max(low-saved['parameters']), np.max(saved['parameters']-high)) <= 1e-9
        assert envelope.min() > 0 and np.diff(time+phase).min() > 0
        phases[sign] = phase
        report['cases'].append(dict(sign=sign, entire_trace_exact=True, final_phase_assessment_and_bounds_exact=True,
            qp_certified=sum(row['certificate']['success'] for row in trace), trace=trace))
    interior = (time >= 5)&(time < 35)
    def metrics(values):
        aligned = values-np.median(values[interior])
        return dict(p95_cycles=float(np.percentile(abs(aligned[interior]), 95)),
            RMS_cycles=float(np.sqrt(np.mean(aligned[interior]**2))))
    sensitivity = dict(minus_vs_zero=metrics(phases[-1]-old['phase_correction']),
        plus_vs_zero=metrics(phases[1]-old['phase_correction']),
        antisymmetric_response=metrics((phases[1]-phases[-1])/2),
        symmetric_drift=metrics((phases[1]+phases[-1])/2-old['phase_correction']))
    assert sensitivity == value['sensitivity']
    prior = args.workspace/'references/analysis/interior_qp_v1/final1'
    for filename in ('C_files_sha256.json', 'voice_files_sha256.json'):
        assert all(sha(repo/name) == digest for name, digest in load(prior/filename).items())
    report.update(result='reconstructed_bounded_pair_input_full_traces_and_sensitivity', sensitivity=sensitivity,
        added_noise_to_observed_RMS_db=float(20*np.log10(np.sqrt(np.mean(inputs['added_source_noise']**2))/np.sqrt(np.mean(audio[:, 0]**2)))),
        C_H=540, voices_and_moving35_unchanged=True)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), layout='constrained')
    for sign in (-1, 1):
        change = phases[sign]-old['phase_correction']
        change -= np.median(change[interior])
        axes[0].plot(time[interior], change[interior], label=f'Added noise sign {sign:+d}')
    for sign in (-1, 1):
        axes[0].axhline(sign*value['original_phase_gate'], color='black', linestyle='--', linewidth=.6)
    for values, label in (((phases[1]-phases[-1])/2, 'Antisymmetric response'),
        ((phases[1]+phases[-1])/2-old['phase_correction'], 'Symmetric drift')):
        aligned = values-np.median(values[interior])
        axes[1].plot(time[interior], aligned[interior], label=label)
    axes[0].set(xlabel='Coarse-cycle coordinate', ylabel='Change from zero fit (cycles)')
    axes[1].set(xlabel='Coarse-cycle coordinate', ylabel='Paired phase response (cycles)')
    for axis in axes:
        axis.legend(fontsize=8)
    fig.savefig(args.out/'bounded_sensitivity.png', dpi=150)
    plt.close(fig)
    report['plot_sha256'] = sha(args.out/'bounded_sensitivity.png')
    print(json.dumps(dict(result=report['result'], cases=[dict(sign=row['sign'], qp_certified=row['qp_certified'])
        for row in report['cases']], sensitivity=sensitivity)), flush=True)
except Exception as exc:
    report.update(result='failed', error=repr(exc))
    raise
finally:
    (args.out/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')
