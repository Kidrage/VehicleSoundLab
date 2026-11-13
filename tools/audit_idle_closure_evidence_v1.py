"""Independent real closure, unwrap/QR, linear convolution and finite-support checks."""
import argparse
import math
import shutil
import sys
from pathlib import Path
p = argparse.ArgumentParser(description=__doc__)
for key in ['workspace', 'input', 'out']: p.add_argument('--'+key, type=Path, required=True)
a = p.parse_args(); repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(a.workspace/'tools/python_deps'))
import numpy as np
from scipy import signal
from research_archive_v1 import load, save, sha

F = np.array([75.03679765988039, 112.48553445984204, 187.52858173958495])
P = np.array([-1.0999136177479023, 2.28663683508382, -1.2162815568787233])
LAGS = np.arange(501)*48


def closed(z):
    a, b, c = z.T
    u, v = c.real*b.real+c.imag*b.imag, c.imag*b.real-c.real*b.imag
    return (u*a.real+v*a.imag)+1j*(v*a.real-u*a.imag)


def statistics(z):
    w = closed(z); n = len(w); mean = complex(math.fsum(w.real)/n, math.fsum(w.imag)/n)
    center = math.atan2(mean.imag, mean.real); principal = np.angle(w*(math.cos(center)-1j*math.sin(center)))
    angle = np.unwrap(np.angle(w)); t = (np.arange(n)-(n-1)/2)/48000
    Q, R = np.linalg.qr(np.column_stack((np.ones(n), t)), mode='reduced'); beta = np.linalg.solve(R, Q.T@angle)
    residual = angle-beta[0]-t*beta[1]; covariance = signal.fftconvolve(residual[::-1], residual, mode='full')[n-1+LAGS]/(n-LAGS)
    prefix = np.r_[0., np.cumsum(angle**2)]; product = signal.fftconvolve(angle[::-1], angle, mode='full')[n-1+LAGS]
    inc = (prefix[n]-prefix[LAGS]+prefix[n-LAGS]-2*product)/(n-LAGS)
    variance = math.fsum(residual**2)/n
    result = dict(frames=n, circular_center_rad=center, resultant=abs(mean),
        circular_mean_real_imag=[mean.real, mean.imag], principal_quantiles=np.quantile(principal, [0., .01, .05, .5, .95, .99, 1.]),
        observed_step_absmax_rad=float(abs(np.diff(angle)).max()), descriptive_linear_slope_hz=beta[1]/math.tau,
        detrended_std_rad=math.sqrt(variance), empirical_chart_valid=bool(abs(principal).max() < math.pi-.05),
        empirical_arc_rad=[float(principal.min()), float(principal.max())])
    arrays = dict(closure=w, unwrapped=angle, residual=residual, residual_covariance=covariance,
                  residual_correlation=covariance/variance, phase_increment_second=inc)
    return result, arrays


def compare_stats(expected, actual):
    errors = []
    for key, value in expected.items():
        if isinstance(value, bool): assert value == actual[key]
        else:
            error = float(np.max(abs(np.asarray(value)-actual[key]))); assert error < 1e-9, (key, error); errors.append(error)
    return max(errors)


