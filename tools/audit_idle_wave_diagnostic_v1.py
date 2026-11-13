"""Independent exponential/covariance diagnostics and analytic non-engine counterexample."""
import argparse
import math
import shutil
import sys
from pathlib import Path
p = argparse.ArgumentParser(description=__doc__)
for key in ['workspace', 'input', 'diagnostic', 'out']:
    p.add_argument('--'+key, type=Path, required=True)
a = p.parse_args(); repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(a.workspace/'tools/python_deps'))
import numpy as np
from scipy.fft import next_fast_len
from scipy.special import i0
from research_archive_v1 import load, save, sha


def corr(q):
    result = []
    for b in range(4):
        for c in range(b+1, 4):
            x, y = q[:, b], q[:, c]
            x = x-math.fsum(x)/len(x); y = y-math.fsum(y)/len(y)
            result.append(math.fsum(x*y)/math.sqrt(math.fsum(x*x)*math.fsum(y*y)))
    return np.asarray(result)


def law(coef, z):
    phi = np.angle(z)
    phi = np.column_stack((phi, phi[:, 1]-phi[:, 0], phi[:, 2]-phi[:, 0], phi[:, 2]-phi[:, 1]))
    return np.column_stack([np.exp(coef[0, b]+sum(coef[k+1, b]*np.cos(phi[:, k])+coef[k+7, b]*np.sin(phi[:, k]) for k in range(6))) for b in range(4)])


a.out.mkdir(parents=True, exist_ok=False); shutil.copy2(__file__, a.out/'executed_auditor.py')
r = dict(result='running', maximum_q_error=0., maximum_correlation_error=0., maximum_variance_error=0.)
try:
    diagnostic = load(a.diagnostic/'report.json')
    assert diagnostic['result'] == 'posthoc_input_and_response_correlations_observed_NO_correction'
    assert diagnostic['input_report_sha256'] == sha(a.input/'report.json')
    for name, digest in diagnostic['sources'].items(): assert sha(a.diagnostic/'exact_sources'/name) == digest
    for path, digest in diagnostic['inputs'].items(): assert sha(path) == digest
    for row in diagnostic['known']:
        expected = 1. if row['offset'] == 0 else (1-i0(.3)**2)/(i0(.6)-i0(.3)**2)
        assert abs(row['result']['q_zero_correlations'][0]-expected) < 1e-12
        assert abs(np.asarray(row['marginal_means'])-i0(.3)).max() < 1e-12
        assert abs(complex(*row['result']['closure_mean'])-np.exp(1j*row['offset'])) < 1e-12
    r['analytic_bessel_counterexample_verified'] = True
    with np.load(a.input/'architecture.npz') as archive:
        h, v, main = archive['h'], archive['variance'], archive['main']
        warmup, frames = int(archive['warmup']), int(archive['frames'])
    size = next_fast_len(len(v)+len(h[0, 0])-1)
    transform = np.fft.rfft(v, n=size, axis=0)
    variance = np.column_stack([np.fft.irfft(sum(np.fft.rfft(h[b, i]**2, n=size)*transform[:, i] for i in range(6)), n=size)[warmup:warmup+frames] for b in range(4)])
    profile = load(a.workspace/'baselines/fixed_source_profiles_v1/evidence/trial1/F2_tailpipe/profile.json')
    model = load(a.workspace/'baselines/idle_positive_power_v1/evidence/observe1/report.json')['observations'][0]['models']['expanded']
    coef = np.asarray(model['coefficients'])
    for row in diagnostic['observations']:
        label = row['label']
        with np.load(a.diagnostic/(label+'.npz')) as archive: saved = {key: archive[key] for key in archive.files}
        if label.startswith('source_'):
            part = label.removeprefix('source_')
            with np.load(a.workspace/f'baselines/idle_conditioned_detail_v1/evidence/observe1/{part}.npz') as archive:
                z = archive['phasors'][12000:-12000]
        else:
            block = int(label[-1]); section = slice(block*144000+12000, (block+1)*144000-12000)
            time = np.arange(frames)[section]/48000
            z = np.column_stack([np.exp(1j*(2*np.pi*profile['modal']['frequencies_hz'][k]*time+profile['modal']['initial_phase_LR'][k][0])) for k in [1, 2, 4]])
            error = float(abs(variance[section]-saved['variance']).max())
            assert error < 1e-16; r['maximum_variance_error'] = max(r['maximum_variance_error'], error)
            assert np.array_equal(main[section], saved['main'])
        q = law(coef, z)
        error = float(abs(q-saved['q']).max()); assert error < 1e-11
        r['maximum_q_error'] = max(r['maximum_q_error'], error)
        closure = np.exp(1j*(np.angle(z[:, 2])-np.angle(z[:, 1])-np.angle(z[:, 0])))
        assert abs(closure-saved['closure']).max() < 1e-11
        result = row['result']; mean = complex(closure.mean())
        assert abs(mean-complex(*result['closure_mean'])) < 1e-12
        assert abs(abs(mean)-result['closure_concentration']) < 1e-12
        assert abs(np.angle(mean)-result['closure_mean_angle']) < 1e-12
        error = float(abs(corr(q)-result['q_zero_correlations']).max()); assert error < 1e-11
        r['maximum_correlation_error'] = max(r['maximum_correlation_error'], error)
        if label.startswith('runtime'):
            for key, values in [('output_variance', saved['variance']), ('output_total_power', saved['variance']+saved['main']**2)]:
                error = float(abs(corr(values)-row[key]['q_zero_correlations']).max()); assert error < 1e-11
                r['maximum_correlation_error'] = max(r['maximum_correlation_error'], error)
        assert np.all(corr(q) > 0)
    for row in diagnostic['observations'][2:]:
        values = row['output_variance']['q_zero_correlations']
        assert values[1] < 0 and values[2] < 0
    r.update(result='all_source_runtime_input_response_diagnostics_independently_verified',
             diagnostic_report_sha256=sha(a.diagnostic/'report.json'), input_report_sha256=sha(a.input/'report.json'),
             all6_input_pairs_positive_all4portions=True, same2_output_pairs_negative_bothblocks=True,
             no_phase_or_delay_correction=True, runtime_changed=False)
except Exception as exc:
    r.update(result='failed', error=repr(exc)); raise
finally:
    save(a.out/'report.json', r)
print(r, flush=True)
