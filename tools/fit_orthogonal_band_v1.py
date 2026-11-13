"""One known rapid control, then conditionally the original dense36 candidate."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import time as timer

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
args = p.parse_args(); repo = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(args.workspace/'tools/ipm_deps'), str(args.workspace/'tools/qp_deps'), str(args.workspace/'tools/python_deps')]
import numpy as np
import scipy
import clarabel
from drive_evidence_v1.sources import sha
from aperture_model_v1.forward import real_rows
from quintic_phase_v1.model import QuinticAbsoluteModel
from complex_radial_v1.fit import estimate
from orthogonal_band_v1.operator import OrthogonalBand
from orthogonal_band_v1.checks import controls
from orthogonal_band_v1.fixtures import observed, assessment_phase


def load(path): return json.loads(path.read_text(encoding='utf-8'))
def save(path, value): path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')


def fit_case(folder, time, audio, initial, plan, variant, settings):
    folder.mkdir(exist_ok=False)
    save(folder/'effective_plan.json', plan); save(folder/'effective_settings.json', settings)
    np.savez_compressed(folder/'input.npz', time=time, audio=audio, initial_parameters=initial)
    model = QuinticAbsoluteModel(time, plan, variant, [])
    model.original.aperture = OrthogonalBand(len(time), plan)
    def progress(row):
        save(folder/'progress.json', row)
        print(json.dumps(dict(case=folder.name, iteration=row['iteration'], accepted=row['accepted'],
            qp_certified=row['qp']['success'], cost=row['candidate_cost'])), flush=True)
    started = timer.perf_counter()
    parameters, phase, fitted = estimate(model, audio, time, plan, variant, settings, initial, progress)
    fitted['seconds'] = timer.perf_counter()-started
    np.savez_compressed(folder/'fit.npz', parameters=parameters, phase_correction=phase)
    save(folder/'fit.json', fitted)
    return parameters, phase, fitted


args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.orthogonal-band-fit/1', result='running', sources={},
    real_audio_read=False, truth_used_by_estimator=False, heldout_used_by_estimator=False,
    model_exported=False, runtime_changed=False, full_qualification=False)
try:
    parent = args.workspace/'references/analysis/complex_radial_v1/fit1'
    prior = load(parent/'report.json'); plan = load(parent/'effective_plan.json')
    settings = load(parent/'effective_settings.json'); assert settings['maximum_iterations'] == 20
    variant = load(repo/'research/minority_phase_v1_plan.json')
    source = {Path(__file__), repo/'research/orthogonal_band_v1_plan.json'}
    source.update((repo/'tools/orthogonal_band_v1').glob('*.py'))
    for name, digest in prior['sources'].items():
        assert sha(repo/name) == sha(parent/'exact_sources'/name) == digest
        source.add(repo/name)
    for path in source:
        relative = path.relative_to(repo); dest = args.out/'exact_sources'/relative
        dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path, dest)
        report['sources'][relative.as_posix()] = sha(path)
    report['numeric_libraries'] = dict(numpy=np.__version__, scipy=scipy.__version__, clarabel=clarabel.__version__)
    assert report['numeric_libraries'] == prior['numeric_libraries']
    report['parent_report_sha256'] = sha(parent/'report.json')
    report['reused_original_QP_controls'] = dict(path='references/analysis/complex_radial_v1/controls1/report.json',
        sha256=sha(args.workspace/'references/analysis/complex_radial_v1/controls1/report.json'), rerun=False)
    report['controls'] = controls(plan); save(args.out/'controls.json', report['controls'])
    # Known source-list metadata, no original observed audio or truth is loaded here.
    original_base = load(repo/'research/aperture_model_v1_plan.json')
    known_plan = dict(plan, source_orders=original_base['source_orders'])
    time, audio = observed(known_plan)
    known_model = QuinticAbsoluteModel(time, known_plan, variant, []).original
    known_model.aperture = OrthogonalBand(len(time), known_plan)
    zero = np.zeros(known_model.parameter_count)
    _, design = known_model.prediction(zero, True)
    zero[:2*known_model.parts] = np.linalg.lstsq(design[:, :2*known_model.parts],
        real_rows(known_model.aperture.apply(audio[:, 0])), rcond=None)[0]
    lower, upper = known_model.bounds(known_plan, variant)
    assert np.max(lower-zero) <= 0 and np.max(zero-upper) <= 0
    assert not np.any(zero[2*known_model.parts:])
    parameters, phase, fitted = fit_case(args.out/'known', time, audio, zero, known_plan, variant, settings)
    # Analytic phase becomes available to the assessment only AFTER the actual fit.
    truth = assessment_phase(time); interior = (time >= 5)&(time < 35)
    error = phase-truth; error -= np.median(error[interior])
    p95 = float(np.percentile(abs(error[interior]), 95))
    root = float(np.percentile(abs(np.gradient(phase, time)-np.gradient(truth, time))[interior]/
        (1+np.gradient(truth, time))[interior], 95))
    certificates = sum(row['qp']['success'] for row in fitted['history'])
    known_passed = bool(p95 <= plan['rules']['maximum_point_phase_p95_cycles'] and
        root <= plan['rules']['maximum_root_relative_p95'] and certificates == len(fitted['history']) and fitted['observation_supported'])
    report['known'] = dict(result='passed' if known_passed else 'rejected', phase_p95_cycles=p95,
        root_relative_p95=root, QP_certified=certificates, steps=len(fitted['history']),
        parameters=known_model.parameter_count, phase_controls=known_model.phase_count,
        initial_phase_and_envelopes_zero=True, observed_linear_coefficients_only=True,
        fit_report_sha256=sha(args.out/'known/fit.json'))
    np.savez_compressed(args.out/'known/assessment.npz', true_phase=truth, phase_error=error)
    save(args.out/'report.json', report)
    print(json.dumps(dict(known=report['known'])), flush=True)
    if not known_passed:
        report.update(result='known_rapid_control_rejected_dense_not_started', dense_started=False)
    else:
        inputs = np.load(parent/'input.npz')
        time, audio, initial = (inputs[key] for key in ('time', 'audio', 'initial_parameters'))
        report['dense_started'] = True
        report['original_input_sha256'] = sha(parent/'input.npz')
        parameters, phase, fitted = fit_case(args.out/'dense', time, audio, initial, plan, variant, settings)
        # Original truth and heldouts are loaded for original assessment only now.
        from observed_topology_v1.fixtures import make
        from aperture_model_v1.checks import assess
        topology = load(repo/'research/observed_topology_v1_plan.json')
        case = next(row for row in topology['added_cases'] if row['id'] == 'unknown_thirty_six')
        independent_time, independent_audio, truth, _ = make(case, original_base)
        assert np.array_equal(time, independent_time) and np.array_equal(audio, independent_audio)
        assessment, positions, oracle = assess(audio, time, truth, phase, parameters,
            {**plan, 'heldout_orders': original_base['heldout_orders']})
        np.savez_compressed(args.out/'dense/assessment.npz', true_phase=truth, positions=positions, oracle_positions=oracle)
        report['dense'] = dict(assessment=assessment, QP_certified=sum(row['qp']['success'] for row in fitted['history']),
            steps=len(fitted['history']), fit_report_sha256=sha(args.out/'dense/fit.json'))
        report['result'] = 'dense_passed_NOT_full_qualification' if assessment['qualified'] and fitted['observation_supported'] else 'original_dense_rejected'
    report.update(original_gates_unchanged=True, full_goal_complete=False,
        limits=['One orthogonal finite-record band replaces STFT; not a lossless old-observation basis change',
            'Finite-record off-grid and omitted-source leakage persists; white noise units do not calibrate real texture',
            'Fewer orthogonal real rows than dense model variables; constraints and finite optimization do not prove global identifiability',
            'Original36/all17/full33/individual14k/originalE remain before real shared-phase DNA'])
except Exception as exc:
    report.update(result='failed', error=repr(exc)); raise
finally: save(args.out/'report.json', report)
