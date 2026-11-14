"""Retain the new DNA; fit an existing joint-channel kernel to its stereo debt."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

p = argparse.ArgumentParser(description=__doc__)
for key in ('workspace', 'fit', 'out', 'stereo-probe', 'dna-probe'):
    p.add_argument('--'+key, type=Path, required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(a.workspace/'tools/python_deps'))
for key in ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS'):
    os.environ[key] = '2'
import numpy as np
import soundfile as sf
from scipy import linalg
from scipy.optimize import nnls
from research_archive_v1 import load, save, sha
from residual_osc_v1.spectrum import matrices, error
from stereo_resonance_v1.model import matrix, predictor, fit, density, measured, pack, export

a.out.mkdir(parents=True, exist_ok=False)
r = dict(result='running', sources={}, inputs={}, models=[], skipped=[], commands=[], trials=[])


def consume(path):
    r['inputs'][str(path)] = sha(path)
    return path


def run(argv, label):
    result = subprocess.run(list(map(str, argv)), cwd=repo, capture_output=True, timeout=180)
    path = a.out/(label+'.log')
    path.write_bytes(result.stdout+result.stderr)
    r['commands'].append(dict(argv=list(map(str, argv)), exit_code=result.returncode, log=path.name))
    save(a.out/'report.json', r)
    assert result.returncode == 0, path


try:
    names = ['tools/fit_E_decel_stereo_v1.py', 'research/E_decel_stereo_v1_plan.json',
             'tools/stereo_resonance_v1/model.py', 'tools/residual_osc_v1/spectrum.py',
             'tools/research_archive_v1.py']
    for name in names:
        target = a.out/'exact_sources'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo/name, target)
        r['sources'][name] = sha(repo/name)
    plan = load(consume(repo/'research/E_decel_stereo_v1_plan.json'))
    # Known cross-lag orientation/predictor controls before loading the fitted source.
    coef = np.array([[[.23, .04], [-.06, -.18]], [[.08, -.02], [.03, .05]], [[-.04, .01], [.02, .03]]])
    noise = np.array([[.3, 0], [.17, .2]])
    companion = np.zeros((6, 6))
    companion[:2] = coef.transpose(1, 0, 2).reshape(2, 6)
    companion[2:, :-2] = np.eye(4)
    innovation = np.zeros((6, 6)); innovation[:2, :2] = noise@noise.T
    stationary = linalg.solve_discrete_lyapunov(companion, innovation)
    gamma = np.array([(np.linalg.matrix_power(companion, k)@stationary)[:2, :2] for k in range(4)])
    recovered, root = predictor(gamma, 3)
    maximum = max(float(abs(recovered-coef).max()), float(abs(root@root.T-noise@noise.T).max()))
    assert maximum < plan['gates']['known_predictor_FS']
    delay = np.zeros((3, 2, 2)); delay[2, 1, 0] = .6
    fixture = dict(a=delay.tolist(), noise=[[1, 0], [0, .8]], sos=[[1, 0, 0, 1, 0, 0]])
    spectral = density(fixture)
    hz = np.arange(len(spectral))*48000/len(spectral)
    signed_error = float(abs(spectral[:, 1, 0]-.6*np.exp(-2j*np.pi*hz*3/48000)/48000).max())
    assert signed_error < plan['gates']['known_signed_density_FS2_per_Hz']
    r['known_before_source'] = dict(predictor_error=maximum, signed_delay_density_error=signed_error)
    previous = load(consume(a.fit/'report.json'))
    assert previous['result'] == 'fixed_centers_checked' and previous['accepted_count'] == 1
    anchor = previous['accepted'][0]
    folder = a.fit/anchor['case']['name']
    reference, rate = sf.read(consume(folder/'reference.wav'), always_2d=True)
    assert rate == 48000
    main_short, rate = sf.read(consume(folder/'withdraw35.wav'), always_2d=True)
    assert rate == 48000
    bands = plan['bands_hz']
    target = np.array([matrix(v) for v in matrices(reference, bands)])
    current = np.array([matrix(v) for v in matrices(main_short[24000:], bands)])
    debt = target-current
    save(a.out/'target_matrices.json', dict(target=pack(target).tolist(), main=pack(current).tolist(), debt=pack(debt).tolist()))
    predictions = []
    for band, wanted in zip(bands, debt):
        eigenvalues = np.linalg.eigvalsh(wanted)
        if min(eigenvalues) <= 0:
            r['skipped'].append(dict(band=band, debt_eigenvalues=eigenvalues.tolist(), reason='Indefinite additive debt; no clipping or strength rescue'))
            continue
        model = fit(reference, band, wanted, plan['kernel'])
        predictions.append(measured(density(model), bands))
        r['models'].append(model)
        save(a.out/'report.json', r)
        print(dict(band=band, pole_radius=model['pole_radius']), flush=True)
    assert r['models'], 'No positive stereo debt bands'
    design = np.stack([pack(v).ravel() for v in predictions], axis=1)
    scale = pack(target).copy()
    scale[:, 2:] = np.sqrt(scale[:, 0]*scale[:, 1])[:, None]
    scale = 1/scale.ravel()
    gain, _ = nnls(design*scale[:, None], pack(debt).ravel()*scale)
    for model, value in zip(r['models'], gain):
        model['gain'] = float(np.sqrt(value))
    expected = sum(g*v for g, v in zip(gain, predictions))
    profile = a.out/'E slowing cabin.sres'
    export(profile, r['models'], anchor['root_hz'])
    # Extend the same C main stream forward, verifying its old prefix exactly.
    run([a.dna_probe, folder/'withdraw35.model', a.out/'main32.wav', plan['statistics_seconds'], 1, 1, 1], 'main32')
    consume(a.dna_probe); consume(a.stereo_probe); consume(folder/'withdraw35.model')
    main, rate = sf.read(a.out/'main32.wav', always_2d=True)
    assert rate == 48000 and np.array_equal(main[:len(main_short)], main_short)
    r['main_first8s_exact'] = True
    for seed in plan['seeds']:
        output = a.out/f'detail32_{seed}.f64'
        run([a.stereo_probe, profile, output, seed, len(main), 1], f'stereo_{seed}')
        detail = np.fromfile(output, dtype='<f8').reshape(-1, 2)
        assert detail.shape == main.shape and np.isfinite(detail).all()
        assert not np.array_equal(detail[:48000], detail[48000:96000])
        actual = np.array([matrix(v) for v in matrices(detail, bands)])
        diagnostic = []
        for wanted, got in zip(expected, actual):
            power_error = (10*np.log10(got.diagonal().real/wanted.diagonal().real)).tolist()
            c = got[1, 0]/np.sqrt(got[0, 0]*got[1, 1])
            d = wanted[1, 0]/np.sqrt(wanted[0, 0]*wanted[1, 1])
            diagnostic.append(dict(power_error_db=power_error, complex_coherence_error=float(abs(c-d))))
        assert max(abs(v) for x in diagnostic for v in x['power_error_db']) < plan['gates']['C_theory_power_db']
        assert max(x['complex_coherence_error'] for x in diagnostic) < plan['gates']['C_theory_complex_coherence']
        mixed = main+detail
        assert abs(mixed).max()*.5 < plan['gates']['peak_after_common_gain']
        count = plan['audition_seconds']*48000
        sf.write(a.out/f'candidate_{seed}.wav', mixed[:count], 48000, subtype='FLOAT')
        sf.write(a.out/f'detail_{seed}.wav', detail[:count], 48000, subtype='FLOAT')
        short_metrics = error(matrices(reference, bands), matrices(mixed[24000:count], bands))
        trial = dict(seed=seed, C_theory=diagnostic, short_mixed_vs_reference=short_metrics,
                     maximum_complex_coherence_error=max(x['complex_coherence_error'] for x in short_metrics),
                     maximum_power_error_db=max(abs(v) for x in short_metrics for v in x['power_delta_db']),
                     peak_FS=float(abs(mixed).max()))
        r['trials'].append(trial)
        save(a.out/'report.json', r)
        print(dict(seed=seed, max_coherence=trial['maximum_complex_coherence_error'], max_power_db=trial['maximum_power_error_db']), flush=True)
    r.update(result='stereo_extension_rendered', root_hz=anchor['root_hz'], profile_sha256=sha(profile),
             same_main=True, same_withdrawal=True, room=False, human_accepted=False, runtime_changed=False)
except Exception as exc:
    r.update(result='failed', error=repr(exc))
    raise
finally:
    save(a.out/'report.json', r)
