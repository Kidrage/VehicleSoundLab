"""Independent real-trigonometric transfer and native arithmetic, all180s retained."""
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
from research_archive_v1 import load, save, sha


def feature(z):
    re = [z[:, k].real for k in range(3)]; im = [z[:, k].imag for k in range(3)]
    for i, j in [(0, 1), (0, 2), (1, 2)]:
        re.append(re[j]*re[i]+im[j]*im[i]); im.append(im[j]*re[i]-re[j]*im[i])
    return re+im


def evaluate(features, coefficient):
    eta = np.tile(coefficient[0], (len(features[0]), 1))
    for k, column in enumerate(features): eta += column[:, None]*coefficient[k+1]
    return np.exp(eta)


def average1ms(q):
    out = np.zeros((len(q)//48, 4))
    for offset in range(48): out += q[offset::48]/48
    return out


def statistics(q, z, columns):
    n = len(q); mean = np.array([math.fsum(q[:, b])/n for b in range(4)])
    second = np.array([[math.fsum(q[:, b]*q[:, c])/n for c in range(4)] for b in range(4)])
    covariance = np.array([[math.fsum((q[:, b]-mean[b])*(q[:, c]-mean[c]))/n for c in range(4)] for b in range(4)])
    sorted_q = np.sort(q, axis=0); position = np.array([0., .01, .5, .99, 1.])*(n-1)
    lo, hi = np.floor(position).astype(int), np.ceil(position).astype(int)
    quantile = sorted_q[lo]+(position-lo)[:, None]*(sorted_q[hi]-sorted_q[lo])
    # Independent closure via real multiplications of z2 * conj(z1) * conj(z0).
    a, b, c = z[:, 0], z[:, 1], z[:, 2]
    u, v = c.real*b.real+c.imag*b.imag, c.imag*b.real-c.real*b.imag
    closure_re, closure_im = u*a.real+v*a.imag, v*a.real-u*a.imag
    circular = np.array([complex(math.fsum(v.real)/n, math.fsum(v.imag)/n) for v in z.T]+
                        [complex(math.fsum(closure_re)/n, math.fsum(closure_im)/n)])
    return dict(mean=mean, second=second, covariance=covariance, quantiles=quantile,
                circular=circular, resultant=abs(circular),
                feature_mean=np.array([math.fsum(v)/n for v in columns]))


def assert_values(expected, actual, errors):
    for key, value in expected.items():
        if key == 'circular':
            value = np.column_stack((value.real, value.imag)); target = actual['circular_real_imag']
        else: target = actual[key]
        error = float(abs(value-target).max()); errors[key] = max(errors.get(key, 0.), error)
        assert error < 1e-9, (key, error)


def known():
    f = np.array([75., 112.5, 187.5]); p = np.array([.2, -.4, .7]); t = np.arange(48000)/48000
    angles = math.tau*t[:, None]*f+p; z = np.cos(angles)+1j*np.sin(angles)
    beta = np.zeros((13, 4)); beta[0] = np.log([.7, 1., 1.3, 2.])
    q = evaluate(feature(z), beta); assert abs(q-[.7, 1., 1.3, 2.]).max() < 1e-14
    theta = p[2]-p[1]-p[0]; values = statistics(q, z, feature(z))
    assert abs(values['circular'][-1]-complex(math.cos(theta), math.sin(theta))) < 1e-12
    t = np.arange(180000)/1000
    closure = math.tau*(t*(f[2]+.00625)+p[2]/math.tau-t*f[1]-p[1]/math.tau-t*f[0]-p[0]/math.tau)
    expected = theta+math.tau*.00625*t
    error = float(abs(np.exp(1j*closure)-np.exp(1j*expected)).max()); assert error < 1e-10
    beta = np.sin(np.arange(52).reshape(13, 4))*.07; q = evaluate(feature(z), beta)
    d = np.array([.41, -.37, .83]); changes = np.r_[d, d[1]-d[0], d[2]-d[0], d[2]-d[1]]
    new = beta.copy()
    for j, change in enumerate(changes):
        new[j+1] = beta[j+1]*math.cos(change)-beta[j+7]*math.sin(change)
        new[j+7] = beta[j+1]*math.sin(change)+beta[j+7]*math.cos(change)
    rotated = evaluate(feature(z*(np.cos(d)+1j*np.sin(d))), new)
    assert abs(q-rotated).max() < 1e-12
    chunks = np.concatenate([evaluate(feature(z[i:i+777]), beta) for i in range(0, len(z), 777)])
    assert abs(chunks-q).max() < 1e-12
    return dict(constant=True, analytic_closed=True, analytic_detuned180s_error=error, rotation=True, chunks=True)


a.out.mkdir(parents=True, exist_ok=False); shutil.copy2(__file__, a.out/'executed_auditor.py')
r = dict(result='running', errors={}, native_q_error=0., mean1ms_error=0.)
try:
    r['known'] = known(); print(dict(stage='independent_known', result=r['known']), flush=True)
    observed = load(a.input/'report.json'); assert observed['result'] == 'all180s_power_phase_transfer_observed_NO_recipe_change'
    for name, digest in observed['sources'].items(): assert digest == sha(repo/name) == sha(a.input/'exact_sources'/name)
    tables = {}
    for name, digest in observed['parent_manifests'].items():
        path = a.workspace/'baselines'/name/'manifest.json'; assert sha(path) == digest
        tables[name] = {v['path']: v['sha256'] for v in load(path)['files']}
    for path, digest in observed['inputs'].items():
        rel = Path(path).resolve().relative_to((a.workspace/'baselines').resolve())
        assert sha(path) == digest == tables[rel.parts[0]][Path(*rel.parts[1:]).as_posix()]
    profile = load(observed['profile_path']); law = load(observed['law_path'])['observations'][0]['models']['expanded']
    beta = np.asarray(law['coefficients'])
    for row in observed['source_observations']:
        assert sha(a.input/row['file']) == row['sha256']
        with np.load(row['path']) as archive: z = archive['phasors'][12000:-12000]
        with np.load(a.input/row['file']) as archive: data = {k: archive[k] for k in archive.files}
        columns = feature(z); q = evaluate(columns, beta); values = statistics(q, z, columns)
        assert np.array_equal(z, data['phasors']); assert_values(values, row, r['errors'])
        error = float(abs(q-data['q']).max()); assert error < 1e-12
        r['native_q_error'] = max(r['native_q_error'], error)
        error = float(abs(average1ms(q)-data['q_mean1ms']).max()); assert error < 1e-12
        with np.load(a.workspace/'baselines/idle_positive_power_v1/evidence/observe1/source.npz') as archive:
            assert abs(average1ms(q)-archive['expanded_'+row['part']+'_prediction']).max() < 1e-12
    assert sha(a.input/observed['data_file']) == observed['data_sha256']
    with np.load(a.input/observed['data_file']) as archive: data = {k: archive[k] for k in archive.files}
    oldq = np.load(a.workspace/'baselines/idle_post_audio_v1/evidence/render1/native_q.npy')
    f = np.asarray(profile['modal']['frequencies_hz'])[[1, 2, 4]]
    initial = np.asarray(profile['modal']['initial_phase_LR'])[[1, 2, 4], 0]; allvalues = []
    for block, row in enumerate(observed['runtime']):
        assert row['block'] == block and row['start_seconds'] == block*3
        t = np.arange(block*144000, (block+1)*144000)/48000
        theta = [math.tau*t*hz+p for hz, p in zip(f, initial)]
        expanded = theta+[theta[j]-theta[i] for i, j in [(0, 1), (0, 2), (1, 2)]]
        columns = [np.cos(v) for v in expanded]+[np.sin(v) for v in expanded]
        z = np.array([np.cos(v)+1j*np.sin(v) for v in theta]).T
        q = evaluate(columns, beta); values = statistics(q, z, columns); allvalues.append(values)
        assert_values(values, row, r['errors'])
        for key, target in [('mean', 'block_means'), ('second', 'block_second'),
                            ('quantiles', 'block_quantiles'), ('feature_mean', 'block_feature_means'), ('circular', 'block_circular')]:
            assert abs(values[key]-data[target][block]).max() < 1e-9
        means = average1ms(q); error = float(abs(means-data['q_mean1ms'][block*3000:(block+1)*3000]).max())
        r['mean1ms_error'] = max(r['mean1ms_error'], error); assert error < 1e-9
        if block < 4:
            error = float(abs(q-oldq[block*144000:(block+1)*144000]).max())
            r['native_q_error'] = max(r['native_q_error'], error); assert error < 1e-10
        assert np.all(q.min(axis=0) >= law['bounds']['power_lower']) and np.all(q.max(axis=0) <= law['bounds']['power_upper'])
        if block % 10 == 9: print(dict(stage='independent_native', blocks=block+1, total=60), flush=True)
    assert len(allvalues) == 60
    means = np.array([v['mean'] for v in allvalues]); second = np.array([v['second'] for v in allvalues])
    full = means.mean(axis=0); covariance = second.mean(axis=0)-np.outer(full, full)
    assert abs(full-observed['full180s']['mean']).max() < 1e-9
    assert abs(covariance-observed['full180s']['covariance']).max() < 1e-9
    circular = np.array([v['circular'] for v in allvalues]).mean(axis=0)
    assert abs(abs(circular)-observed['full180s']['resultant']).max() < 1e-9
    ratio = 10*np.log10(means/means[:4].mean(axis=0))
    assert abs(ratio-observed['block_q_power_db_relative_first12']).max() < 1e-9
    assert abs(means.min(axis=0)-observed['runtime_block_mean_min']).max() < 1e-9
    assert abs(means.max(axis=0)-observed['runtime_block_mean_max']).max() < 1e-9
    delta = float(f[2]-f[1]-f[0]); assert delta == observed['detuning_hz'] and 1/abs(delta) == observed['closure_period_seconds']
    for name, count in [('C_files_sha256.json', 612), ('voice_files_sha256.json', 67)]:
        entries = load(a.workspace/'baselines/idle_microtexture_c_v1/inputs'/name); assert len(entries) == count
        for source, digest in entries.items(): assert sha(repo/source) == digest
    r.update(result='all60_native_blocks_and_both_recorded_phase_portions_verified',
             input_report_sha256=sha(a.input/'report.json'), runtime_changed=False, audio_generated=False,
             source_phase_is_not_free_modal_phase=True, listening_accepted=False)
except Exception as exc: r.update(result='failed', error=repr(exc)); raise
finally: save(a.out/'report.json', r)
print(r, flush=True)
