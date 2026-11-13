"""One parent-method rapid control with exactly the same observed initial state."""
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
from drive_evidence_v1.sources import sha
from quintic_phase_v1.model import QuinticAbsoluteModel
from correlated_observation_v1.marginal import MarginalAperture
from complex_radial_v1.fit import estimate
from orthogonal_band_v1.fixtures import assessment_phase


def load(path): return json.loads(path.read_text(encoding='utf-8'))
def save(path, value): path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')


args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.orthogonal-band-matched-control/1', result='running', sources={},
    real_audio_read=False, truth_used_by_estimator=False, heldout_used_by_estimator=False,
    model_exported=False, runtime_changed=False, full_qualification=False, dense_started=False)
try:
    parent = args.workspace/'references/analysis/orthogonal_band_v1/fit1'
    candidate = load(parent/'report.json'); assert candidate['result'] == 'known_rapid_control_rejected_dense_not_started'
    sources = {Path(__file__), repo/'research/orthogonal_band_v1_matched_control_plan.json'}
    for name, digest in candidate['sources'].items():
        assert sha(repo/name) == sha(parent/'exact_sources'/name) == digest
        sources.add(repo/name)
    for path in sources:
        relative = path.relative_to(repo); dest = args.out/'exact_sources'/relative
        dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path, dest)
        report['sources'][relative.as_posix()] = sha(path)
    report['parent_report_sha256'] = sha(parent/'report.json')
    known = parent/'known'; inputs = np.load(known/'input.npz')
    time, audio, initial = (inputs[k] for k in ('time', 'audio', 'initial_parameters'))
    plan, settings = load(known/'effective_plan.json'), load(known/'effective_settings.json')
    variant = load(repo/'research/minority_phase_v1_plan.json')
    model = QuinticAbsoluteModel(time, plan, variant, [])
    model.original.aperture = MarginalAperture(model.original.aperture)
    save(args.out/'effective_plan.json', plan); save(args.out/'effective_settings.json', settings)
    np.savez_compressed(args.out/'input.npz', time=time, audio=audio, initial_parameters=initial)
    report['exact_same_input_sha256'] = sha(known/'input.npz')
    def progress(row):
        save(args.out/'progress.json', row)
        print(json.dumps(dict(iteration=row['iteration'], accepted=row['accepted'],
            qp_certified=row['qp']['success'], cost=row['candidate_cost'])), flush=True)
    started = timer.perf_counter()
    parameters, phase, fitted = estimate(model, audio, time, plan, variant, settings, initial, progress)
    fitted['seconds'] = timer.perf_counter()-started
    save(args.out/'fit.json', fitted)
    np.savez_compressed(args.out/'fit.npz', parameters=parameters, phase_correction=phase)
    # Assessment truth is independent of any fitting input and requested afterward.
    truth = assessment_phase(time); inside = (time >= 5)&(time < 35)
    error = phase-truth; error -= np.median(error[inside])
    p95 = float(np.percentile(abs(error[inside]), 95))
    root = float(np.percentile(abs(np.gradient(phase, time)-np.gradient(truth, time))[inside]/
        (1+np.gradient(truth, time))[inside], 95))
    certified = sum(row['qp']['success'] for row in fitted['history'])
    passed = bool(p95 <= plan['rules']['maximum_point_phase_p95_cycles'] and root <= plan['rules']['maximum_root_relative_p95']
        and certified == len(fitted['history']) and fitted['observation_supported'])
    np.savez_compressed(args.out/'assessment.npz', true_phase=truth, phase_error=error)
    report.update(result='matched_parent_control_passed' if passed else 'matched_parent_control_rejected',
        assessment=dict(phase_p95_cycles=p95, root_relative_p95=root, passed=passed),
        QP_certified=certified, steps=len(fitted['history']), accepted_steps=fitted['accepted_steps'],
        known_orthogonal_still_rejected=True, original_dense_not_started=True,
        fit_report_sha256=sha(args.out/'fit.json'), full_goal_complete=False)
    print(json.dumps(dict(result=report['result'], assessment=report['assessment'], certified=certified)), flush=True)
except Exception as exc:
    report.update(result='failed', error=repr(exc)); raise
finally: save(args.out/'report.json', report)