def original_observer(x):
    output = []
    for f in F:
        sos = signal.butter(4, [f-10, f+10], btype='bandpass', fs=48000, output='sos')
        y = signal.sosfiltfilt(sos, x); spectrum = np.fft.fft(y)
        multiplier = np.zeros(len(y)); multiplier[0] = multiplier[len(y)//2] = 1.; multiplier[1:len(y)//2] = 2.
        analytic = np.fft.ifft(spectrum*multiplier); output.append(analytic/abs(analytic))
    return np.array(output).T[12000:-12000]


def known(report):
    delta = float(F[2]-F[1]-F[0]); phi = P[2]-P[1]-P[0]
    short = abs(math.sin(math.pi*delta*2.5)/(120000*math.sin(math.pi*delta/48000)))
    long = abs(math.sin(math.pi*delta*180)/(180000*math.sin(math.pi*delta/1000)))
    assert abs(short-report['independent_short_resultant']) < 1e-12 and abs(long-report['independent180s_resultant']) < 1e-12
    maximum = 0.
    for row in report['original_observer']:
        t = np.arange(144000)/48000+row['portion']*3
        theta = math.tau*t[:, None]*F+P
        if row['kind'] == 'bounded_third_FM': theta[:, 2] += .18*np.sin(math.tau*2.3*t)
        amplitude = np.tile([.07959081914372979, .0751960872053696, .03924681140931266], (144000, 1))
        if row['kind'] == 'independent_AM': amplitude *= 1+.25*np.cos(math.tau*t[:, None]*[1.3, 1.7, 2.1]+[.2, -.4, .7])
        x = (np.cos(theta)*amplitude).sum(axis=1); z = original_observer(x)
        truth = np.cos(theta[12000:-12000])+1j*np.sin(theta[12000:-12000])
        error = float(np.quantile(abs(np.angle(closed(z)*closed(truth).conj())), .95))
        assert error < .105 and abs(error-row['p95_observer_closure_error_rad']) < 1e-9
        stats, _ = statistics(z); maximum = max(maximum, compare_stats(stats, row))
    t = np.arange(30000)/48000; angle = .31+math.tau*.013*t+.17*np.sin(math.tau*3.1*t)+.07*np.cos(math.tau*7.3*t)
    # Construct phasors with exactly the known closure, then verify ALL501 overlaps directly.
    z = np.column_stack((np.ones(len(t), complex), np.ones(len(t), complex), np.exp(1j*angle)))
    stats, arrays = statistics(z); residual = arrays['residual']; raw = arrays['unwrapped']
    covariance = np.array([math.fsum(residual[:len(t)-lag]*residual[lag:])/(len(t)-lag) for lag in LAGS])
    increments = np.array([math.fsum((raw[lag:]-raw[:len(t)-lag])**2)/(len(t)-lag) for lag in LAGS])
    assert abs(covariance-arrays['residual_covariance']).max() < 1e-12
    assert abs(increments-arrays['phase_increment_second']).max() < 1e-12
    theta = math.tau*t[:, None]*F+P; z = np.exp(1j*theta); s, _ = statistics(z)
    assert abs(s['descriptive_linear_slope_hz']-delta) < 1e-10
    changed, _ = statistics(z*np.exp(1j*np.array([.1, -.3, .7])))
    assert abs(changed['resultant']-s['resultant']) < 1e-12
    return dict(max_known_report_error=maximum, all501_direct=True, independent_short=short, independent_long=long)


def membership(w, train):
    if not train['empirical_chart_valid']: return None
    p = train['circular_center_rad']; deviation = np.arctan2(w.imag*math.cos(p)-w.real*math.sin(p),
                                                           w.real*math.cos(p)+w.imag*math.sin(p))
    lo, hi = train['empirical_arc_rad']; return (deviation >= lo) & (deviation <= hi)


a.out.mkdir(parents=True, exist_ok=False); shutil.copy2(__file__, a.out/'executed_auditor.py')
r = dict(result='running', max_stats_error=0., max_array_error=0., observations=0)
try:
    observed = load(a.input/'report.json'); assert observed['result'] == 'all8_closure_portions_and_shortrecord_counterexample_observed'
    r['known'] = known(observed['known']); print(dict(stage='independent_known_pass'), flush=True)
    for name, digest in observed['sources'].items(): assert digest == sha(repo/name) == sha(a.input/'exact_sources'/name)
    tables = {}
    for name, digest in observed['parent_manifests'].items():
        path = a.workspace/'baselines'/name/'manifest.json'; assert sha(path) == digest
        tables[name] = {row['path']: row['sha256'] for row in load(path)['files']}
    for path, digest in observed['inputs'].items():
        rel = Path(path).resolve().relative_to((a.workspace/'baselines').resolve())
        assert sha(path) == digest == tables[rel.parts[0]][Path(*rel.parts[1:]).as_posix()]
    beta = np.asarray(load(observed['law_path'])['observations'][0]['models']['expanded']['coefficients'])
    rows = {}; arrays = {}
    for row in observed['observations']:
        with np.load(row['input_path']) as parent: z = parent['phasors'][12000:-12000]
        assert sha(a.input/row['file']) == row['sha256']
        with np.load(a.input/row['file']) as archive: data = {key: archive[key] for key in archive.files}
        assert np.array_equal(z, data['phasors']) and np.array_equal(data['lags_frames'], LAGS)
        stats, value = statistics(z); r['max_stats_error'] = max(r['max_stats_error'], compare_stats(stats, row))
        for key, expected in value.items():
            error = float(abs(expected-data[key]).max()); r['max_array_error'] = max(r['max_array_error'], error)
            assert error < 1e-8, (row['label'], key, error)
        # Evaluate the frozen source law by explicit real complex-product coordinates.
        features = [z[:, k] for k in range(3)]+[z[:, j]*z[:, i].conj() for i, j in [(0, 1), (0, 2), (1, 2)]]
        eta = np.tile(beta[0], (len(z), 1))
        for k, f in enumerate(features): eta += f.real[:, None]*beta[k+1]+f.imag[:, None]*beta[k+7]
        q = np.exp(eta); assert abs(q-data['q']).max() < 1e-12
        if row['group'] == 'source':
            with np.load(a.workspace/f"baselines/idle_phase_transfer_v1/evidence/observe1/source_{row['part']}.npz") as prior:
                assert np.array_equal(prior['q'], data['q'])
                mean = np.array([math.fsum(q[:, b])/len(q) for b in range(4)])
                covariance = np.array([[math.fsum((q[:, b]-mean[b])*(q[:, c]-mean[c]))/len(q) for c in range(4)] for b in range(4)])
                assert abs(mean-prior['mean']).max() < 1e-10 and abs(covariance-prior['covariance']).max() < 1e-10
        rows[row['label']] = stats; arrays[row['label']] = value; r['observations'] += 1
    assert r['observations'] == 8
    for group, fraction in observed['source_arc_check_coverage'].items():
        # Use the exact archived empirical endpoints for endpoint inclusivity; independently checked above.
        train = next(x for x in observed['observations'] if x['label'] == group+'_train')
        inside = membership(arrays[group+'_check']['closure'], train)
        if inside is None: assert fraction is None
        else: assert float(inside.mean()) == fraction
    assert sha(a.input/observed['runtime_arc_file']) == observed['runtime_arc_sha256']
    with np.load(a.input/observed['runtime_arc_file']) as archive: data = {key: archive[key] for key in archive.files}
    t = (np.arange(180000)*48+23.5)/48000; theta = math.tau*t[:, None]*F+P
    w = closed(np.cos(theta)+1j*np.sin(theta)); assert abs(w-data['closure']).max() < 1e-10
    train = next(x for x in observed['observations'] if x['label'] == 'source_train')
    inside = membership(w, train); assert np.array_equal(inside, data['inside_train_arc'])
    assert float(inside.mean()) == observed['runtime_arc_coverage']
    assert float(inside[:12000].mean()) == observed['runtime_first12s_arc_coverage']
    for name, count in [('C_files_sha256.json', 612), ('voice_files_sha256.json', 67)]:
        values = load(a.workspace/'baselines/idle_microtexture_c_v1/inputs'/name); assert len(values) == count
        for source, digest in values.items(): assert sha(repo/source) == digest
    r.update(result='all8_closure_501lag_curves_and180000_arc_decisions_verified',
        input_report_sha256=sha(a.input/'report.json'), runtime_changed=False,
        longterm_stationary_coupling_identified=False, audio_generated=False)
except Exception as exc: r.update(result='failed', error=repr(exc)); raise
finally: save(a.out/'report.json', r)
print(r, flush=True)
