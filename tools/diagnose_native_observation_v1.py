"""One native-bin observation candidate using the unchanged certified estimator."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import time as timer

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--parent', type=Path, required=True)
parser.add_argument('--observed', type=Path, required=True)
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
from aperture_model_v1.checks import assess
from aperture_model_v1.forward import real_rows
from joint_trust_v1.fit import estimate_with_model
from interior_qp_v1.certified import CertifiedObservedSolver
from native_observation_v1.geometry import complete
from native_observation_v1.checks import controls


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')


args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.native-observation-diagnosis/1', result='running', sources={},
    real_audio_read=False, real_source_permitted=False, qualification_changed=False,
    runtime_changed=False, model_exported=False, audio_exported=False)
try:
    parent = load(args.parent/'report.json')
    observed = load(args.observed/'report.json')
    assert parent['result'] == 'dense_diagnostic_rejected' and parent['qp_certified'] == 20
    assert observed['parent_report_sha256'] == sha(args.parent/'report.json')
    settings, chain = {}, []
    path = repo/'research/native_observation_v1_plan.json'
    while True:
        value = load(path)
        chain.append((path, value))
        if path == repo/'research/joint_trust_precise_v1_plan.json':
            break
        path = repo/value['parent_plan']
    for _, value in reversed(chain):
        settings.update(value)
    sources = {Path(__file__)} | {path for path, _ in chain}
    sources.update((repo/'tools/native_observation_v1').glob('*.py'))
    for name, digest in parent['sources'].items():
        assert sha(repo/name) == sha(args.parent/'exact_sources'/name) == digest
        sources.add(repo/name)
    for path in sources:
        relative = path.relative_to(repo)
        target = args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        report['sources'][relative.as_posix()] = sha(path)
    report['numeric_libraries'] = dict(numpy=np.__version__, scipy=scipy.__version__, clarabel=clarabel.__version__)
    assert report['numeric_libraries'] == parent['numeric_libraries']
    previous = load(args.parent/'effective_plan.json')
    plan, geometry = complete(previous)
    report['controls'] = controls(previous)
    report['geometry'] = geometry
    save(args.out/'controls.json', report['controls'])
    saved = np.load(args.parent/'fit.npz')
    original = np.load(args.observed/'input.npz')
    time, audio, initial = original['time'], original['original_observed_audio'], saved['initial_parameters']
    assert np.array_equal(time, saved['time']) and np.array_equal(initial, original['initial_parameters'])
    variant = load(repo/'research/minority_phase_v1_plan.json')
    model, old = (QuinticAbsoluteModel(time, value, variant, []) for value in (plan, previous))
    outer, amplitude = model.unpack(initial)
    assert np.array_equal(model.original.samples(initial)[0], old.original.samples(initial)[0])
    assert np.array_equal(model.original.phase_basis, old.original.phase_basis)
    assert np.array_equal(model.original.envelope_basis, old.original.envelope_basis)
    assert np.array_equal(model.original.bounds(plan, variant), old.original.bounds(previous, variant))
    np.savez_compressed(args.out/'input.npz', time=time, audio=audio, initial_parameters=initial)
    save(args.out/'effective_plan.json', plan)
    save(args.out/'effective_settings.json', settings)
    report.update(parent_report_sha256=sha(args.parent/'report.json'), observed_report_sha256=sha(args.observed/'report.json'),
        unchanged_waveform_phase_amplitude_bounds_and_initial=True)
    target = real_rows(model.original.aperture.apply(audio[:, 0]))
    solver = CertifiedObservedSolver(target, plan['soft_l1_scale'])
    print(json.dumps(dict(status='independent_projection_controls_passed',
        old_real_rows=report['controls']['old_real_rows'], new_real_rows=len(target), unchanged_parameters=len(initial))), flush=True)
    def progress(row):
        save(args.out/'progress.json', row)
        print(json.dumps(dict(iteration=row['iteration'], accepted=row['accepted'], qp_certified=row['qp']['success'],
            cost=row['candidate_cost'])), flush=True)
    started = timer.perf_counter()
    parameters, phase, fit = estimate_with_model(model, audio, time, plan, variant, settings, initial, progress, qp_solver=solver)
    fit['seconds'] = timer.perf_counter()-started
    report['fit'] = fit
    np.savez_compressed(args.out/'fit.npz', parameters=parameters, phase_correction=phase)
    # Analytic truth and spectral heldouts are evaluation-only, after fitting.
    base = load(repo/'research/aperture_model_v1_plan.json')
    assessment, positions, oracle = assess(audio, time, saved['true_phase_correction'], phase, parameters,
        {**plan, 'heldout_orders': base['heldout_orders']})
    report['assessment'] = assessment
    np.savez_compressed(args.out/'coordinates.npz', positions=positions, oracle_positions=oracle)
    report.update(result='dense_native_observation_passed_not_full_qualification' if assessment['qualified'] and fit['observation_supported'] else 'dense_native_observation_rejected',
        qp_certified=sum(row['qp']['success'] for row in fit['history']),
        full_qualification=False, original_gates_unchanged=True,
        limits=['Native-bin quadrature and Hann-energy controls do not establish rapid/occlusion phase-estimator qualification',
            'The observation completion preserves source candidates and waveform but changes the statistical weighting; adjacent Hann bins remain correlated',
            'Original failed dense positive/all17/full33/individual14kHz/original E remain required; no real audio/model/C'])
    print(json.dumps(dict(result=report['result'], qp_certified=report['qp_certified'],
        phase_p95=assessment['point_phase_p95_cycles'])), flush=True)
except Exception as exc:
    report.update(result='failed', error=repr(exc))
    raise
finally:
    save(args.out/'report.json', report)
