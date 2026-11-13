"""Replay the retained initial-score construction and independently check its rejection."""
import argparse
import json
from pathlib import Path
import shutil
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--native', type=Path, required=True)
parser.add_argument('--geometry', type=Path, required=True)
parser.add_argument('--invariance', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(args.workspace/'tools/python_deps'))
import numpy as np
from drive_evidence_v1.sources import sha
from quintic_phase_v1.model import QuinticAbsoluteModel
from model_score_v1.projection import build, ScoreAperture
from model_score_v1.checks import controls
from model_score_v1.invariance import check


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.model-score-audit/1', result='running', sources={},
    real_audio_read=False, truth_used=False, heldout_used=False, nonlinear_estimator_run=False,
    full_qualification=False, model_exported=False, runtime_changed=False)
try:
    geometry, invariance = (load(path/'report.json') for path in (args.geometry, args.invariance))
    assert geometry['result'] == 'fixed_initial_score_geometry_and_linear_controls_passed'
    assert invariance['result'] == 'fixed_initial_score_space_not_numerically_qualified'
    assert not invariance['fit_permitted'] and not invariance['controls']['passed']
    assert sha(args.geometry/'report.json') == invariance['geometry_report_sha256']
    paths = {Path(__file__)}
    for directory, value in ((args.geometry, geometry), (args.invariance, invariance)):
        for relative, digest in value['sources'].items():
            assert sha(repo/relative) == sha(directory/'exact_sources'/relative) == digest
            paths.add(repo/relative)
    for path in paths:
        relative = path.relative_to(repo)
        target = args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        report['sources'][relative.as_posix()] = sha(path)
    plan = load(args.native/'effective_plan.json')
    assert sha(args.native/'effective_plan.json') == geometry['native_plan_sha256']
    assert sha(args.native/'input.npz') == geometry['native_input_sha256']
    inputs = np.load(args.native/'input.npz')
    model = QuinticAbsoluteModel(inputs['time'], plan, load(repo/'research/minority_phase_v1_plan.json'), [])
    basis, metadata = build(model, inputs['initial_parameters'])
    assert sha(args.geometry/'basis.npy') == geometry['basis']['sha256']
    assert np.array_equal(basis, np.load(args.geometry/'basis.npy', allow_pickle=False))
    for key, value in metadata.items():
        assert value == geometry['basis'][key]
    geometry_controls = controls(model.original.aperture, ScoreAperture(basis, model.original.aperture), plan)
    assert geometry_controls == geometry['controls']
    repeated, reverse = check(model, inputs['initial_parameters'], basis, plan)
    assert repeated == invariance['controls']
    assert sha(args.invariance/'reverse_basis.npy') == invariance['reverse_basis_sha256']
    assert np.array_equal(reverse, np.load(args.invariance/'reverse_basis.npy', allow_pickle=False))
    # Independent source-projector comparison using scalar dot and squared norms.
    # This has no dependency on the check's compare() implementation.
    independent = []
    time = inputs['time']
    for order in (3., 3.1, 8.37, 9.13, 10., 15.):
        signal = .2*np.cos(2*np.pi*order*time+.31)
        one = np.sum(basis*(basis.T@signal)[None, :], axis=1)
        two = np.sum(reverse*(reverse.T@signal)[None, :], axis=1)
        measured = float(np.sqrt(np.sum((one-two)**2)/np.sum(signal**2)))
        expected = next(row['relative_source_projection_difference']
                        for row in repeated['signals'] if row['id'] == f'tone_{order}')
        error = abs(measured-expected)
        assert error <= plan['rules']['maximum_forward_check_error']
        independent.append(dict(order=order, projection_relative_difference=measured,
                                independent_implementation_difference=error))
    prior = args.workspace/'references/analysis/state_media_v1/final1'
    for name in ('C_files_sha256.json', 'voice_files_sha256.json'):
        assert all(sha(repo/path) == digest for path, digest in load(prior/name).items())
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    figure, axes = plt.subplots(1, 2, figsize=(11, 4), layout='constrained')
    for label, singular in (('Original order', metadata['singular_values']),
                             ('Reversed order', repeated['reverse_singular_values'])):
        singular = np.asarray(singular)
        axes[0].semilogy(np.arange(1, len(singular)+1), singular/singular[0], label=label)
    axes[0].axhline(np.finfo(float).eps, color='k', linestyle='--', linewidth=.8, label='Float64 epsilon (context)')
    axes[0].set(xlabel='Singular direction (all retained)', ylabel='Relative singular value',
                title='Initial adjoint model responses')
    axes[0].legend(fontsize=8)
    labels = [row['id'].replace('tone_', '') for row in repeated['signals']]
    values = [row['relative_source_projection_difference'] for row in repeated['signals']]
    axes[1].bar(np.arange(len(labels)), values)
    axes[1].set_xticks(np.arange(len(labels)), labels, rotation=35, ha='right')
    axes[1].set(ylabel='Source projection difference / source norm',
                title='Column reversal must preserve exact projector', ylim=(0, .16))
    figure.savefig(args.out/'model_score_numerics.png', dpi=150)
    plt.close(figure)
    report.update(result='initial_score_geometry_replayed_and_permutation_failure_independently_confirmed',
        geometry_report_sha256=sha(args.geometry/'report.json'),
        invariance_report_sha256=sha(args.invariance/'report.json'),
        geometry_and_invariance_exact_replay=True, independent_projection_checks=independent,
        failed_permutation_retained=True, fit_permitted=False, C_H=540, voices_and_moving35_unchanged=True,
        plot_sha256=sha(args.out/'model_score_numerics.png'),
        limitations=['This diagnoses the floating-point construction, not rank or identifiability in exact arithmetic',
            'U.T U = I describes new independent white innovations for fixed U; the observed-initialized basis is data dependent',
            'No actual-fit or phase-recovery claim, no noise confidence interval or physical engine-source separation'])
    print(json.dumps(dict(result=report['result'], independent_checks=independent)), flush=True)
except Exception as exc:
    report.update(result='failed', error=repr(exc))
    raise
finally:
    (args.out/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n',
                                      encoding='utf-8', newline='\n')
