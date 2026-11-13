"""One fixed-budget observed fit with exact same-window marginal noise metric."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import time as timer

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--native', type=Path, required=True)
parser.add_argument('--geometry', type=Path, required=True)
parser.add_argument('--ancestor', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(args.workspace/'tools/ipm_deps'), str(args.workspace/'tools/qp_deps'),
               str(args.workspace/'tools/python_deps')]
import numpy as np
import scipy
import clarabel
from drive_evidence_v1.sources import sha
from quintic_phase_v1.model import QuinticAbsoluteModel
from correlated_observation_v1.marginal import MarginalAperture
from aperture_model_v1.forward import real_rows
from aperture_model_v1.checks import assess
from joint_trust_v1.fit import estimate_with_model
from interior_qp_v1.certified import CertifiedObservedSolver


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')


args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.correlated-observation-fit/1', result='running', sources={},
    real_audio_read=False, model_exported=False, runtime_changed=False, full_qualification=False)
try:
    parent, geometry = load(args.native/'report.json'), load(args.geometry/'report.json')
    assert parent['result'] == 'dense_native_observation_rejected' and parent['qp_certified'] == 20
    assert geometry['result'] == 'marginal_geometry_and_linear_controls_passed' and geometry['controls']['passed']
    assert geometry['native_plan_sha256'] == sha(args.native/'effective_plan.json')
    sources = {Path(__file__), repo/'research/correlated_observation_v1_plan.json'}
    for directory, value in ((args.native, parent), (args.geometry, geometry)):
        for relative, digest in value['sources'].items():
            assert sha(repo/relative) == sha(directory/'exact_sources'/relative) == digest
            sources.add(repo/relative)
    for source in sources:
        relative = source.relative_to(repo)
        target = args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        report['sources'][relative.as_posix()] = sha(source)
    plan, settings = load(args.native/'effective_plan.json'), load(args.native/'effective_settings.json')
    assert settings['maximum_iterations'] == 20
    variant = load(repo/'research/minority_phase_v1_plan.json')
    original = np.load(args.native/'input.npz')
    time, audio, initial = (original[key] for key in ('time', 'audio', 'initial_parameters'))
    model = QuinticAbsoluteModel(time, plan, variant, [])
    before_samples = model.original.samples(initial)[0]
    model.original.aperture = MarginalAperture(model.original.aperture)
    assert np.array_equal(before_samples, model.original.samples(initial)[0])
    report.update(parent_report_sha256=sha(args.native/'report.json'), geometry_report_sha256=sha(args.geometry/'report.json'),
        native_input_sha256=sha(args.native/'input.npz'), ancestor_report_sha256=sha(args.ancestor/'report.json'),
        initial_parameters_unchanged=True, waveform_and_bounds_unchanged=True,
        marginal_white_variance_preserved=True, interwindow_whitening=False,
        numeric_libraries=dict(numpy=np.__version__, scipy=scipy.__version__, clarabel=clarabel.__version__))
    assert report['numeric_libraries'] == parent['numeric_libraries']
    np.savez_compressed(args.out/'input.npz', time=time, audio=audio, initial_parameters=initial)
    save(args.out/'effective_plan.json', plan)
    save(args.out/'effective_settings.json', settings)
    target = real_rows(model.original.aperture.apply(audio[:, 0]))
    solver = CertifiedObservedSolver(target, plan['soft_l1_scale'])
    def progress(row):
        save(args.out/'progress.json', row)
        print(json.dumps(dict(iteration=row['iteration'], accepted=row['accepted'],
            qp_certified=row['qp']['success'], cost=row['candidate_cost'])), flush=True)
    started = timer.perf_counter()
    parameters, phase, fit = estimate_with_model(model, audio, time, plan, variant,
        settings, initial, progress, qp_solver=solver)
    fit['seconds'] = timer.perf_counter()-started
    np.savez_compressed(args.out/'fit.npz', parameters=parameters, phase_correction=phase)
    report['fit'] = fit
    # Analytic fixture truth and held-out orders are only accessed after fitting.
    truth = np.load(args.ancestor/'fit.npz')['true_phase_correction']
    heldouts = load(repo/'research/aperture_model_v1_plan.json')['heldout_orders']
    assessment, positions, oracle = assess(audio, time, truth, phase, parameters,
        {**plan, 'heldout_orders': heldouts})
    report['assessment'] = assessment
    np.savez_compressed(args.out/'coordinates.npz', positions=positions, oracle_positions=oracle)
    report.update(result='dense_marginal_metric_passed_not_full_qualification' if assessment['qualified'] and fit['observation_supported'] else 'dense_marginal_metric_rejected',
        qp_certified=sum(row['qp']['success'] for row in fit['history']),
        original_gates_unchanged=True, source_candidates_unchanged=True,
        limitations=['Same-window composite metric; overlapping noise is not jointly whitened',
            'Out-of-band sensitivity increases despite bounded raw-source norm',
            'No real coloured-noise calibration or convergence guarantee',
            'Original failed dense positive/all17/full33/individual14kHz/original E remain required'])
    print(json.dumps(dict(result=report['result'], qp_certified=report['qp_certified'],
        phase_p95=assessment['point_phase_p95_cycles'])), flush=True)
except Exception as exc:
    report.update(result='failed', error=repr(exc))
    raise
finally:
    save(args.out/'report.json', report)
