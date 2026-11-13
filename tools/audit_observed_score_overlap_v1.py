"""Independent complex sources, explicit 2D Hessians and scalar window matrices."""
import argparse
import json
from pathlib import Path
import shutil
import sys

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
args = p.parse_args(); repo = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(args.workspace/'tools/python_deps')]
import numpy as np
from scipy.linalg import svd
from drive_evidence_v1.sources import sha
from quintic_phase_v1.model import QuinticAbsoluteModel
from aperture_model_v1.forward import Aperture, real_rows
from correlated_observation_v1.marginal import MarginalAperture
from complex_radial_v1.loss import gradient


def load(path): return json.loads(path.read_text(encoding='utf-8'))
def save(path, value): path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')
def relative(a, b): return float(np.linalg.norm(a-b)/max(np.linalg.norm(b), 1e-300))


args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.observed-score-overlap-audit/1', result='running', sources={}, cases=[],
    real_audio_read=False, truth_read=False, heldout_used=False, estimator_rerun=False,
    model_exported=False, runtime_changed=False)
try:
    parent = args.workspace/'references/analysis/observed_score_overlap_v1/observe1'
    observed = load(parent/'report.json'); assert observed['controls']['passed']
    assert observed['result'] == 'frozen_observed_initialization_and_exact_score_overlap_measured'
    for name, digest in observed['sources'].items():
        assert sha(repo/name) == sha(parent/'exact_sources'/name) == digest
    for path in {Path(__file__), repo/'research/observed_score_overlap_v1_audit_cancellation_plan.json'} | {repo/name for name in observed['sources']}:
        relative_path = path.relative_to(repo); dest = args.out/'exact_sources'/relative_path
        dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path, dest)
        report['sources'][relative_path.as_posix()] = sha(path)
    report['parent_report_sha256'] = sha(parent/'report.json')
    previous = None
    for item in observed['parent_report_chain']:
        path = args.workspace/item['path']; assert sha(path) == item['sha256']
        r = load(path)
        if previous is not None: assert previous['parent_report_sha256'] == item['sha256']
        previous = r
    original = np.load(args.workspace/'references/analysis/complex_radial_v1/fit1/input.npz')
    saved = np.load(parent/'input.npz'); time = saved['time']; audio = saved['audio'][:, 0]
    assert all(np.array_equal(saved[k], original[k]) for k in ('time', 'audio', 'initial_parameters'))
    for item in observed['input_identities']:
        path = args.workspace/item['path']; assert sha(path) == item['sha256']
        assert np.array_equal(np.load(path)[item['array']], saved['initial_parameters'])
    plan = load(parent/'effective_plan.json'); variant = load(repo/'research/minority_phase_v1_plan.json')
    model = QuinticAbsoluteModel(time, plan, variant, []).original
    start = 2*model.parts; direction = saved['phase_control_direction']
    assert np.array_equal(direction, saved['final_parameters'][start:start+model.phase_count]-
        saved['initial_parameters'][start:start+model.phase_count])
    # Construct the independent observation matrix locally, never a full inverse.
    size = round(plan['projection_cycles']*plan['samples_per_cycle'])
    hop = round(plan['projection_hop_cycles']*plan['samples_per_cycle'])
    starts = np.arange(0, len(time)-size+1, hop)
    bins = np.arange(round(plan['observed_order_range'][0]*plan['projection_cycles']),
        round(plan['observed_order_range'][1]*plan['projection_cycles'])+1)
    angle = 2*np.pi*bins[:, None]*np.arange(size)[None, :]/size
    window = np.sin(np.pi*np.arange(size)/size)**2
    base = 2/window.sum()*window[None, :]*(np.cos(angle)-1j*np.sin(angle))
    factor = np.zeros((len(bins), len(bins)+2))
    for k in range(len(bins)): factor[k, k:k+3] = [1/np.sqrt(6), -2/np.sqrt(6), 1/np.sqrt(6)]
    u, singular, _ = svd(factor, full_matrices=False, lapack_driver='gesvd')
    symmetric = (u/singular)@u.T
    matrices = dict(native=base, marginal=symmetric@base)
    for state in ('initial', 'final'):
        parameters = saved[state+'_parameters']; count = model.parts
        phase = model.phase_basis@parameters[2*count:2*count+model.phase_count]
        envelope = 1+model.envelope_basis@parameters[2*count+model.phase_count:model.base_count].reshape(count, -1).T
        complex_sources = envelope*np.exp(2j*np.pi*(time[:, None]+phase[:, None])*model.orders)*(
            parameters[:count]-1j*parameters[count:2*count])
        samples = complex_sources.real.sum(axis=1)
        derivative = -(complex_sources.imag*2*np.pi*model.orders).sum(axis=1)[:, None]*model.phase_basis
        source_wave_error = float(abs(samples-model.samples(parameters)[0]).max())
        assert source_wave_error < 1e-12
        for metric in ('native', 'marginal'):
            tag = state+'_'+metric; row = next(x for x in observed['cases'] if x['id'] == tag)
            path = parent/(tag+'.npz'); assert sha(path) == row['arrays_sha256']
            expected = np.load(path)
            pullback = np.zeros_like(derivative); independent = np.zeros((model.phase_count, model.phase_count))
            score = np.zeros(model.phase_count)
            original_operator = Aperture(len(time), plan)
            if metric == 'marginal': original_operator = MarginalAperture(original_operator)
            original_samples, original_jacobian = model.samples(parameters, True)
            original_jacobian = original_jacobian[:, 2*count:2*count+model.phase_count]
            original_residual = real_rows(original_operator.apply(original_samples-audio))
            original_projected = real_rows(original_operator.apply(original_jacobian))
            original_psi = gradient(original_residual, plan['soft_l1_scale'])
            bins_count = len(bins); observations = len(starts)*bins_count
            de2 = dj2 = norm_j2 = 0.; alt_abs_products = np.zeros(model.phase_count)
            for window_index, offset in enumerate(starts):
                rotation = np.cos(2*np.pi*bins*offset/size)-1j*np.sin(2*np.pi*bins*offset/size)
                matrix = rotation[:, None]*matrices[metric]
                z = matrix@(samples[offset:offset+size]-audio[offset:offset+size])
                j = matrix@derivative[offset:offset+size]
                scale = plan['soft_l1_scale']; f = np.sqrt(1+(z.real**2+z.imag**2)/scale**2)
                h00 = 1/f-z.real**2/(scale**2*f**3)
                h11 = 1/f-z.imag**2/(scale**2*f**3)
                h01 = -z.real*z.imag/(scale**2*f**3)
                w0 = h00[:, None]*j.real+h01[:, None]*j.imag
                w1 = h01[:, None]*j.real+h11[:, None]*j.imag
                local = matrix.real.T@w0+matrix.imag.T@w1
                pullback[offset:offset+size] += local; independent += local.T@local
                score += j.real.T@(z.real/f)+j.imag.T@(z.imag/f)
                selected = np.r_[np.arange(window_index*bins_count, (window_index+1)*bins_count),
                    observations+np.arange(window_index*bins_count, (window_index+1)*bins_count)]
                real_j = np.r_[j.real, j.imag]; real_z = np.r_[z.real, z.imag]
                de2 += float(np.sum((real_z-original_residual[selected])**2))
                dj2 += float(np.sum((real_j-original_projected[selected])**2))
                norm_j2 += float(np.sum(real_j**2))
                alt_abs_products += abs(j.real).T@abs(z.real/f)+abs(j.imag).T@abs(z.imag/f)
            full = pullback.T@pullback
            errors = dict(source_pullback=relative(pullback, expected['source_pullback']),
                full_covariance=relative(full, expected['full_covariance']),
                independent_covariance=relative(independent, expected['independent_window_covariance']),
                score=relative(score, expected['score']))
            eps = np.finfo(float).eps; operations = len(original_residual)+len(starts)
            gamma = operations*eps/(1-operations*eps)
            analytic_bound = np.sqrt(dj2)*np.linalg.norm(original_psi)+np.sqrt(norm_j2*de2)
            rounding_bound = gamma*(np.linalg.norm(abs(original_projected).T@abs(original_psi))+
                np.linalg.norm(alt_abs_products))+20*eps*np.sqrt(norm_j2)*np.linalg.norm(original_psi)
            score_difference = float(np.linalg.norm(score-expected['score']))
            score_check = dict(original_relative_gate=1e-10, original_relative_error=errors['score'],
                original_relative_gate_passed=bool(errors['score'] < 1e-10),
                absolute_difference=score_difference, original_score_norm=float(np.linalg.norm(expected['score'])),
                residual_difference_norm=float(np.sqrt(de2)), jacobian_difference_norm=float(np.sqrt(dj2)),
                Lipschitz_bound=float(analytic_bound), rounding_bound=float(rounding_bound),
                additional_forward_bound_passed=bool(score_difference <= analytic_bound+rounding_bound))
            report['current_case'] = dict(id=tag, errors=errors, score_check=score_check)
            assert max(v for k, v in errors.items() if k != 'score') < 1e-10
            assert score_check['additional_forward_bound_passed']
            ratio = full.diagonal()/independent.diagonal()
            assert relative(ratio, expected['variance_ratios']) < 1e-10
            direct = float(direction@full@direction); other = float(direction@independent@direction)
            assert abs(direct/other-row['directional_full_over_independent']) < 1e-10
            report['cases'].append(dict(id=tag, source_waveform_maximum_error=source_wave_error,
                independent_relative_errors=errors, score_check=score_check,
                directional_full_over_independent=direct/other))
            print(json.dumps(dict(id=tag, maximum_relative_error=max(errors.values()))), flush=True)
    report.update(result='four_covariance_geometries_rebuilt_score_relative_gate_separately_retained',
        all_original_score_relative_gates_passed=all(x['score_check']['original_relative_gate_passed'] for x in report['cases']),
        original_phase_error_cause_proved=False, fitted_phase_uncertainty=False,
        new_real_DNA_permitted=False, full_goal_complete=False,
        limits=observed['limits'])
except Exception as exc:
    report.update(result='failed', error=repr(exc)); raise
finally: save(args.out/'report.json', report)
