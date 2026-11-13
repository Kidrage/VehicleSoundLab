"""One fresh rapid-control run with observation-driven stage scales and total20 steps."""
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
from quintic_phase_v1.model import QuinticAbsoluteModel
from orthogonal_band_v1.operator import OrthogonalBand
from residual_scale_bootstrap_v1.fit import estimate
from residual_scale_bootstrap_v1.checks import controls


def load(path): return json.loads(path.read_text(encoding='utf-8'))
def save(path, value): path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')


args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.residual-scale-bootstrap-fit/1', result='running', sources={},
    real_audio_read=False, truth_used_by_estimator=False, heldout_used_by_estimator=False,
    model_exported=False, runtime_changed=False, full_qualification=False, original_dense_started=False)
try:
    parent = args.workspace/'references/analysis/orthogonal_band_v1/fit1'; prior = load(parent/'report.json')
    assert prior['result'] == 'known_rapid_control_rejected_dense_not_started'
    sources = {Path(__file__), repo/'research/residual_scale_bootstrap_v1_plan.json'}
    sources.update((repo/'tools/residual_scale_bootstrap_v1').glob('*.py'))
    for name, digest in prior['sources'].items():
        assert sha(repo/name) == sha(parent/'exact_sources'/name) == digest
        sources.add(repo/name)
    for path in sources:
        relative = path.relative_to(repo); dest = args.out/'exact_sources'/relative
        dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path, dest)
        report['sources'][relative.as_posix()] = sha(path)
    report['numeric_libraries'] = dict(numpy=np.__version__, scipy=scipy.__version__, clarabel=clarabel.__version__)
    assert report['numeric_libraries'] == prior['numeric_libraries']
    report['controls'] = controls(); save(args.out/'controls.json', report['controls'])
    known = parent/'known'; inputs = np.load(known/'input.npz')
    time, audio, initial = (inputs[k] for k in ('time', 'audio', 'initial_parameters'))
    plan, settings = load(known/'effective_plan.json'), load(known/'effective_settings.json')
    variant = load(repo/'research/minority_phase_v1_plan.json'); assert settings['maximum_iterations'] == 20
    model = QuinticAbsoluteModel(time, plan, variant, []); model.original.aperture = OrthogonalBand(len(time), plan)
    np.savez_compressed(args.out/'input.npz', time=time, audio=audio, initial_parameters=initial)
    save(args.out/'effective_plan.json', plan); save(args.out/'effective_settings.json', settings)
    report.update(parent_report_sha256=sha(parent/'report.json'), parent_input_sha256=sha(known/'input.npz'),
        parent_fit_sha256=sha(known/'fit.json'), same_physical_initial=True, original_total_iteration_budget=20)
    def progress(row):
        save(args.out/'progress.json', row)
        print(json.dumps(dict(iteration=row['iteration'], stage_scale=row['stage_scale'], accepted=row['accepted'],
            certified=row['qp']['success'], original_cost=row['original_candidate_cost'])), flush=True)
    started = timer.perf_counter()
    parameters, phase, fitted = estimate(model, audio, plan, variant, settings, initial, progress)
    fitted['seconds'] = timer.perf_counter()-started
    save(args.out/'fit.json', fitted)
    np.savez_compressed(args.out/'fit.npz', parameters=parameters, phase_correction=phase)
    # Actual estimator has returned before the saved analytic assessment is read.
    truth = np.load(known/'assessment.npz')['true_phase']; inside = (time >= 5)&(time < 35)
    error = phase-truth; error -= np.median(error[inside])
    p95 = float(np.percentile(abs(error[inside]), 95))
    root = float(np.percentile(abs(np.gradient(phase, time)-np.gradient(truth, time))[inside]/(1+np.gradient(truth, time))[inside], 95))
    certified = sum(row['qp']['success'] for row in fitted['history'])
    passed = bool(p95 <= plan['rules']['maximum_point_phase_p95_cycles'] and root <= plan['rules']['maximum_root_relative_p95']
        and fitted['observation_supported'] and certified == len(fitted['history']) and fitted['original_scale_reached'])
    np.savez_compressed(args.out/'assessment.npz', true_phase=truth, phase_error=error)
    report.update(result='known_bootstrap_passed_NOT_full_qualification' if passed else 'known_bootstrap_rejected',
        assessment=dict(phase_p95_cycles=p95, root_relative_p95=root, passed=passed),
        fit_report_sha256=sha(args.out/'fit.json'), steps=fitted['iterations'], QP_certified=certified,
        accepted_steps=fitted['accepted_steps'], original_scale_reached=fitted['original_scale_reached'],
        final_scale=fitted['final_stage_scale'], original_support=fitted['observation_supported'],
        fixed_original_objective_monotone_on_accepted_steps=True, old_unchanged_solver_controls_reused=True,
        full_goal_complete=False, original_gates_unchanged=True,
        limits=['One known control and one data-derived scale rule; not a strength/initial/window/iteration search',
            'Changing stage objectives; the old fixed-scale objective must also strictly decrease on accepted steps',
            'No nonlinear/global convergence, physical RPM or real-timbre claim',
            'Original36/all17/full33/individual14k/originalE required before real shared-phase DNA'])
    print(json.dumps(dict(result=report['result'], assessment=report['assessment'], final_scale=report['final_scale'])), flush=True)
except Exception as exc:
    report.update(result='failed', error=repr(exc)); raise
finally: save(args.out/'report.json', report)
