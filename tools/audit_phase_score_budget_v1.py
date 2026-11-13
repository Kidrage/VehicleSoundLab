"""Independent scalar-trig/2x2/QR/SVD checks of frozen rank failure and all stages."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import sys

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
args = p.parse_args(); repo = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(args.workspace/'tools/python_deps')]
import numpy as np
from scipy.linalg import svd, qr
from drive_evidence_v1.sources import sha
from phase_score_budget_v1.checks import controls
from quintic_phase_v1.model import QuinticAbsoluteModel
from correlated_observation_v1.marginal import MarginalAperture
from aperture_model_v1.forward import real_rows


def load(path): return json.loads(path.read_text(encoding='utf-8'))


def independent_raw(model, outer, amplitudes):
    m = model.original; trajectory = m.time+m.phase_basis@outer[m.parts:m.parts+m.phase_count]
    cols = []; common = np.zeros(len(m.time)); amplitude_columns = []
    for k, order in enumerate(m.orders):
        angle = 2*np.pi*trajectory*order+outer[k]
        envelope = sum(model.full[:, j]*amplitudes[k, j] for j in range(model.controls))
        column = -envelope*np.sin(angle); cols.append(column); common += column*2*np.pi*order
        amplitude_columns.extend(np.cos(angle)*model.full[:, j] for j in range(model.controls))
    return np.column_stack((*cols, *(common*m.phase_basis[:, j] for j in range(m.phase_count)), *amplitude_columns))


def block_root(residual, matrix, scale):
    count = len(residual)//2; r = np.column_stack((residual[:count], residual[count:]))
    norm = np.hypot(r[:, 0], r[:, 1]); v = 1/np.hypot(1., norm/scale)
    unit = np.divide(r, norm[:, None], out=np.zeros_like(r), where=norm[:, None] > 0)
    projector = np.einsum('ni,nj->nij', unit, unit)
    root = np.sqrt(v)[:, None, None]*(np.eye(2)[None]-projector)+v[:, None, None]**1.5*projector
    pairs = np.stack((matrix[:count], matrix[count:]), axis=1)
    result = np.einsum('nij,njk->nik', root, pairs)
    return np.concatenate((result[:, 0], result[:, 1]))


args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.phase-score-budget-audit/1', result='running', sources={}, stages=[],
    real_audio_read=False, model_exported=False, runtime_changed=False, nonlinear_estimator_rerun=False,
    quadratic_solver_rerun=False, phase_response_calculated=False, full_qualification=False)
try:
    root = args.workspace/'references/analysis/phase_score_budget_v1'
    failed = load(root/'diagnosis1/report.json'); rank = load(root/'rank1/report.json')
    assert failed['result'] == 'failed' and rank['result'] == 'rank_loss_localized_without_phase_response_or_model_change'
    assert rank['previous_failure_sha256'] == sha(root/'diagnosis1/report.json')
    paths = {Path(__file__)}
    for folder in (root/'diagnosis1', root/'rank1'):
        for name, digest in load(folder/'report.json')['sources'].items():
            assert sha(repo/name) == sha(folder/'exact_sources'/name) == digest
            paths.add(repo/name)
    for path in paths:
        relative = path.relative_to(repo); dest = args.out/'exact_sources'/relative
        dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path, dest)
        report['sources'][relative.as_posix()] = sha(path)
    assert controls() == failed['controls']
    snapshot = root/'diagnosis1/exact_sources/tools/phase_score_budget_v1/projection.py'
    spec = importlib.util.spec_from_file_location('frozen_phase_response_failure', snapshot)
    frozen_module = importlib.util.module_from_spec(spec); spec.loader.exec_module(frozen_module)
    parent = args.workspace/'references/analysis/complex_radial_v1/fit1'
    assert rank['parent_fit_sha256'] == sha(parent/'fit.npz') and rank['parent_input_sha256'] == sha(parent/'input.npz')
    inputs = np.load(parent/'input.npz'); fitted = np.load(parent/'fit.npz'); saved = np.load(root/'rank1/rank.npz')
    plan = load(parent/'effective_plan.json'); variant = load(repo/'research/minority_phase_v1_plan.json')
    fit = load(parent/'report.json'); scales = np.asarray(fit['fit']['scales'])
    model = QuinticAbsoluteModel(inputs['time'], plan, variant, [])
    outer, amplitudes = model.unpack(fitted['parameters']); raw = independent_raw(model, outer, amplitudes)
    indices = np.arange(model.parts, model.parts+model.original.phase_count)
    assert np.array_equal(indices, saved['phase_indices']) and np.array_equal(scales, saved['scales'])
    matrices = [('raw_samples', raw*scales[None, :])]; helper_errors = {}
    # Forward-check independent scalar trig against the executed model; build
    # observation stages from canonical model arithmetic for bitwise replay.
    for metric in ('native', 'marginal'):
        if metric == 'marginal': model.original.aperture = MarginalAperture(model.original.aperture)
        value, derivative = model.prediction(outer, amplitudes, True)
        original = np.column_stack((derivative, model.design(outer)))
        independent = real_rows(model.original.aperture.apply(raw))
        error = float(abs(independent-original).max()); assert error <= 1e-12
        helper_errors[metric] = error
        matrix = original*scales[None, :]
        residual = value-real_rows(model.original.aperture.apply(inputs['audio'][:, 0]))
        weighted = block_root(residual, matrix, plan['soft_l1_scale'])
        matrices.extend(((metric, matrix), (metric+'_radial', weighted)))
        if metric == 'native':
            # Failure is independent of RHS and occurs before any response use.
            from complex_radial_v1.loss import hessian_apply
            exact = hessian_apply(residual, matrix, plan['soft_l1_scale'], .5)
            assert np.linalg.norm(exact-weighted)/np.linalg.norm(exact) <= 1e-12
            try: frozen_module.profile(exact, indices, np.zeros((len(exact), 4)))
            except ValueError as exc: failure_message = repr(exc)
            else: raise AssertionError('Original failed full-rank gate no longer fails')
            assert failure_message == failed['error']
    for (name, matrix), original in zip(matrices, rank['stages']):
        assert name == original['stage']
        free = np.setdiff1d(np.arange(matrix.shape[1]), indices)
        nuisance, common = matrix[:, free], matrix[:, indices]
        cutoff = np.finfo(float).eps*max(matrix.shape)*np.linalg.norm(matrix, 'fro')
        assert abs(cutoff-original['cutoff']) <= 1e-12*original['cutoff']
        u, s, _ = svd(nuisance, full_matrices=False, lapack_driver='gesvd')
        nuisance_rank = int(np.sum(s > cutoff))
        projected = common-u[:, :nuisance_rank]@(u[:, :nuisance_rank].T@common)
        phase_singular = svd(projected, full_matrices=False, compute_uv=False, lapack_driver='gesvd')
        full = svd(matrix, full_matrices=False, compute_uv=False, lapack_driver='gesvd')
        ranks = dict(nuisance_rank=nuisance_rank, conditional_phase_rank=int(np.sum(phase_singular > cutoff)),
            full_rank=int(np.sum(full > cutoff)))
        assert all(ranks[k] == original[k] for k in ranks)
        errors = {}
        for key, values in (('nuisance_singular', s), ('phase_singular', phase_singular), ('full_singular', full)):
            reference = saved[name+'_'+key]
            errors[key] = float(np.linalg.norm(values-reference)/max(np.linalg.norm(reference), 1e-30))
        assert max(errors.values()) <= 1e-6, errors
        # QR diagonals are a second rank indicator, not interchangeable with a
        # singular-value cutoff. Record any numerical count difference honestly.
        _, r, pivots = qr(nuisance, mode='economic', pivoting=True)
        qr_count = int(np.sum(abs(r.diagonal()) > cutoff))
        direction = saved[name+'_weakest_nuisance_direction']
        null_norm = float(np.linalg.norm(nuisance@direction))
        assert abs(np.linalg.norm(direction)-1) <= 1e-12
        assert abs(null_norm-original['weakest_nuisance_norm']) <= 1e-12*max(1., np.linalg.norm(matrix, 'fro'))
        report['stages'].append(dict(stage=name, **ranks, pivoted_QR_diagonal_count=qr_count,
            independent_SVD_relative_errors=errors, weakest_nuisance_norm=null_norm,
            same_rank_cutoff=True, canonical_matrix_columns=matrix.shape[1]))
        print(json.dumps(dict(audited_stage=name, **ranks, QR_count=qr_count)), flush=True)
    previous = args.workspace/'references/analysis/complex_radial_v1/final1'
    for name in ('C_files_sha256.json', 'voice_files_sha256.json'):
        assert all(sha(repo/file) == digest for file, digest in load(previous/name).items())
    report.update(result='original_failure_and_allfive_rank_stages_independently_reproduced',
        diagnosis_report_sha256=sha(root/'diagnosis1/report.json'), rank_report_sha256=sha(root/'rank1/report.json'),
        original_failure_replayed=failure_message, original_known_controls_replayed=True,
        scalar_trig_observed_maximum_errors=helper_errors, C_H=540, voices_and_moving35_unchanged=True,
        limits=['QR diagonal and SVD numerical rank definitions differ; only singular-value ranks use declared gate',
            'Conditional phase rank after nuisance truncation is not a qualification; full joint ranks are lower than naive block sum',
            'No phase response was rescued, no threshold changed and no bounded/nonlinear solver rerun'])
except Exception as exc:
    report.update(result='failed', error=repr(exc)); raise
finally:
    (args.out/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')
