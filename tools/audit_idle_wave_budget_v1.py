"""Independent linear convolutions and general set-partition wave cumulants."""
import argparse
import itertools
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


def partitions(items):
    if not items:
        yield []; return
    for rest in partitions(items[1:]):
        yield [[items[0]]]+[v[:] for v in rest]
        for k in range(len(rest)):
            yield [([items[0]]+v if j == k else v[:]) for j, v in enumerate(rest)]


PARTITIONS = list(partitions([0, 1, 2, 3]))
ORDERS = [(1, 0), (0, 1), (2, 0), (0, 2), (1, 1), (2, 1), (1, 2), (2, 2)]
assert len(PARTITIONS) == 15


def cumulant(raw):
    table = {(0, 0): 1., **dict(zip(ORDERS, raw))}
    values = []
    for partition in PARTITIONS:
        product = (-1)**(len(partition)-1)*math.factorial(len(partition)-1)
        for block in partition:
            first = sum(v < 2 for v in block)
            product *= table[first, len(block)-first]
        values.append(product)
    return math.fsum(values)


def known_oracle(path):
    with np.load(path) as archive: data = {key: archive[key] for key in archive.files}
    h, v, m, levels, probabilities = [data[key] for key in ['h', 'v', 'm', 'levels', 'weights']]
    maximum = 0.
    for b, c in [(0, 0), (0, 1), (1, 1)]:
        for lag in range(-2, 3):
            moments = []
            for n in range(max(0, -lag), min(len(m), len(m)-lag)):
                addresses = list(dict.fromkeys([(i, s+2-u) for s in [n, n+lag] for i in range(2) for u in range(2)]))
                grid = np.array(list(itertools.product(range(len(levels)), repeat=len(addresses))))
                weight = np.prod(probabilities[grid], axis=1)
                excitation = levels[grid]
                x = np.full(len(grid), m[n, b]); y = np.full(len(grid), m[n+lag, c])
                for index, (i, time) in enumerate(addresses):
                    for out, band, at in [(x, b, n), (y, c, n+lag)]:
                        u = at+2-time
                        if 0 <= u < 2:
                            out += h[band, i, u]*math.sqrt(v[time, i])*excitation[:, index]
                moments.append([math.fsum(weight*x**p*y**q) for p, q in ORDERS])
            raw = np.mean(moments, axis=0)
            error = float(abs(raw-data[f'raw_{b}_{c}_{lag}']).max())
            assert error < 1e-12
            maximum = max(maximum, error)
    return maximum


def fields(h, v, kappa, warmup, frames, b, c, lag, stationary):
    left, right = max(0, -lag), min(h.shape[2], h.shape[2]-lag)
    C = np.zeros(frames); J = np.zeros(frames)
    for i in range(h.shape[1]):
        kernel = np.zeros(h.shape[2])
        kernel[left:right] = h[b, i, left:right]*h[c, i, left+lag:right+lag]
        if stationary:
            C += math.fsum(kernel)
            J += kappa[i]*math.fsum(kernel*kernel)
        else:
            C += signal.oaconvolve(v[:, i], kernel)[warmup:warmup+frames]
            if kappa[i] != 0:
                J += kappa[i]*signal.oaconvolve(v[:, i]**2, kernel**2)[warmup:warmup+frames]
    return C, J


def raw_moments(m, d, v, w, C, J):
    # Extended-precision direct raw moments, then general cumulant partitions.
    m, d, v, w, C, J = [x.astype(np.longdouble) for x in [m, d, v, w, C, J]]
    return np.asarray([m.mean(), d.mean(), (m*m+v).mean(), (d*d+w).mean(), (m*d+C).mean(),
                       (m*m*d+d*v+2*m*C).mean(), (m*d*d+m*w+2*d*C).mean(),
                       (m*m*d*d+m*m*w+d*d*v+4*m*d*C+v*w+2*C*C+J).mean()], dtype=float)


a.out.mkdir(parents=True, exist_ok=False); shutil.copy2(__file__, a.out/'executed_auditor.py')
r = dict(result='running', known_maximum_error=0., maximum_normalized_raw_error=0.,
         maximum_cumulant_error=0., maximum_covariance_error=0., maximum_term_error=0., pairs=0)
