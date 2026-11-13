"""Independent integer products, native curves, and every joint arc decision."""
import argparse
import math
import shutil
import sys
from pathlib import Path
p = argparse.ArgumentParser(description=__doc__)
for key in ['workspace', 'input', 'extension', 'out']: p.add_argument('--'+key, type=Path, required=True)
a = p.parse_args(); repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(a.workspace/'tools/python_deps'))
import numpy as np
from scipy import signal
from research_archive_v1 import load, save, sha


def eta(z):
    u, v, s, t = z[:, 0].real, z[:, 0].imag, z[:, 1].real, z[:, 1].imag
    re, im = u**3-3*u*v*v, 3*u*u*v-v**3
    return (re*(s*s-t*t)+im*2*s*t)+1j*(im*(s*s-t*t)-re*2*s*t)


def inside(w, row):
    if not row['empirical_chart_valid']: return None
    p = row['circular_center_rad']; re = w.real*math.cos(p)+w.imag*math.sin(p)
    im = w.imag*math.cos(p)-w.real*math.sin(p); d = np.arctan2(im, re)
    lo, hi = row['empirical_arc_rad']; return (d >= lo) & (d <= hi)


a.out.mkdir(parents=True, exist_ok=False); shutil.copy2(__file__, a.out/'executed_extension_auditor.py')
r = dict(result='running', max_array_error=0., observations=0)
try:
    theta = np.arange(30000)[:, None]*[.00071, .00113, .00219]+[.2, -.4, .7]
    z = np.cos(theta)+1j*np.sin(theta); expected = np.exp(1j*(3*theta[:, 0]-2*theta[:, 1]))
    assert abs(eta(z)-expected).max() < 1e-12
    changed = z*np.exp(1j*np.array([.1, -.3, .7]))
    assert abs(eta(changed)-eta(z)*np.exp(1j*.9)).max() < 1e-12
    parent = load(a.input/'report.json'); extension = load(a.extension/'report.json')
    assert extension['result'] == 'second_coordinate_and_joint_support_observed_NO_generation'
    assert extension['input_report_sha256'] == sha(a.input/'report.json')
    lags = np.arange(501)*48; rows = {}; values = {}
    for row in extension['observations']:
        prior = next(x for x in parent['observations'] if x['label'] == row['label'])
        assert sha(a.input/prior['file']) == prior['sha256'] and sha(a.extension/row['file']) == row['sha256']
        with np.load(a.input/prior['file']) as archive: z = archive['phasors']
        with np.load(a.extension/row['file']) as archive: data = {k: archive[k] for k in archive.files}
        w = eta(z); n = len(w); angle = np.unwrap(np.angle(w)); t = (np.arange(n)-(n-1)/2)/48000
        Q, R = np.linalg.qr(np.column_stack((np.ones(n), t)), mode='reduced'); b = np.linalg.solve(R, Q.T@angle)
        residual = angle-b[0]-b[1]*t; var = math.fsum(residual**2)/n
        ac = signal.fftconvolve(residual[::-1], residual, mode='full')[n-1+lags]/(n-lags)
        cross = signal.fftconvolve(angle[::-1], angle, mode='full')[n-1+lags]; prefix = np.r_[0., np.cumsum(angle**2)]
        inc = (prefix[n]-prefix[lags]+prefix[n-lags]-2*cross)/(n-lags)
        mean = complex(math.fsum(w.real)/n, math.fsum(w.imag)/n); principal = np.angle(w*np.exp(-1j*np.angle(mean)))
        assert abs(abs(mean)-row['resultant']) < 1e-10
        assert abs(b[1]/math.tau-row['descriptive_linear_slope_hz']) < 1e-10
        assert abs(math.sqrt(var)-row['detrended_std_rad']) < 1e-10
        assert abs(np.quantile(principal, [0., .01, .05, .5, .95, .99, 1.])-row['principal_quantiles']).max() < 1e-9
        assert bool(abs(principal).max() < math.pi-.05) == row['empirical_chart_valid']
        assert abs(np.array([principal.min(), principal.max()])-row['empirical_arc_rad']).max() < 1e-9
        for key, expected in dict(closure=w, unwrapped=angle, residual=residual, residual_covariance=ac,
            residual_correlation=ac/var, phase_increment_second=inc).items():
            error = float(abs(expected-data[key]).max()); r['max_array_error'] = max(r['max_array_error'], error)
            assert error < 1e-8, (row['label'], key, error)
        assert np.array_equal(lags, data['lags_frames']); rows[row['label']] = row; values[row['label']] = w; r['observations'] += 1
    assert r['observations'] == 8
    eta_check = inside(values['source_check'], rows['source_train'])
    psi_train = next(x for x in parent['observations'] if x['label'] == 'source_train')
    prior = next(x for x in parent['observations'] if x['label'] == 'source_check')
    with np.load(a.input/prior['file']) as archive: psi_check = inside(archive['closure'], psi_train)
    assert float(eta_check.mean()) == extension['source_eta_check_coverage']
    assert float((eta_check & psi_check).mean()) == extension['source_joint_check_coverage']
    with np.load(a.input/parent['runtime_arc_file']) as archive: t = archive['time_seconds']; psi_runtime = archive['inside_train_arc']
    f = np.array([75.03679765988039, 112.48553445984204, 187.52858173958495])
    p = np.array([-1.0999136177479023, 2.28663683508382, -1.2162815568787233])
    theta = math.tau*t[:, None]*f+p; w = eta(np.cos(theta)+1j*np.sin(theta))
    assert sha(a.extension/extension['runtime_file']) == extension['runtime_sha256']
    with np.load(a.extension/extension['runtime_file']) as archive: data = {k: archive[k] for k in archive.files}
    assert abs(w-data['closure']).max() < 1e-10
    mask = inside(w, rows['source_train']); joint = mask & psi_runtime
    assert np.array_equal(mask, data['inside_train_arc']) and np.array_equal(joint, data['inside_joint_rectangle'])
    assert float(mask.mean()) == extension['runtime_eta_coverage'] and float(mask[:12000].mean()) == extension['runtime_eta_first12_coverage']
    assert float(joint.mean()) == extension['runtime_joint_coverage'] and float(joint[:12000].mean()) == extension['runtime_joint_first12_coverage']
    assert float(3*f[0]-2*f[1]) == extension['eta_frequency_hz']
    r.update(result='all8_eta_501lag_curves_and180000_joint_decisions_verified',
        input_report_sha256=sha(a.input/'report.json'), extension_report_sha256=sha(a.extension/'report.json'),
        runtime_changed=False, audio_generated=False, known_integer_and_origin=True)
except Exception as exc: r.update(result='failed', error=repr(exc)); raise
finally: save(a.out/'report.json', r)
print(r, flush=True)
