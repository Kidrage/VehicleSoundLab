"""Exact-moment check of frozen F3 parameters, with unchanged deterministic replay.

No alternative fitting or source search. Original projection audit is preserved;
the reported finite-perturbation bound is conditional on the actual two arrays.
"""
import argparse
import math
import os
from pathlib import Path
import shutil
import sys

p = argparse.ArgumentParser(description=__doc__)
for key in ('workspace', 'controls', 'out'):
    p.add_argument('--'+key, type=Path, required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(a.workspace/'tools/python_deps'))
for key in ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS'):
    os.environ[key] = '2'
import numpy as np
import soundfile as sf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from local_voice_batch_v1.ratio_exact import exact_rho, compare
from local_voice_batch_v1.ratio_trace import trace
from local_voice_batch_v1.audit_kernels import rebuild
from decel_source_v1.aperture import extract
from sound_dna.windowed import coefficients
from sound_dna.profile import export
from idle_texture_v1.profile import load as model_load
from research_archive_v1 import load, save, sha, verify

a.out.mkdir(parents=True, exist_ok=False)
r = dict(result='running', sources={}, inputs={}, cases=[])


def consume(path):
    r['inputs'][str(path)] = sha(path)
    return path


def direct_rows(audio, h, reduced):
    w = .5-.5*np.cos(2*np.pi*np.arange(4096)/4096)
    orders = np.arange(1, h+1)
    if reduced:
        kernel = np.exp(-2j*np.pi*((orders[:, None]*np.arange(4096)[None, :]) % 1024)/1024)
    else:
        # Same multiplication grouping as the original independent audit2.
        kernel = np.exp(-2j*np.pi*orders[:, None]*np.arange(4096)[None, :]/1024)
    kernel *= w[None, :]*2/math.fsum(w)
    result = []
    for start in range(0, len(audio)-4096+1, 256):
        at = orders*start
        rotation = np.exp(-2j*np.pi*((at % 1024) if reduced else at)/1024)
        z = kernel@audio[start:start+4096]*rotation[:, None]
        result.append(np.column_stack([z[:, 0].real, z[:, 0].imag, z[:, 1].real, z[:, 1].imag]).ravel())
    return np.array(result)


def alternative_residual(rows, model):
    h, k = model['basis'].shape[:2]
    flat = model['basis'].transpose(1, 0, 2).reshape(k, h*4)
    centered = rows-rows.mean(axis=0)
    scores = centered@flat.T/np.sum(flat*flat, axis=1)[None, :]
    return (centered-scores@flat).reshape(-1, h, 4)


