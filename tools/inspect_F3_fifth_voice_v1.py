"""Fixed modulo-phase diagnosis and same-pitch source/model descriptive comparison."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

p = argparse.ArgumentParser(description=__doc__)
for key in ('workspace', 'fit', 'audit', 'out', 'dna-probe'):
    p.add_argument('--'+key, type=Path, required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(a.workspace/'tools/python_deps'))
for key in ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS'):
    os.environ[key] = '2'
import numpy as np
import soundfile as sf
from scipy import signal
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from local_voice_batch_v1.audit_kernels import rebuild
from idle_texture_v1.profile import load as model_load
from research_archive_v1 import load, save, sha

a.out.mkdir(parents=True, exist_ok=False)
r = dict(result='running', sources={}, inputs={}, cases=[])


def consume(path):
    r['inputs'][str(path)] = sha(path)
    return path


def spectrum(audio, plan):
    w = plan['welch']
    size, hop, fft = w['window_samples'], w['hop_samples'], w['fft_samples']
    window = .5-.5*np.cos(2*np.pi*np.arange(size)/size)
    hz = np.arange(fft//2+1)*48000/fft
    power = np.zeros((len(hz), 2))
    cross = np.zeros(len(hz), complex)
    count = 0
    for start in range(0, len(audio)-size+1, hop):
        z = np.fft.rfft(audio[start:start+size]*window[:, None], fft, axis=0)
        power += abs(z)**2
        cross += z[:, 0]*z[:, 1].conj()
        count += 1
    scale = 1/(48000*np.sum(window*window)*count)
    power *= scale
    cross *= scale
    power[1:-1] *= 2
    cross[1:-1] *= 2
    rows = []
    for lo, hi in plan['bands_hz']:
        keep = (hz >= lo) & (hz < hi)
        pp = np.sum(power[keep], axis=0)*48000/fft
        cr = np.sum(cross[keep])*48000/fft
        correlation = cr/np.sqrt(max(pp[0]*pp[1], 1e-60))
        rows.append(dict(hz=[lo, hi], power_LR=pp.tolist(),
                         signed_complex_correlation=[float(correlation.real), float(correlation.imag)]))
    return dict(frames=len(audio), windows=count, bands=rows,
                RMS_LR=np.sqrt(np.mean(audio**2, axis=0)).tolist())


def rho_diagnostic(exact, model, reduced):
    h, k = model['basis'].shape[:2]
    orders = np.arange(1, h+1)
    angles = orders[:, None]*np.arange(4096)[None, :]
    if reduced:
        angles %= 1024
    w = .5-.5*np.cos(2*np.pi*np.arange(4096)/4096)
    kernel = np.exp(-2j*np.pi*angles/1024)*w[None, :]*2/w.sum()
    rows = []
    for start in range(0, len(exact)-4096+1, 256):
        at = orders*start
        if reduced:
            at %= 1024
        z = kernel@exact[start:start+4096]*np.exp(-2j*np.pi*at/1024)[:, None]
        rows.append(np.column_stack([z[:, 0].real, z[:, 0].imag, z[:, 1].real, z[:, 1].imag]).ravel())
    values = np.array(rows)
    centered = values-values.mean(axis=0)
    flat = model['basis'].transpose(1, 0, 2).reshape(k, -1)
    scores = centered@flat.T/np.sum(flat*flat, axis=1)[None, :]
    residual = (centered-scores@flat).reshape(-1, h, 4)
    denominator = np.sum(residual[:-1]**2, axis=(0, 2))
    numerator = np.sum(residual[1:]*residual[:-1], axis=(0, 2))
    rho = np.clip(numerator/np.maximum(denominator, 1e-30), -.95, .95)
    error = abs(rho-model['residual_rho'])
    worst = int(np.argmax(error))
    return dict(maximum_error=float(error.max()), worst_order=worst+1,
                denominator_at_worst=float(denominator[worst]),
                mean_error=float(abs(values.mean(axis=0).reshape(h, 4)-model['mean']).max()),
                original_1e9_gate_passed=bool(error.max() < 1e-9),
                failure_count=int(np.sum(error >= 1e-9))), dict(rho=rho, error=error, denominator=denominator)


def known_finite_tone_band(plan):
    # Closed finite geometric sum of BOTH real-tone images through Hann.
    # An ideal exp(-.4j) is not the exact finite-band/window answer.
    size = plan['welch']['window_samples']
    fft = plan['welch']['fft_samples']
    f = np.arange(fft//2+1)/fft

    def geometric(q):
        result = np.zeros(q.shape, complex)
        integral = q == np.rint(q)
        result[integral] = size
        nonzero = ~integral
        result[nonzero] = np.expm1(-2j*np.pi*size*q[nonzero])/np.expm1(-2j*np.pi*q[nonzero])
        return result

    def hann(q):
        return .5*geometric(q)-.25*geometric(q-1/size)-.25*geometric(q+1/size)

    positive, negative = hann(f-12/size), hann(f+12/size)
    z = np.column_stack([.1*(positive+negative),
                         .06*(np.exp(.4j)*positive+np.exp(-.4j)*negative)])
    factor = np.ones(len(f))*2
    factor[[0, -1]] = 1
    power = abs(z)**2*factor[:, None]/(48000*(3*size/8))
    cross = z[:, 0]*z[:, 1].conj()*factor/(48000*(3*size/8))
    keep = (f*48000 >= 120) & (f*48000 < 400)
    pp = np.sum(power[keep], axis=0)*48000/fft
    cc = np.sum(cross[keep])*48000/fft/np.sqrt(pp[0]*pp[1])
    return pp, cc


try:
    for name in ('tools/inspect_F3_fifth_voice_v1.py', 'research/F3_fifth_compare_v1_plan.json',
                 'tools/local_voice_batch_v1/audit_kernels.py', 'tools/idle_texture_v1/profile.py',
                 'tools/sustain_osc_v1/oracle.py', 'tools/research_archive_v1.py'):
        dest = a.out/'exact_sources'/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo/name, dest)
        r['sources'][name] = sha(repo/name)
    plan = load(repo/'research/F3_fifth_compare_v1_plan.json')
    # Known stationary stereo tone validates power integration and cross sign.
    t = np.arange(48000)/48000
    fixture = np.column_stack([.2*np.cos(2*np.pi*281.25*t), .12*np.cos(2*np.pi*281.25*t+.4)])
    known = spectrum(fixture, plan)
    middle = known['bands'][1]
    assert max(abs(np.array(middle['power_LR'])/np.array([.02, .0072])-1)) < .02
    expected_power, expected_cross = known_finite_tone_band(plan)
    cross_error = abs(complex(*middle['signed_complex_correlation'])-expected_cross)
    assert max(abs(np.array(middle['power_LR'])-expected_power)) < 1e-12 and cross_error < 1e-12
    r['known_before_source'] = known
    r['known_finite_cross_error'] = float(cross_error)
    r['known_ideal_cross_difference'] = float(abs(expected_cross-np.exp(-.4j)))
    fit = load(consume(a.fit/'report.json'))
    audit = load(consume(a.audit/'report.json'))
    assert fit['qualified'] == 2 and audit['result'] == 'audit_complete_with_unresolved_residual_rho_ratio'
    assert not audit['residual_rho_absolute_gate_passed']
    assert subprocess.check_output([str(a.dna_probe), '--describe']).decode().strip() == 'vsl.sound-dna-raw-export/1'
    consume(a.dna_probe)
    fig, axes = plt.subplots(2, 2, figsize=(12, 7), layout='constrained')
    for i, case in enumerate(fit['cases']):
        folder = a.fit/case['case']['name']
        out = a.out/case['case']['name']
        out.mkdir(exist_ok=False)
        model, root = model_load(consume(folder/'voice.model'))
        native, _ = sf.read(consume(folder/'native.wav'), always_2d=True)
        with np.load(consume(folder/'coordinates.npz')) as f:
            positions = f['source_seconds']
        exact = rebuild(native, case['case']['seconds'][0], positions, case['extraction']['phase']['source_cutoff_hz'])
        original, oa = rho_diagnostic(exact, model, False)
        reduced, ra = rho_diagnostic(exact, model, True)
        np.savez_compressed(out/'rho_diagnosis.npz', **{'original_'+k:v for k, v in oa.items()},
                            **{'modulo_'+k:v for k, v in ra.items()})
        # This fixed argument reduction is diagnostic, never a profile rescue.
        assert not original['original_1e9_gate_passed']
        reference = signal.resample_poly(exact, *plan['reference_resample'], axis=0, window=('kaiser', 8.6))
        sf.write(out/'reference64.wav', reference, 48000, subtype='FLOAT')
        row = dict(name=case['case']['name'], original_root_hz=root, common_root_hz=64,
                   original_ratio_check=original, reduced_argument_ratio_check=reduced,
                   reference=spectrum(reference, plan), generated=[])
        for seed in plan['seeds']:
            wavepath = out/f'DNA64_{seed}.wav'
            argv = list(map(str, [a.dna_probe, folder/'voice.model', wavepath, plan['render_seconds'],
                                 plan['common_root_hz']/root, 1, seed, 512]))
            done = subprocess.run(argv, cwd=repo, capture_output=True, timeout=180)
            (out/f'C_{seed}.log').write_bytes(done.stdout+done.stderr)
            assert done.returncode == 0
            wave, rate = sf.read(wavepath, always_2d=True)
            assert rate == 48000 and wave.shape == (384000, 2) and np.isfinite(wave).all()
            assert abs(wave).max()*.5 < .95
            row['generated'].append(dict(seed=seed, argv=argv, sha256=sha(wavepath), spectrum=spectrum(wave, plan)))
        r['cases'].append(row)
        orders = np.arange(1, len(oa['rho'])+1)
        axes[i, 0].semilogy(orders, np.maximum(oa['error'], 1e-18), label='original direct phase')
        axes[i, 0].semilogy(orders, np.maximum(ra['error'], 1e-18), label='modulo phase')
        axes[i, 0].axhline(1e-9, color='red', ls=':')
        axes[i, 0].set(title=row['name']+' / ratio diagnostic', xlabel='Acoustic harmonic', ylabel='Absolute rho difference')
        axes[i, 0].legend(fontsize=8)
        ref = np.array([v['power_LR'] for v in row['reference']['bands']]).mean(axis=1)
        gen = np.array([[v['power_LR'] for v in g['spectrum']['bands']] for g in row['generated']]).mean(axis=(0, 2))
        axes[i, 1].plot(np.arange(8), 10*np.log10(np.maximum(ref, 1e-30)), 'o-', label='short source @64Hz')
        axes[i, 1].plot(np.arange(8), 10*np.log10(np.maximum(gen, 1e-30)), 'o-', label='8s C, mean 3 seeds')
        axes[i, 1].set(xticks=np.arange(8), xticklabels=['28-120','120-400','400-1.2k','1.2-3k','3-6k','6-8k','8-10k','10-14k'],
                       ylabel='Band power dBFS', title='Descriptive; unequal durations / no gain matching')
        axes[i, 1].tick_params(axis='x', labelrotation=30)
        axes[i, 1].legend(fontsize=8)
    cross = []
    for generated in r['cases']:
        for reference in r['cases']:
            expected = np.array([v['power_LR'] for v in reference['reference']['bands']])
            differences = []
            correlations = []
            expected_corr = np.array([complex(*v['signed_complex_correlation']) for v in reference['reference']['bands']])
            for g in generated['generated']:
                actual = np.array([v['power_LR'] for v in g['spectrum']['bands']])
                differences.append((10*np.log10(np.maximum(actual, 1e-30)/np.maximum(expected, 1e-30))).tolist())
                actual_corr = np.array([complex(*v['signed_complex_correlation']) for v in g['spectrum']['bands']])
                correlations.append(abs(actual_corr-expected_corr).tolist())
            cross.append(dict(generated=generated['name'], reference=reference['name'],
                              band_LR_dB_errors_each_seed=differences,
                              band_complex_correlation_errors_each_seed=correlations,
                              mean_absolute_band_LR_error_dB=float(np.mean(abs(np.array(differences))))))
    r.update(result='descriptive_comparison_complete', cross_context=cross, models_changed=False,
             original_audit_ratio_gate_passed=False, generic_phase_qualified=False,
             physical_RPM_load=False, new_timbre_accepted=False, live_catalog_promoted=False)
    fig.savefig(a.out/'comparison.png', dpi=145)
    plt.close(fig)
except Exception as exc:
    r.update(result='failed', error=repr(exc))
    raise
finally:
    save(a.out/'report.json', r)
print(dict(result=r['result'], ratios=[(v['original_ratio_check'], v['reduced_argument_ratio_check']) for v in r['cases']],
           cross=[(v['generated'], v['reference'], v['mean_absolute_band_LR_error_dB']) for v in r.get('cross_context', [])]))
