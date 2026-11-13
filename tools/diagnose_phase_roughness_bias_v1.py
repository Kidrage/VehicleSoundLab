"""Truth-isolated diagnosis of roughness bias, never an estimator initializer."""
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
from aperture_model_v1.forward import real_rows


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.phase-roughness-bias-diagnosis/1', result='running', sources={},
    real_audio_read=False, real_source_permitted=False, qualification_changed=False,
    may_initialize_estimator=False, analytic_truth_used_only_for_diagnosis=True,
    nonlinear_estimator_rerun=False, linear_projection_solves=False)
try:
    candidate = load(args.candidate/'report.json')
    assert candidate['result'] == 'dense_noise_budget_candidate_rejected'
    known_folder = args.workspace/'references/analysis/quintic_phase_v1/observation2'
    known_report = load(known_folder/'report.json')
    assert known_report['may_initialize_estimator'] is False
    sources = {Path(__file__)} | {repo/name for name in candidate['sources']}
    for name, digest in candidate['sources'].items():
        assert sha(repo/name) == sha(args.candidate/'exact_sources'/name) == digest
    for path in sources:
        relative = path.relative_to(repo)
        target = args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        report['sources'][relative.as_posix()] = sha(path)
    inputs = np.load(args.candidate/'input.npz')
    actual = np.load(args.candidate/'fit.npz')
    known = np.load(known_folder/'diagnostic_arrays.npz')
    time, audio, roughness = inputs['time'], inputs['audio'], inputs['roughness']
    assert np.array_equal(time, known['time'])
    plan = load(args.candidate/'effective_plan.json')
    variant = load(repo/'research/minority_phase_v1_plan.json')
    model = QuinticAbsoluteModel(time, plan, variant, [])
    noise_radius = float(inputs['noise_radius'])
    target = real_rows(model.original.aperture.apply(audio[:, 0]))
    interior = (time >= 5)&(time < 35)
    curves, cases = {}, []
    for name, parameters in (('observed_discrepancy_start', inputs['initial_parameters']),
        ('actual_minimum_jerk_candidate', actual['parameters']), ('known_phase_representation_diagnosis_only', known['parameters'])):
        outer, controls = model.unpack(parameters)
        _, phase, envelope = model.original.samples(parameters)
        if name.startswith('known'):
            assert np.array_equal(phase, known['anchor_phase'])
        error = phase-known['true_phase']
        error -= np.median(error[interior])
        residual = model.prediction(outer, controls)-target
        lower, upper = model.original.bounds(plan, variant)
        bound = float(max(0., np.max(lower-parameters), np.max(parameters-upper)))
        rough = roughness@outer
        cases.append(dict(id=name, phase_p95_cycles=float(np.percentile(abs(error[interior]), 95)),
            normalized_roughness_objective=float(.5*np.linalg.norm(rough)**2),
            observed_noise_ratio=float(np.linalg.norm(residual)/noise_radius),
            original_bound_violation=bound, minimum_envelope=float(envelope.min()),
            minimum_coordinate_step=float(np.diff(time+phase).min()),
            parameters_from_truth_diagnosis_only=name.startswith('known')))
        curves[name] = error
    report.update(result='saved_true_phase_representation_and_actual_roughness_compared',
        candidate_report_sha256=sha(args.candidate/'report.json'),
        known_diagnostic_report_sha256=sha(known_folder/'report.json'),
        known_diagnostic_arrays_sha256=sha(known_folder/'diagnostic_arrays.npz'), cases=cases,
        limits=['Known-phase representation and its frozen nuisance parameters are diagnosis only, not a fitted constrained optimum',
            'This comparison cannot prove global nonlinear convergence or identify one sole cause of the actual bias',
            'No truth parameter or curve may initialize or select a future estimator'])
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axis = plt.subplots(figsize=(10, 4), layout='constrained')
    for name, error in curves.items():
        axis.plot(time[interior], error[interior], label=name)
    for sign in (-1, 1):
        axis.axhline(sign*plan['rules']['maximum_point_phase_p95_cycles'], color='k', linestyle='--', linewidth=.7)
    axis.set(xlabel='Coarse-cycle coordinate', ylabel='Median-aligned phase error (cycles)')
    axis.legend(fontsize=8)
    fig.savefig(args.out/'roughness_bias.png', dpi=150)
    plt.close(fig)
    report['plot_sha256'] = sha(args.out/'roughness_bias.png')
    print(json.dumps(dict(result=report['result'], cases=cases)), flush=True)
except Exception as exc:
    report.update(result='failed', error=repr(exc))
    raise
finally:
    (args.out/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')
