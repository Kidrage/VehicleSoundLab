"""Independent full-seed placement renders, explicit known paths and cross-seed sums."""
import argparse
import itertools
import shutil
import sys
from pathlib import Path
p = argparse.ArgumentParser(description=__doc__)
for key in ['workspace', 'input', 'out']: p.add_argument('--'+key, type=Path, required=True)
a = p.parse_args(); repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(a.workspace/'tools/python_deps'))
import numpy as np
from scipy import signal, special
from research_archive_v1 import load, save, sha


def summary(x, q):
    count, size, bands = x.shape; total = x.sum(axis=0); means = x.mean(axis=1)
    product = (total.T@total-np.einsum('stb,stc->bc', x, x))/(size*count*(count-1))
    mean_product = (means.sum(axis=0)[:, None]*means.sum(axis=0)[None, :]-means.T@means)/(count*(count-1))
    covariance = product-mean_product; variance = np.diag(covariance)
    assert (variance > 0).all()
    mean = total.mean(axis=0)/count
    mse = np.diag(product)-2*(total*q).mean(axis=0)/count+(q*q).mean(axis=0)
    cov_q = (total*q).mean(axis=0)/count-mean*q.mean(axis=0)
    corr = cov_q/np.sqrt(variance*q.var(axis=0))
    cross = [covariance[b, c]/np.sqrt(variance[b]*variance[c]) for b in range(bands) for c in range(b+1, bands)]
    return np.r_[mean, mse, corr, cross]


def deterministic(x, q):
    covariance = np.cov(x, rowvar=False, bias=True); variance = np.diag(covariance)
    cov_q = (x*q).mean(axis=0)-x.mean(axis=0)*q.mean(axis=0)
    return np.r_[x.mean(axis=0), np.mean((x-q)**2, axis=0), cov_q/np.sqrt(variance*q.var(axis=0)),
                 [covariance[b, c]/np.sqrt(variance[b]*variance[c]) for b in range(4) for c in range(b+1, 4)]]


def known(source):
    taps, observers, g = map(np.asarray, (source['taps'], source['observers'], source['gains']))
    maximum = 0.
    for placement in ('pre', 'post'):
        expected = np.zeros((len(g), 2)); enumerated = np.zeros_like(expected)
        for at in range(len(g)):
            variables = [(s, i) for s in range(max(0, at-2), at+1) for i in range(2)]
            paths = np.zeros((2, len(variables)))
            for b in range(2):
                for u in range(2):
                    for k in range(2):
                        s = at-u-k
                        if s < 0: continue
                        for i in range(2):
                            control_time = s if placement == 'pre' else at-u
                            paths[b, variables.index((s, i))] += observers[b, u]*taps[i, k]*g[control_time, i]
            expected[at] = np.sum(paths*paths, axis=1)
            for values in itertools.product((-1., 1.), repeat=len(variables)):
                enumerated[at] += (paths@values)**2/2**len(variables)
        error = max(float(abs(expected-enumerated).max()), float(abs(expected-source['powers'][placement]).max()))
        assert error < 1e-12; maximum = max(maximum, error)
    return maximum