try:
    observed = load(a.input/'report.json')
    assert observed['result'] == 'all_actual_preinnovation_wave_budgets_complete_NO_sound_promotion'
    for name, digest in observed['sources'].items(): assert sha(a.input/'exact_sources'/name) == digest
    tables = {}
    for name, digest in observed['parent_manifests'].items():
        root = a.workspace/'baselines'/name; assert sha(root/'manifest.json') == digest
        tables[name] = {row['path']: row['sha256'] for row in load(root/'manifest.json')['files']}
    for path, digest in observed['inputs'].items():
        relative = Path(path).relative_to(a.workspace/'baselines')
        assert sha(path) == digest == tables[relative.parts[0]][Path(*relative.parts[1:]).as_posix()]
    for row in observed['known']['exact_ensembles']:
        r['known_maximum_error'] = max(r['known_maximum_error'], known_oracle(a.input/'known'/row['file']))
    print(dict(stage='exact_known_ensembles', error=r['known_maximum_error']), flush=True)
    with np.load(a.input/'architecture.npz') as archive: architecture = {key: archive[key] for key in archive.files}
    h, kappa, main, v = [architecture[key] for key in ['h', 'kappa', 'main', 'variance']]
    warmup, frames = int(architecture['warmup']), int(architecture['frames'])
    assert warmup == 65535 and frames == 288000 and h.shape == (4, 6, 65536)
    profile = load(a.workspace/'baselines/fixed_source_profiles_v1/evidence/trial1/F2_tailpipe/profile.json')
    source = load(a.workspace/'baselines/idle_positive_power_v1/evidence/observe1/report.json')
    model = source['observations'][0]['models']['expanded']; coef = np.asarray(model['coefficients'])
    time = (np.arange(warmup+frames)-warmup)/48000
    modal = profile['modal']; raw = np.zeros(len(time))
    for frequency, amplitude, phase in zip(modal['frequencies_hz'], modal['amplitude_LR'], modal['initial_phase_LR']):
        raw += amplitude[0]*np.cos(2*np.pi*frequency*time+phase[0])
    nfft = 1<<int(math.ceil(math.log2(len(raw)+131072)))
    z = np.exp(-2j*np.pi*np.arange(nfft//2+1)/nfft)
    spectrum = np.fft.rfft(raw, nfft); independent_main = []; response_error = 0.
    for b, cascade in enumerate(architecture['sos']):
        transfer = np.ones(len(z), complex)
        for s in cascade:
            transfer *= (s[0]+s[1]*z+s[2]*z*z)/(s[3]+s[4]*z+s[5]*z*z)
        independent_main.append(np.fft.irfft(spectrum*transfer, nfft)[warmup:warmup+frames])
        for i, kernel in enumerate(profile['kernels']):
            taps = np.fft.rfft(np.asarray(kernel['taps'])*kernel['gain'], nfft)
            expected = np.fft.irfft(taps*transfer, nfft)[:65536]
            response_error = max(response_error, float(abs(expected-h[b, i]).max()))
    main_error = float(abs(np.asarray(independent_main).T-main).max())
    assert main_error < 1e-11 and response_error < 1e-14
    r.update(maximum_main_filter_error_FS=main_error, maximum_response_error_FS=response_error)
    z0, z1, z2 = [np.exp(1j*(2*np.pi*modal['frequencies_hz'][k]*time+modal['initial_phase_LR'][k][0])) for k in [1, 2, 4]]
    phases = [z0, z1, z2, z1*z0.conj(), z2*z0.conj(), z2*z1.conj()]
    q = np.column_stack([np.exp(coef[0, b]+sum(coef[i+1, b]*x.real+coef[i+7, b]*x.imag for i, x in enumerate(phases))) for b in range(4)])
    qerror = float(abs(q-v[:, 2:]).max()); assert qerror < 1e-10
    assert np.array_equal(v[:, :2], np.ones((len(v), 2)))
    r['maximum_input_variance_error'] = qerror
    assert np.all(q.min(axis=0) >= model['bounds']['power_lower']) and np.all(q.max(axis=0) <= model['bounds']['power_upper'])
    cases = {}
    for row in observed['cases']:
        assert sha(a.input/row['file']) == row['sha256']
        with np.load(a.input/row['file']) as archive: cases[row['amount'], row['block'], row['distribution']] = {key: archive[key] for key in archive.files}
    assert len(cases) == 8 and observed['moment_order'] == [list(v) for v in ORDERS]
    for amount in [0, 1]:
        inputs = np.ones_like(v) if amount == 0 else v
        variance = np.column_stack([fields(h, inputs, kappa, warmup, frames, b, b, 0, amount == 0)[0] for b in range(4)])
        for block in range(2):
            first, last = block*144000+4800, (block+1)*144000-4800
            mu = main[first:last].mean(axis=0)
            mainvar = ((main[first:last]-mu)**2).mean(axis=0)
            randomvar = variance[first:last].mean(axis=0)
            for distribution in ['Gaussian', 'sparse']:
                saved = cases[amount, block, distribution]
                for key, expected in [('mean', mu), ('main_variance', mainvar), ('random_variance', randomvar),
                                      ('variance', mainvar+randomvar), ('mean_power', (main[first:last]**2+variance[first:last]).mean(axis=0))]:
                    assert np.allclose(expected, saved[key], atol=1e-20, rtol=1e-11)
                assert np.array_equal(saved['lags'], np.arange(-1920, 1921, 48))
        for pair, (b, c) in enumerate([(b, c) for b in range(4) for c in range(b, 4)]):
            for li, lag in enumerate(range(-1920, 1921, 48)):
                C, J = fields(h, inputs, kappa, warmup, frames, b, c, lag, amount == 0)
                for block in range(2):
                    first = block*144000+4800+max(0, -lag); last = (block+1)*144000-4800-max(0, lag)
                    left, right = slice(first, last), slice(first+lag, last+lag)
                    m, d, V, W = main[left, b], main[right, c], variance[left, b], variance[right, c]
                    cross = C[left]
                    mc, dc = m-m.mean(), d-d.mean()
                    cov = lambda x, y: float(np.mean((x.astype(np.longdouble)-np.mean(x.astype(np.longdouble)))*(y.astype(np.longdouble)-np.mean(y.astype(np.longdouble)))))
                    denominator = cases[amount, block, 'Gaussian']['variance'][b]*cases[amount, block, 'Gaussian']['variance'][c]
                    for distribution in ['Gaussian', 'sparse']:
                        j = J[left] if distribution == 'sparse' else np.zeros(last-first)
                        saved = cases[amount, block, distribution]
                        raw = raw_moments(m, d, V, W, cross, j)
                        scales = np.array([saved['variance'][b]**(p/2)*saved['variance'][c]**(q/2) for p, q in ORDERS])
                        error = float((abs(raw-saved['raw'][pair, li])/scales).max()); assert error < 1e-8
                        r['maximum_normalized_raw_error'] = max(r['maximum_normalized_raw_error'], error)
                        K = cumulant(raw)/denominator
                        ce = abs(K-saved['normalized'][pair, li]); assert ce < 1e-8
                        r['maximum_cumulant_error'] = max(r['maximum_cumulant_error'], ce)
                        covariance = (raw[4]-raw[0]*raw[1])/math.sqrt(denominator)
                        ve = abs(covariance-saved['covariance'][pair, li]); assert ve < 1e-8
                        r['maximum_covariance_error'] = max(r['maximum_covariance_error'], ve)
                        terms = [float(np.mean(mc*mc*dc*dc)-np.mean(mc*mc)*np.mean(dc*dc)-2*np.mean(mc*dc)**2),
                                 cov(V, W), 2*cov(cross, cross), cov(mc*mc, W), cov(dc*dc, V), 4*cov(mc*dc, cross), math.fsum(j)/len(j)]
                        term_error = float(abs(np.asarray(terms)/denominator-saved['terms'][pair, li]).max()); assert term_error < 1e-8
                        r['maximum_term_error'] = max(r['maximum_term_error'], term_error)
            r['pairs'] += 1
            print(dict(amount=amount, pair=[b, c], all81lags_verified=True), flush=True)
    for row in observed['cases']:
        saved = cases[row['amount'], row['block'], row['distribution']]
        mask = (abs(saved['lags']) >= 384) & (abs(saved['lags']) <= 960)
        assert np.allclose(saved['normalized'][:, mask].mean(axis=1), row['late8_to20ms_mean'], atol=1e-12)
        assert np.array_equal(saved['normalized'][:, 40], row['zero_lag'])
        assert np.array_equal(saved['mean_power'], row['mean_power'])
    with np.load(a.workspace/'baselines/idle_joint_lag_v1/evidence/observe1/expectation.npz') as archive:
        old_error = float(abs(cases[0, 0, 'sparse']['normalized']-archive['normalized']).max())
        assert old_error < 1e-8 and old_error == observed['original_stationary_full_curve_error']
    failed = load(a.input.parent/'observe1/report.json')
    assert failed['result'] == 'failed' and 'Warmup must cover' in failed['error']
    for name, digest in failed['sources'].items(): assert sha(a.input.parent/'observe1/exact_sources'/name) == digest
    changed = {name for name in observed['sources'] if observed['sources'][name] != failed['sources'][name]}
    assert changed == {'tools/observe_idle_wave_budget_v1.py', 'research/idle_wave_budget_v1_plan.json'}
    for name, count in [('C_files_sha256.json', 612), ('voice_files_sha256.json', 67)]:
        values = load(a.workspace/'baselines/idle_microtexture_c_v1/inputs'/name); assert len(values) == count
        for path, digest in values.items(): assert sha(repo/path) == digest, path
    r.update(result='all8_wave_cases_15partition_and_independent_convolution_verified',
             input_report_sha256=sha(a.input/'report.json'), curves=80, lag_points=6480,
             original_stationary_full_curve_error=old_error, failed_warmup_attempt_preserved=True,
             ensemble_time_origin_NOT_finite_record_estimator=True,
             unchanged_C_H=612, unchanged_old_voices=67, runtime_changed=False, generated_random_audio=False)
except Exception as exc:
    r.update(result='failed', error=repr(exc)); raise
finally:
    save(a.out/'report.json', r)
print(r, flush=True)
