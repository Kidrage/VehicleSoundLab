"""One original joint rapid14 fit with derived IRLS curvature and TOTAL20 steps."""
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
from joint_radial_majorizer_v1.fit import estimate


def load(path): return json.loads(path.read_text(encoding='utf-8'))
def save(path, value): path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')


args.out.mkdir(parents=True, exist_ok=False)
r = dict(schema='vsl.joint-radial-majorizer-fit/1', result='running', sources={}, real_audio_read=False,
    truth_used_by_estimator=False, heldout_used_by_estimator=False, model_exported=False, runtime_changed=False,
    original_dense_started=False, full_qualification=False, full_goal_complete=False)
try:
    parent = args.workspace/'references/analysis/radial_majorizer_v1/fit1'
    prior = load(parent/'report.json'); previous = load(parent/'fit.json'); assert prior['result'] == 'known_majorizer_rejected'
    diagnosis = args.workspace/'references/analysis/radial_majorizer_v1/diagnosis1'; diagnosed = load(diagnosis/'report.json')
    assert diagnosed['result'] == 'all20_saved_candidate_deficits_decomposed_no_refit' and diagnosed['controls']['passed']
    assert prior['diagnosis_report_sha256'] == sha(diagnosis/'report.json')
    sources = {Path(__file__), repo/'research/joint_radial_majorizer_v1_plan.json'}
    sources.update((repo/'tools/joint_radial_majorizer_v1').glob('*.py'))
    for folder, report in ((parent, prior), (diagnosis, diagnosed)):
        for name, digest in report['sources'].items():
            assert sha(repo/name) == sha(folder/'exact_sources'/name) == digest
            sources.add(repo/name)
    for path in sources:
        rel = path.relative_to(repo); dest = args.out/'exact_sources'/rel
        dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path, dest); r['sources'][rel.as_posix()] = sha(path)
    r['controls'] = diagnosed['controls']; r['controls_reused_by_source_identity'] = True
    r['unchanged_QP_controls_reused'] = prior['unchanged_restricted_QP_controls_reused']
    r['numeric_libraries'] = dict(numpy=np.__version__, scipy=scipy.__version__, clarabel=clarabel.__version__)
    assert r['numeric_libraries'] == prior['numeric_libraries']
    inputs = np.load(parent/'input.npz'); time, audio, initial = (inputs[k] for k in ('time', 'audio', 'initial_parameters'))
    plan, settings = load(parent/'effective_plan.json'), load(parent/'effective_settings.json')
    variant = load(repo/'research/minority_phase_v1_plan.json'); assert settings['maximum_iterations'] == 20
    model = QuinticAbsoluteModel(time, plan, variant, []); model.original.aperture = OrthogonalBand(len(time), plan)
    np.savez_compressed(args.out/'input.npz', time=time, audio=audio, initial_parameters=initial)
    save(args.out/'effective_plan.json', plan); save(args.out/'effective_settings.json', settings)
    r.update(parent_report_sha256=sha(parent/'report.json'), parent_fit_sha256=sha(parent/'fit.json'),
        parent_input_sha256=sha(parent/'input.npz'), diagnosis_report_sha256=sha(diagnosis/'report.json'),
        same_physical_initial=True, original_total_iteration_budget=20, original_initial_scales_preserved=True,
        certificate_scope='original_joint_all_variables')
    def progress(row):
        save(args.out/'progress.json', row)
        print(json.dumps(dict(iteration=row['iteration'], accepted=row['accepted'],
            certified=row['qp']['success'], original_cost=row['original_candidate_cost'])), flush=True)
    started = timer.perf_counter()
    parameters, phase, fitted = estimate(model, audio, plan, variant, settings, initial, progress)
    fitted['seconds'] = timer.perf_counter()-started
    assert np.array_equal(np.asarray(fitted['scales']), np.asarray(previous['scales']))
    save(args.out/'fit.json', fitted); np.savez_compressed(args.out/'fit.npz', parameters=parameters, phase_correction=phase)
    # Truth is first opened only AFTER actual estimator returned.
    truth = np.load(parent/'assessment.npz')['true_phase']; inside = (time >= 5)&(time < 35)
    error = phase-truth; error -= np.median(error[inside]); p95 = float(np.percentile(abs(error[inside]), 95))
    root = float(np.percentile(abs(np.gradient(phase, time)-np.gradient(truth, time))[inside]/(1+np.gradient(truth, time))[inside], 95))
    certified = sum(x['qp']['success'] for x in fitted['history'])
    passed = bool(p95 <= plan['rules']['maximum_point_phase_p95_cycles'] and root <= plan['rules']['maximum_root_relative_p95']
        and fitted['observation_supported'] and fitted['original_scale_reached'] and certified == fitted['iterations'])
    np.savez_compressed(args.out/'assessment.npz', true_phase=truth, phase_error=error)
    r.update(result='known_joint_majorizer_passed_NOT_full_qualification' if passed else 'known_joint_majorizer_rejected',
        assessment=dict(phase_p95_cycles=p95, root_relative_p95=root, passed=passed), fit_report_sha256=sha(args.out/'fit.json'),
        steps=fitted['iterations'], QP_certified=certified, accepted_steps=fitted['accepted_steps'],
        original_scale_reached=fitted['original_scale_reached'], final_scale=fitted['final_stage_scale'],
        original_support=fitted['observation_supported'],
        limits=['One same-input known fit and one analytically derived curvature; no sweep or added budget',
            'Majorization applies to residual-space or exactly linear amplitude updates; phase/angle waveform remains nonlinear',
            'Full-QP certificates do not establish nonlinear optimality or physical RPM/timbre recovery',
            'Original36/all17/full33/individual14k/originalE required before real sharedphase DNA'])
except Exception as exc:
    r.update(result='failed', error=repr(exc)); raise
finally: save(args.out/'report.json', r)
print(json.dumps(dict(result=r['result'], assessment=r['assessment'], final_scale=r['final_scale'])), flush=True)
