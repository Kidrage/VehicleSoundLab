"""Separate robust curvature and waveform linearization on every saved step."""
import argparse
import json
from pathlib import Path
import shutil
import sys

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
args = p.parse_args(); repo = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(args.workspace/'tools/ipm_deps'), str(args.workspace/'tools/qp_deps'), str(args.workspace/'tools/python_deps')]
import numpy as np
from drive_evidence_v1.sources import sha
from quintic_phase_v1.model import QuinticAbsoluteModel
from orthogonal_band_v1.operator import OrthogonalBand
from aperture_model_v1.forward import real_rows
from complex_radial_v1.loss import cost, quadratic
from radial_majorizer_v1.checks import controls as control_checks
from radial_majorizer_v1.geometry import surrogate


def load(path): return json.loads(path.read_text(encoding='utf-8'))
def save(path, value): path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')


args.out.mkdir(parents=True, exist_ok=False)
r = dict(schema='vsl.radial-majorizer-diagnosis/1', result='running', sources={}, trace=[],
    truth_read=False, real_audio_read=False, nonlinear_fit=False, QP_solve=False, model_exported=False, runtime_changed=False)
try:
    parent = args.workspace/'references/analysis/phase_envelope_blocks_v1/fit2'
    old = load(parent/'report.json'); fitted = load(parent/'fit.json'); assert old['result'] == 'known_blocks_rejected'
    sources = {Path(__file__), repo/'research/radial_majorizer_v1_plan.json'}
    sources.update((repo/'tools/radial_majorizer_v1').glob('*.py'))
    for name, digest in old['sources'].items():
        assert sha(repo/name) == sha(parent/'exact_sources'/name) == digest
        sources.add(repo/name)
    for path in sources:
        rel = path.relative_to(repo); dest = args.out/'exact_sources'/rel
        dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path, dest); r['sources'][rel.as_posix()] = sha(path)
    r['controls'] = control_checks(); assert r['controls']['passed']
    r['parent_report_sha256'] = sha(parent/'report.json'); r['parent_fit_sha256'] = sha(parent/'fit.json')
    inputs = np.load(parent/'input.npz'); time, audio, initial = (inputs[k] for k in ('time', 'audio', 'initial_parameters'))
    plan = load(parent/'effective_plan.json'); variant = load(repo/'research/minority_phase_v1_plan.json')
    model = QuinticAbsoluteModel(time, plan, variant, []); model.original.aperture = OrthogonalBand(len(time), plan)
    outer, amplitude = model.unpack(initial); scales = np.asarray(fitted['scales'])
    target = real_rows(model.original.aperture.apply(audio[:, 0]))
    for row in fitted['history']:
        value, jacobian = model.prediction(outer, amplitude, True)
        design = np.column_stack((jacobian, model.design(outer)))*scales[None, :]
        new_outer = np.asarray(row['candidate_outer']); new_amplitude = np.asarray(row['candidate_absolute_amplitudes'])
        step = (np.r_[new_outer, new_amplitude.ravel()]-np.r_[outer, amplitude.ravel()])/scales
        residual = value-target; stage = row['stage_scale']; before = cost(residual, stage)
        gram, g, _, _ = quadratic(residual, design, stage)
        predicted_cost = float(before+g@step+.5*step@gram@step)
        linear = residual+design@step; actual = model.prediction(new_outer, new_amplitude)-target
        linear_cost, actual_cost = cost(linear, stage), cost(actual, stage)
        majorizer_cost = surrogate(residual, linear, stage)
        curvature = linear_cost-predicted_cost; wave = actual_cost-linear_cost
        assert abs(curvature+wave-(actual_cost-predicted_cost)) <= 1e-12
        assert majorizer_cost >= linear_cost-1e-12
        assert actual_cost == row['candidate_cost'] and before == row['before_cost']
        r['trace'].append(dict(iteration=row['iteration'], block=row['block'], accepted=row['accepted'],
            stage_scale=stage, before_cost=before, old_quadratic_candidate=predicted_cost,
            linearized_radial_candidate=linear_cost, actual_candidate=actual_cost,
            curvature_deficit=curvature, waveform_deficit=wave,
            IRLS_majorizer_on_same_linear_step=majorizer_cost,
            majorizer_bound_margin=majorizer_cost-linear_cost,
            linearized_radial_decreases=bool(linear_cost < before),
            actual_decreases=bool(actual_cost < before),
            waveform_vs_linear_residual_norm=float(np.linalg.norm(actual-linear))))
        if row['accepted']: outer, amplitude = new_outer, new_amplitude
    r.update(result='all20_saved_candidate_deficits_decomposed_no_refit',
        angle_amplitude_rejected=[x['iteration'] for x in r['trace'] if x['block'] != 'phase' and not x['accepted']],
        angle_amplitude_linear_radial_increases=[x['iteration'] for x in r['trace'] if x['block'] != 'phase' and not x['linearized_radial_decreases']],
        phase_linear_radial_increases=[x['iteration'] for x in r['trace'] if x['block'] == 'phase' and not x['linearized_radial_decreases']],
        full_goal_complete=False, limits=['Fixed saved steps are not optimized alternatives or source-energy decomposition',
            'IRLS bounds linear residual cost; phase and angle waveform nonlinearity still needs actual cost acceptance'])
except Exception as exc:
    r.update(result='failed', error=repr(exc)); raise
finally: save(args.out/'report.json', r)
print(json.dumps({k: r[k] for k in ('result', 'angle_amplitude_rejected', 'angle_amplitude_linear_radial_increases', 'phase_linear_radial_increases')}), flush=True)
