"""Locate numerical deterioration across sample, observed and adjoint tangents."""
import argparse
import json
from pathlib import Path
import shutil
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--native', type=Path, required=True)
parser.add_argument('--geometry', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(args.workspace/'tools/python_deps'))
import numpy as np
from drive_evidence_v1.sources import sha
from quintic_phase_v1.model import QuinticAbsoluteModel
from aperture_model_v1.forward import real_rows
from model_score_v1.adjoint import native_adjoint


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def spectrum(values):
    norms = np.linalg.norm(values, axis=0)
    assert np.all(norms > 0)
    singular = np.linalg.svd(values/norms[None, :], compute_uv=False)
    return dict(rows=values.shape[0], columns=values.shape[1], singular_values=singular.tolist(),
        normalized_column_condition=float(singular[0]/singular[-1]),
        smallest_relative_singular_value=float(singular[-1]/singular[0]),
        all_columns_retained=True, rank_cutoff_used=False)


args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.model-score-conditioning/1', result='running', sources={},
    real_audio_read=False, truth_used=False, heldout_used=False, nonlinear_estimator_run=False,
    full_qualification=False, model_exported=False, runtime_changed=False)
try:
    geometry = load(args.geometry/'report.json')
    assert sha(args.native/'input.npz') == geometry['native_input_sha256']
    assert sha(args.native/'effective_plan.json') == geometry['native_plan_sha256']
    paths = {Path(__file__)}
    for relative, digest in geometry['sources'].items():
        assert sha(repo/relative) == sha(args.geometry/'exact_sources'/relative) == digest
        paths.add(repo/relative)
    for path in paths:
        relative = path.relative_to(repo)
        target = args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        report['sources'][relative.as_posix()] = sha(path)
    plan = load(args.native/'effective_plan.json')
    inputs = np.load(args.native/'input.npz')
    model = QuinticAbsoluteModel(inputs['time'], plan, load(repo/'research/minority_phase_v1_plan.json'), [])
    outer, amplitudes = model.unpack(inputs['initial_parameters'])
    cosine, sine, _ = model.carrier(outer)
    slope = -(model.full@amplitudes.T)*sine
    common = (slope*2*np.pi*model.original.orders).sum(axis=1)
    source = np.column_stack((slope, common[:, None]*model.original.phase_basis,
        (cosine[:, :, None]*model.full[:, None, :]).reshape(len(cosine), -1)))
    _, phase = model.prediction(outer, amplitudes, True)
    observed = np.column_stack((phase, model.design(outer)))
    forward_error = float(abs(real_rows(model.original.aperture.apply(source))-observed).max())
    assert forward_error <= plan['rules']['maximum_forward_check_error']
    adjoint = native_adjoint(model.original.aperture, observed, len(inputs['time']))
    spectra = {name: spectrum(value) for name, value in
               (('raw_sample_D', source), ('native_A_D', observed), ('adjoint_A_T_A_D', adjoint))}
    assert all(value['columns'] == 732 for value in spectra.values())
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    figure, axis = plt.subplots(figsize=(9, 4), layout='constrained')
    for name, row in spectra.items():
        singular = np.asarray(row['singular_values'])
        axis.semilogy(np.arange(1, len(singular)+1), singular/singular[0], label=name)
    axis.axhline(np.finfo(float).eps, color='k', linestyle='--', linewidth=.8)
    axis.set(xlabel='Singular direction (all retained)', ylabel='Relative singular value',
             title='Same observed initial and 732 sample derivatives')
    axis.legend()
    figure.savefig(args.out/'model_score_conditioning.png', dpi=150)
    plt.close(figure)
    report.update(result='same_initial_tangent_conditioning_measured_without_fitting',
        geometry_report_sha256=sha(args.geometry/'report.json'),
        sample_to_observed_jacobian_maximum_error=forward_error, spectra=spectra,
        float64_epsilon=float(np.finfo(float).eps),
        plot_sha256=sha(args.out/'model_score_conditioning.png'),
        limitations=['Singular tails are floating-point diagnostics, not exact ranks or physical identifiability',
            'No source direction truncated, no noise calibration or phase recovery established',
            'A square-root factorization would still require independent permutation and original full phase checks'])
    print(json.dumps(dict(result=report['result'], forward_error=forward_error,
        conditions={name: value['normalized_column_condition'] for name, value in spectra.items()})), flush=True)
except Exception as exc:
    report.update(result='failed', error=repr(exc))
    raise
finally:
    (args.out/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n',
                                      encoding='utf-8', newline='\n')
