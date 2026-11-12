"""Separate known noise/model errors after independently certified QPs."""
import argparse
import json
from pathlib import Path
import shutil
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--parent', type=Path, required=True)
parser.add_argument('--fit', type=Path, required=True)
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
from absolute_amplitude_v1.amplitude import cost


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.certified-qp-noise-diagnosis/1', result='running', sources={},
    real_audio_read=False, real_source_permitted=False, qualification_changed=False,
    may_initialize_estimator=False, nonlinear_estimator_rerun=False,
    analytic_truth_used_only_for_diagnosis=True)
try:
    value, prior = load(args.fit/'report.json'), load(args.parent/'report.json')
    assert value['result'] == 'dense_diagnostic_rejected' and value['qp_certified'] == 20
    report['fit_report_sha256'] = sha(args.fit/'report.json')
    report['prior_report_sha256'] = sha(args.parent/'report.json')
    sources = {Path(__file__)} | {repo/name for name in value['sources']}
    for name, digest in value['sources'].items():
        assert sha(repo/name) == sha(args.fit/'exact_sources'/name) == digest
    for path in sources:
        relative = path.relative_to(repo)
        target = args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        report['sources'][relative.as_posix()] = sha(path)
    topology = load(repo/'research/observed_topology_v1_plan.json')
    base, variant = load(repo/topology['base_plan']), load(repo/topology['minority_plan'])
    case = next(row for row in topology['added_cases'] if row['id'] == 'unknown_thirty_six')
    time, audio, truth, _ = make(case, base)
    _, clean, _, _ = make({**case, 'noise': 0.}, base)
    _, source, _, _ = make({**case, 'noise': 0.}, {**base, 'heldout_orders': []})
    plan = load(args.fit/'effective_plan.json')
    model = QuinticAbsoluteModel(time, plan, variant, [])
    project = lambda samples: real_rows(model.original.aperture.apply(samples))
    observed, clean_target, source_target = project(audio[:, 0]), project(clean[:, 0]), project(source[:, 0])
    saved = np.load(args.fit/'fit.npz')
    old = np.load(args.parent/'fit.npz')
    assert np.array_equal(time, saved['time']) and np.array_equal(truth, saved['true_phase_correction'])
    prediction = model.original.prediction(saved['parameters'])
    noise, omitted = observed-clean_target, clean_target-source_target
    model_error = prediction-source_target
    residual = prediction-observed
    closure = float(abs(residual-(model_error-omitted-noise)).max())
    assert closure < 1e-12
    report.update(result='diagnosed_certified_fit_known_noise_not_qualified',
        residual_decomposition_maximum_error=closure,
        norms=dict(known_noise=float(np.linalg.norm(noise)), omitted_line_projection=float(np.linalg.norm(omitted)),
            actual_residual=float(np.linalg.norm(residual)), actual_model_vs_clean=float(np.linalg.norm(prediction-clean_target))),
        costs=dict(actual_on_observed=cost(residual, plan['soft_l1_scale']),
            actual_on_clean=cost(prediction-clean_target, plan['soft_l1_scale'])),
        actual_model_error_noise_correlation=float(np.dot(model_error, noise)/max(np.linalg.norm(model_error)*np.linalg.norm(noise), 1e-30)),
        phase_p95_cycles=value['assessment']['point_phase_p95_cycles'],
        phase_gate=plan['rules']['maximum_point_phase_p95_cycles'],
        qp_certified=20, nonlinear_global_convergence_claimed=False,
        limits=['Known source/noise/truth are isolated here; not estimator inputs or real-recording uncertainty',
            'All20 QP certificates do not establish nonlinear/global convergence or phase accuracy',
            'Noise correlation supports sensitivity/overfit investigation, not a sole-cause proof',
            'Keep original dense failed positive/all17/full33/individual14kHz/original E'])
    np.savez_compressed(args.out/'noise_arrays.npz', time=time, truth=truth,
        prior_phase=old['phase_correction'], actual_phase=saved['phase_correction'],
        projected_noise=noise, omitted=omitted, model_error=model_error, residual=residual)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), layout='constrained')
    interior = (time >= 5)&(time < 35)
    for phase, label in ((old['phase_correction'], 'Prior OSQP (1/20 certified)'),
        (saved['phase_correction'], 'QR + active set (20/20 certified)')):
        error = phase-truth
        error -= np.median(error[interior])
        axes[0].plot(time[interior], error[interior], label=label)
    for sign in (-1, 1):
        axes[0].axhline(sign*report['phase_gate'], color='black', linestyle='--', linewidth=.6)
    axes[0].set(xlabel='Coarse-cycle coordinate', ylabel='Phase error (cycles)')
    axes[0].legend(fontsize=7)
    for fit, label in ((prior['fit'], 'Prior OSQP'), (value['fit'], 'QR + active set')):
        accepted = [row for row in fit['history'] if row['accepted']]
        axes[1].semilogy([row['iteration'] for row in accepted], [row['candidate_cost'] for row in accepted],
            marker='.', label=label)
    axes[1].set(xlabel='Accepted trust-region iteration', ylabel='Original robust objective')
    axes[1].legend(fontsize=8)
    fig.savefig(args.out/'certified_phase.png', dpi=150)
    plt.close(fig)
    report['plot_sha256'] = sha(args.out/'certified_phase.png')
    print(json.dumps({key: report[key] for key in ('result', 'norms', 'costs', 'actual_model_error_noise_correlation')}), flush=True)
except Exception as exc:
    report.update(result='failed', error=repr(exc))
    raise
finally:
    (args.out/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')