try:
    control = load(consume(a.controls/'report.json'))
    assert control['result'] == 'known_exact_moment_and_perturbation_controls_passed' and not control['real_source_read']
    for name, digest in control['sources'].items():
        assert sha(repo/name) == digest == sha(a.controls/'exact_sources'/name)
    names = set(control['sources']) | {
        'tools/replay_residual_ratio_numeric_v1.py', 'tools/local_voice_batch_v1/audit_kernels.py',
        'tools/decel_source_v1/aperture.py', 'tools/exterior_clock_v1/warp.py',
        'tools/sound_dna/windowed.py', 'tools/sound_dna/profile.py',
        'tools/idle_texture_v1/profile.py', 'tools/sustain_osc_v1/oracle.py'}
    for name in sorted(names):
        dest = a.out/'exact_sources'/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo/name, dest)
        r['sources'][name] = sha(repo/name)
    numeric_plan = load(repo/'research/residual_ratio_numeric_v1_plan.json')
    parent = a.workspace/'baselines/F3_fifth_voice_v1'
    verify(parent)
    consume(parent/'manifest.json')
    evidence = parent/'evidence'
    fit = load(consume(evidence/'fit1/report.json'))
    audit = load(consume(evidence/'audit2/report.json'))
    plan = load(consume(evidence/'fit1/exact_sources/research/F3_fifth_voice_v1_plan.json'))
    assert fit['qualified'] == 2 and not audit['residual_rho_absolute_gate_passed']
    for name, digest in fit['sources'].items():
        assert sha(repo/name) == digest == sha(evidence/'fit1/exact_sources'/name)
    fig, axes = plt.subplots(2, 2, figsize=(11, 6), layout='constrained')
    for i, item in enumerate(fit['cases']):
        case = item['case']
        folder = evidence/'fit1'/case['name']
        out = a.out/case['name']
        out.mkdir(exist_ok=False)
        native, rate = sf.read(consume(folder/'native.wav'), always_2d=True)
        assert rate == 48000
        normalized, positions, info = extract(native, case['seconds'][0], item['family']['rows'], case['center_seconds'], plan)
        assert info == item['extraction']
        rows = coefficients(normalized, plan['harmonics'])
        model, statistics, residual, projected = trace(rows, plan['harmonics'], plan['components'])
        export(out/'replayed.model', model, info['root_hz'])
        expected_model = consume(folder/'voice.model')
        assert sha(out/'replayed.model') == sha(expected_model)
        stored, root = model_load(expected_model)
        independent_audio = rebuild(native, case['seconds'][0], positions, info['phase']['source_cutoff_hz'])
        alternatives = dict(same_FFT_projection=projected,
                            original_direct_projection=alternative_residual(direct_rows(independent_audio, plan['harmonics'], False), stored),
                            modulo_direct_projection=alternative_residual(direct_rows(independent_audio, plan['harmonics'], True), stored))
        checks = []
        for h in range(plan['harmonics']):
            exact, moments = exact_rho(residual[:, h])
            literal_error = abs(exact-stored['residual_rho'][h])
            assert literal_error < numeric_plan['literal_moment_error_gate']
            tampered = stored['residual_rho'][h]+(-numeric_plan['tamper_delta'] if exact >= 0 else numeric_plan['tamper_delta'])
            assert abs(tampered-exact) > numeric_plan['literal_moment_error_gate']
            variants = {name: compare(residual[:, h], values[:, h]) for name, values in alternatives.items()}
            checks.append(dict(order=h+1, exact_rho=exact, stored_rho=float(stored['residual_rho'][h]),
                               literal_error=literal_error, tamper_rejected=True, moments=moments, alternatives=variants))
        np.savez_compressed(out/'residual_trace.npz', input_rows=rows, actual_residual=residual,
                            literal_rho=stored['residual_rho'], **alternatives)
        row = dict(name=case['name'], original_model_sha256=sha(expected_model),
                   replayed_model_sha256=sha(out/'replayed.model'), replayed_model_exact=True,
                   root_hz=root, normalized_frames=len(normalized), statistics=statistics,
                   actual_to_independent_normalized_error_FS=float(abs(normalized-independent_audio).max()),
                   exact_moment_maximum_error=max(v['literal_error'] for v in checks),
                   original_1e9_gate_passed=False, old_audit= audit['cases'][i]['residual_rho_check'],
                   original_independent_audit_relabelled=False, harmonics=checks)
        r['cases'].append(row)
        order = np.arange(1, plan['harmonics']+1)
        for name in alternatives:
            differences = [v['alternatives'][name]['exact_quotient_difference'] for v in checks]
            bounds = [v['alternatives'][name]['perturbation_bound'] for v in checks]
            axes[i, 0].semilogy(order, np.maximum(differences, 1e-18), label=name)
            if name == 'original_direct_projection':
                axes[i, 0].semilogy(order, np.maximum(bounds, 1e-18), '--', label='exact finite-perturbation bound')
        axes[i, 0].axhline(1e-9, color='red', ls=':')
        axes[i, 0].set(title=case['name'], xlabel='Acoustic harmonic', ylabel='Rho difference / bound')
        axes[i, 0].legend(fontsize=6)
        axes[i, 1].semilogy(order, np.maximum([v['moments']['denominator_FS2'] for v in checks], 1e-40))
        axes[i, 1].set(title='Actual residual energy / denominator', xlabel='Acoustic harmonic', ylabel='Sum squares FS2')
        save(a.out/'report.json', r)
    fig.savefig(a.out/'conditioning.png', dpi=145)
    plt.close(fig)
    for filename, count in [('C_files_sha256.json', 650), ('voice_files_sha256.json', 76)]:
        records = load(consume(a.workspace/'baselines/catalog_F3_v1/inputs'/filename))
        assert len(records) == count and all(sha(repo/name) == digest for name, digest in records.items())
    r.update(result='frozen_models_replay_exact_and_literal_rho_moments_verified',
             frozen_profiles_checked=2, exact_harmonic_moment_checks=576, tamper_rejections=576,
             finite_perturbation_pairs=1728, original_projection_gate_passed=False,
             original_audit_relabelled=False, independent_SVD=False,
             interpretation='Literal stored calculation verified and exact conditional perturbation containment; no universal FFT/SVD bound or timbre/state acceptance.',
             new_audio=False, runtime_changed=False, source_gate_changed=False,
             protected_C_H_exact=650, protected_voice_parameters_exact=76)
except Exception as exc:
    r.update(result='failed', error=repr(exc))
    raise
finally:
    save(a.out/'report.json', r)
print(dict(result=r['result'], cases=[(v['name'], v['replayed_model_exact'], v['exact_moment_maximum_error']) for v in r['cases']]))