a.out.mkdir(parents=True, exist_ok=False); shutil.copy2(__file__, a.out/'executed_auditor.py')
r = dict(result='running', maximum_power_error=0., maximum_metric_error=0., seeds=0)
try:
    observed = load(a.input/'report.json')
    assert observed['result'] == 'all64_paired_placement_power_observations_complete_NO_timbre_claim'
    for name, digest in observed['sources'].items(): assert sha(a.input/'exact_sources'/name) == digest
    for path, digest in observed['inputs'].items(): assert sha(path) == digest
    for name, digest in observed['parent_manifests'].items(): assert sha(a.workspace/'baselines'/name/'manifest.json') == digest
    r['known_error'] = known(observed['known'])
    assert sha(a.input/observed['data_file']) == observed['data_sha256']
    with np.load(a.input/observed['data_file']) as archive: data = {k: archive[k] for k in archive.files}
    assert np.array_equal(data['seeds'], np.arange(64)) and data['samples'].shape == (64, 2, 6000, 4)
    profile = load(a.workspace/'baselines/fixed_source_profiles_v1/evidence/trial1/F2_tailpipe/profile.json')
    with np.load(a.workspace/'baselines/idle_wave_budget_v1/evidence/observe2/architecture.npz') as archive:
        h, v, sos = archive['h'], archive['variance'], archive['sos']
        warmup, frames = int(archive['warmup']), int(archive['frames'])
    reference = np.sum(h*h, axis=(1, 2)); assert np.array_equal(reference, data['reference'])
    amplitude = np.sqrt(v)
    expected = np.column_stack([sum(signal.oaconvolve(v[:, i], h[b, i]**2)[warmup:warmup+frames]
                                for i in range(6)) for b in range(4)])
    expected = expected.reshape(-1, 48, 4).mean(axis=1)/reference
    r['exact_pre_power_error'] = float(abs(expected-data['expected_pre']).max())
    assert r['exact_pre_power_error'] < 1e-11
    guide = v[warmup:, 2:].reshape(-1, 48, 4).mean(axis=1)
    assert np.array_equal(guide, data['target'])
    for seed in range(64):
        noise = np.random.Generator(np.random.PCG64(seed)).standard_normal(v.shape)
        for placement in range(2):
            audio = np.zeros(len(noise))
            for i, kernel in enumerate(profile['kernels']):
                x = noise[:, i]*amplitude[:, i] if placement == 0 else noise[:, i]
                branch = signal.oaconvolve(x, np.asarray(kernel['taps']))[:len(x)]*kernel['gain']
                audio += branch if placement == 0 else amplitude[:, i]*branch
            filtered = []
            for cascade in sos:
                value = audio.copy()
                for section in cascade: value = signal.lfilter(section[:3], section[3:], value)
                filtered.append(value[warmup:warmup+frames])
            power = np.asarray(filtered).T**2
            power = power.reshape(-1, 48, 4).mean(axis=1)/reference
            error = float(abs(power-data['samples'][seed, placement]).max())
            assert error < 1e-10, (seed, placement, error)
            r['maximum_power_error'] = max(r['maximum_power_error'], error)
        r['seeds'] += 1
        if seed % 8 == 7: print(dict(stage='independent_seed', completed=seed+1), flush=True)
    for block in range(2):
        selection = slice(block*3000+100, (block+1)*3000-100)
        q = guide[selection]; points = []; leaves = []
        for placement in range(2):
            x = data['samples'][:, placement, selection]
            point = summary(x, q)
            leave = np.asarray([summary(np.delete(x, i, axis=0), q) for i in range(64)])
            se = np.sqrt(63/64*np.sum((leave-leave.mean(axis=0))**2, axis=0))
            radius = special.stdtrit(63, .975)*se
            row = next(z for z in observed['observations'] if z['block'] == block and z['placement'] == ['pre', 'post'][placement])
            for key, value in [('point', point), ('se', se), ('low', point-radius), ('high', point+radius)]:
                error = float(abs(value-row[key]).max()); assert error < 1e-10
                r['maximum_metric_error'] = max(r['maximum_metric_error'], error)
            if placement == 0:
                benchmark = deterministic(expected[selection], q)
                assert abs(benchmark-row['exact']).max() < 1e-10
                inside = ((benchmark >= point-radius) & (benchmark <= point+radius)).tolist()
                assert inside == row['exact_inside_pointwise95']
            points.append(point); leaves.append(leave)
        point = points[1]-points[0]; leave = leaves[1]-leaves[0]
        se = np.sqrt(63/64*np.sum((leave-leave.mean(axis=0))**2, axis=0))
        row = observed['paired_post_minus_pre'][block]
        radius = special.stdtrit(63, .975)*se
        family = special.stdtrit(63, 1-.05/16)*se[4:8]
        for key, value in [('point', point), ('se', se), ('low', point-radius), ('high', point+radius),
                           ('mse_family_low', point[4:8]-family), ('mse_family_high', point[4:8]+family)]:
            error = float(abs(value-row[key]).max()); assert error < 1e-10
            r['maximum_metric_error'] = max(r['maximum_metric_error'], error)
    r.update(result='all64paired_renders_known_and_crossseed_statistics_verified',
             input_report_sha256=sha(a.input/'report.json'), all_seed_arrays_rerendered=True,
             finite_ensemble_NOT_exact_post=True, runtime_changed=False)
except Exception as exc:
    r.update(result='failed', error=repr(exc)); raise
finally:
    save(a.out/'report.json', r)
