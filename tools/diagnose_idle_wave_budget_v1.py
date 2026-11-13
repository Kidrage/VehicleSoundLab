"""Posthoc locate covariance sign changes without fitting phase or delay corrections."""
import argparse
import math
import shutil
import sys
from pathlib import Path
p = argparse.ArgumentParser(description=__doc__)
for key in ['workspace', 'input', 'out']:
    p.add_argument('--'+key, type=Path, required=True)
a = p.parse_args(); repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(a.workspace/'tools/python_deps'))
import numpy as np
from scipy import signal
from research_archive_v1 import load, save, sha


def describe(z, q):
    closure = z[:, 2]*z[:, 1].conj()*z[:, 0].conj()
    mean = complex(closure.mean())
    correlations = []
    for b in range(4):
        for c in range(b+1, 4):
            x, y = q[:, b]-q[:, b].mean(), q[:, c]-q[:, c].mean()
            norm = np.linalg.norm(x)*np.linalg.norm(y)
            correlations.append(float(x@y/norm) if norm else None)
    return dict(closure_mean=[mean.real, mean.imag], closure_concentration=abs(mean),
                closure_mean_angle=float(np.angle(mean)), q_zero_correlations=correlations)


def power(coef, z):
    phases = [z[:, 0], z[:, 1], z[:, 2], z[:, 1]*z[:, 0].conj(), z[:, 2]*z[:, 0].conj(), z[:, 2]*z[:, 1].conj()]
    return np.exp(coef[0]+sum(x.real[:, None]*coef[k+1]+x.imag[:, None]*coef[k+7] for k, x in enumerate(phases)))


a.out.mkdir(parents=True, exist_ok=False)
r = dict(result='running', sources={}, inputs={}, observations=[])
try:
    for name in ['tools/diagnose_idle_wave_budget_v1.py', 'research/idle_wave_budget_v1_diagnostic_plan.json', 'tools/research_archive_v1.py']:
        path = repo/name; dest = a.out/'exact_sources'/name
        dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path, dest); r['sources'][name] = sha(path)
    time = np.arange(48000)/48000
    known = []
    for offset in [0., np.pi]:
        z = np.exp(1j*(2*np.pi*time[:, None]*np.array([75., 112.5, 187.5])+np.array([0., 0., offset])))
        q1 = np.exp(.3*z[:, 0].real); q2 = np.exp(.3*(z[:, 2]*z[:, 1].conj()).real)
        q = np.column_stack((q1, q2, q1, q2)); result = describe(z, q)
        assert abs(complex(*result['closure_mean'])-np.exp(1j*offset)) < 1e-12
        scalar1 = np.array([math.exp(.3*math.cos(2*math.pi*75*t)) for t in time])
        scalar2 = np.array([math.exp(.3*math.cos(2*math.pi*75*t+offset)) for t in time])
        assert abs(scalar1-q1).max() < 1e-12 and abs(scalar2-q2).max() < 1e-12
        assert (result['q_zero_correlations'][0] > .999 if offset == 0 else result['q_zero_correlations'][0] < -.97)
        known.append(dict(offset=offset, result=result, marginal_means=q.mean(axis=0).tolist()))
    r['known'] = known
    print(dict(stage='known_closure_counterexample', correlations=[v['result']['q_zero_correlations'][0] for v in known]), flush=True)
    observed = load(a.input/'report.json')
    assert observed['result'] == 'all_actual_preinnovation_wave_budgets_complete_NO_sound_promotion'
    tables = {}
    for name in ['idle_conditioned_detail_v1', 'idle_positive_power_v1', 'fixed_source_profiles_v1']:
        root = a.workspace/'baselines'/name; r['inputs'][str(root/'manifest.json')] = sha(root/'manifest.json')
        tables[name] = {v['path']: v['sha256'] for v in load(root/'manifest.json')['files']}

    def parent(name, file):
        path = a.workspace/'baselines'/name/file; assert sha(path) == tables[name][file]
        r['inputs'][str(path)] = sha(path); return path

    profile = load(parent('fixed_source_profiles_v1', 'evidence/trial1/F2_tailpipe/profile.json'))
    coef = np.asarray(load(parent('idle_positive_power_v1', 'evidence/observe1/report.json'))['observations'][0]['models']['expanded']['coefficients'])
    for part in ['train', 'check']:
        with np.load(parent('idle_conditioned_detail_v1', f'evidence/observe1/{part}.npz')) as data:
            z = data['phasors'][12000:-12000]
        q = power(coef, z)
        r['observations'].append(dict(label='source_'+part, result=describe(z, q)))
        np.savez_compressed(a.out/('source_'+part+'.npz'), q=q, closure=z[:, 2]*z[:, 1].conj()*z[:, 0].conj())
    with np.load(a.input/'architecture.npz') as data:
        h, v, main = data['h'], data['variance'], data['main']; warmup, frames = int(data['warmup']), int(data['frames'])
    r['inputs'][str(a.input/'architecture.npz')] = sha(a.input/'architecture.npz')
    V = np.column_stack([sum(signal.oaconvolve(v[:, i], h[b, i]**2)[warmup:warmup+frames]
                                for i in range(6)) for b in range(4)])
    modal = profile['modal']; time = np.arange(frames)/48000
    z = np.column_stack([np.exp(1j*(2*np.pi*modal['frequencies_hz'][k]*time+modal['initial_phase_LR'][k][0])) for k in [1, 2, 4]])
    q = power(coef, z)
    assert abs(q-v[warmup:, 2:]).max() < 1e-10
    for block in range(2):
        section = slice(block*144000+12000, (block+1)*144000-12000)
        row = dict(label='runtime_block'+str(block), result=describe(z[section], q[section]),
                   output_variance=describe(z[section], V[section]),
                   output_total_power=describe(z[section], V[section]+main[section]**2))
        r['observations'].append(row)
        np.savez_compressed(a.out/(row['label']+'.npz'), q=q[section], variance=V[section], main=main[section],
                            closure=z[section, 2]*z[section, 1].conj()*z[section, 0].conj())
    for row in r['observations']: print(row, flush=True)
    r.update(result='posthoc_input_and_response_correlations_observed_NO_correction',
             input_report_sha256=sha(a.input/'report.json'), no_phase_or_delay_fit=True,
             runtime_changed=False, generated_random_audio=False)
except Exception as exc:
    r.update(result='failed', error=repr(exc)); raise
finally:
    save(a.out/'report.json', r)
