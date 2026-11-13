"""Actual POST LTV kernels and joint periodic/independent zero-lag allocation."""
import argparse
import shutil
import sys
from pathlib import Path
p = argparse.ArgumentParser(description=__doc__)
for key in ['workspace', 'out']: p.add_argument('--'+key, type=Path, required=True)
a = p.parse_args(); repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(a.workspace/'tools/python_deps'))
import numpy as np
from scipy import signal, stats
from research_archive_v1 import load, save, sha
from idle_post_budget_v1.response import support, kernels, matrices, operator_error
from idle_post_budget_v1.budget import summarize, allocate, prediction, PAIRS
from idle_post_budget_v1.checks import run


def serial(state): return {k: v.tolist() for k, v in state.items()}


a.out.mkdir(parents=True, exist_ok=False)
r = dict(result='running', sources={}, inputs={}, parent_manifests={})
try:
    plan_path = repo/'research/idle_post_budget_v1_plan.json'; plan = load(plan_path)
    for path in [Path(__file__), plan_path, repo/'tools/research_archive_v1.py', repo/'tools/idle_wave_budget_v1/moments.py',
                 *sorted((repo/'tools/idle_post_budget_v1').glob('*.py'))]:
        name = path.relative_to(repo); dest = a.out/'exact_sources'/name
        dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path, dest); r['sources'][name.as_posix()] = sha(path)
    r['known'] = run(); print(dict(stage='known', result=r['known']), flush=True)
    tables = {}
    for name in plan['parents']:
        root = a.workspace/'baselines'/name; r['parent_manifests'][name] = sha(root/'manifest.json')
        tables[name] = {row['path']: row['sha256'] for row in load(root/'manifest.json')['files']}

    def parent(name, file):
        path = a.workspace/'baselines'/name/file
        assert sha(path) == tables[name][file]; r['inputs'][str(path)] = sha(path); return path

    profile = load(parent('fixed_source_profiles_v1', 'evidence/trial1/F2_tailpipe/profile.json'))
    law = load(parent('idle_positive_power_v1', 'evidence/observe1/report.json'))['observations'][0]['models']['expanded']
    source = load(parent('idle_joint_cumulant_v1', 'evidence/observe1/report.json'))
    sourceQ = np.array([[row['raw']['normalized'][b][c] for b, c in PAIRS] for part in ['training', 'check']
                        for row in source['observations'] if row['label'] == part])
    with np.load(parent('idle_wave_budget_v1', 'evidence/observe2/architecture.npz')) as archive:
        v, sos, h, oldkappa = archive['variance'], archive['sos'], archive['h'], archive['kappa'][2:]
        main, warmup, frames = archive['main'], int(archive['warmup']), int(archive['frames'])
    observers = []; supports = []; constant_error = []; tail_checks = []
    for band, cascade in enumerate(sos):
        impulse, description = support(cascade); observers.append(impulse); supports.append(description)
        full = np.zeros(65536); full[0] = 1; full = signal.sosfilt(cascade, full)
        actual_tail = float(abs(full[len(impulse):]).sum())
        assert actual_tail <= description['tail_L1_bound']
        tail_checks.append(actual_tail)
    taps = [np.asarray(kernel['taps'])*kernel['gain'] for kernel in profile['kernels']]
    gmax = np.r_[np.ones(2), np.sqrt(law['bounds']['power_upper'])]
    epsilon = np.array([[gmax[i]*sum(abs(taps[i]))*s['tail_L1_bound'] for s in supports] for i in range(6)])
    generator = np.random.Generator(np.random.PCG64(20261114))
    origins = generator.integers(0, 134400, size=(2,64,16))+4800+np.arange(2)[:,None,None]*144000
    flat = origins.reshape(-1); covariance = np.zeros((len(flat),4,4)); operator = np.zeros((len(flat),4,4,4))
    bound2 = np.zeros((6,4,4)); bound4 = np.zeros((6,4,4))
    for i, tap in enumerate(taps):
        constant = kernels(np.array([warmup+flat[0]]), np.ones(len(v)), tap, observers)[0]
        reference = np.zeros_like(h[:,i]); reference[:,:constant.shape[1]] = constant
        constant_error.append(float(abs(reference-h[:,i]).max()))
        assert constant_error[-1] < 1e-12
        amplitude = np.sqrt(v[:,i])
        for first in range(0, len(flat), 64):
            last = min(len(flat), first+64)
            response = kernels(warmup+flat[first:last], amplitude, tap, observers)
            C, A = matrices(response); covariance[first:last] += C
            if i >= 2: operator[first:last,:,:,i-2] = A
            e2, e4 = operator_error(response, epsilon[i])
            bound2[i] = np.maximum(bound2[i], e2); bound4[i] = np.maximum(bound4[i], e4)
        print(dict(stage='actual_POST_input', completed=i+1, total=6), flush=True)
    sampled_main = main[flat].reshape(2,1024,4)
    covariance = covariance.reshape(2,1024,4,4); operator = operator.reshape(2,1024,4,4,4)
    states = [summarize(sampled_main[b], covariance[b], operator[b]) for b in range(2)]
    allocation = allocate(states[0], sourceQ[0])
    r.update(supports=supports, observed_tail_L1=tail_checks, kernel_uniform_L2_error=epsilon.tolist(),
             conditional_C_uniform_error=bound2.sum(axis=0).tolist(), innovation_A_uniform_error=bound4[2:].transpose(1,2,0).tolist(),
             stationary_full_response_max_error=constant_error, sourceQ=sourceQ.tolist(), old_kappa=oldkappa.tolist(),
             states=[serial(z) for z in states], allocation=allocation, old_predictions=[prediction(z,oldkappa).tolist() for z in states],
             origins_seed=20261114, origins_duplicates=[1024-len(np.unique(x)) for x in origins], plan=plan)
    kappa = np.asarray(allocation['kappa']) if 'kappa' in allocation else None
    if kappa is not None:
        r['new_predictions'] = [prediction(z,kappa).tolist() for z in states]
        r['kappa_ratio_to_old'] = (kappa/oldkappa).tolist()
    leaves = []; statuses = []
    for group in range(64):
        selection = np.r_[np.arange(group*16), np.arange((group+1)*16,1024)]
        selected = [summarize(sampled_main[b,selection], covariance[b,selection], operator[b,selection]) for b in range(2)]
        fitted = allocate(selected[0],sourceQ[0]); statuses.append(fitted['status'])
        if 'kappa' in fitted:
            coefficient = np.asarray(fitted['kappa'])
            leaves.append(np.r_[coefficient, prediction(selected[0],coefficient), prediction(selected[1],coefficient)])
        else: leaves.append(np.full(24,np.nan))
    leave = np.asarray(leaves); r['jackknife_statuses'] = statuses
    if kappa is not None and np.isfinite(leave).all():
        point = np.r_[kappa,*r['new_predictions']]
        se = np.sqrt(63/64*((leave-leave.mean(axis=0))**2).sum(axis=0)); radius = stats.t.ppf(.975,63)*se
        r['jackknife'] = dict(point=point.tolist(), se=se.tolist(), low=(point-radius).tolist(), high=(point+radius).tolist(),
                              estimated_plugin_bias=(63*(leave.mean(axis=0)-point)).tolist())
    path = a.out/'conditional_fields.npz'
    np.savez_compressed(path, origins=origins, main=sampled_main, covariance=covariance, operator=operator,
                        global_gmax=gmax, epsilon=epsilon, bound2=bound2, bound4=bound4, sourceQ=sourceQ,
                        leave=leave, oldkappa=oldkappa)
    r.update(result='all_POST_zero_budgets_and_TRAIN_allocation_complete_NO_promotion', data_file=path.name, data_sha256=sha(path),
             no_random_innovations_sampled=True, time_sampling_NOT_full_native_zero_budget=True,
             all_lag_curves_qualified=False, audio_or_runtime_changed=False)
    print(dict(stage='allocation', result=allocation, ratios=r.get('kappa_ratio_to_old'), predictions=r.get('new_predictions')),flush=True)
except Exception as exc:
    r.update(result='failed', error=repr(exc)); raise
finally:
    save(a.out/'report.json',r)
