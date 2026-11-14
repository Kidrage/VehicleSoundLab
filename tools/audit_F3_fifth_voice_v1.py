"""Independent native/coordinate/moment/C audit of the two fixed fifth-gear cases."""
import argparse
import math
import os
from pathlib import Path
import shutil
import sys

p = argparse.ArgumentParser(description=__doc__)
for key in ('workspace', 'fit', 'out'):
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
from local_voice_batch_v1.audit_kernels import peaks, path, coherence, rebuild, coordinates, seeded_samples
from idle_texture_v1.profile import load as model_load
from research_archive_v1 import load, save, sha

a.out.mkdir(parents=True, exist_ok=False)
r = dict(result='running', sources={}, inputs={}, cases=[])


def consume(path):
    r['inputs'][str(path)] = sha(path)
    return path


try:
    for name in ('tools/audit_F3_fifth_voice_v1.py', 'tools/local_voice_batch_v1/audit_kernels.py',
                 'tools/idle_texture_v1/profile.py', 'tools/sustain_osc_v1/oracle.py', 'tools/research_archive_v1.py'):
        dest = a.out/'exact_sources'/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo/name, dest)
        r['sources'][name] = sha(repo/name)
    # Known exact Fourier bin and signed L*conj(R) before the real source read.
    t = np.arange(16384)/48000
    win = .5-.5*np.cos(2*np.pi*np.arange(16384)/16384)
    tone = np.column_stack([.2*np.cos(2*np.pi*375*t), .12*np.cos(2*np.pi*375*t+.4)])
    z = np.fft.rfft(tone*win[:, None], axis=0)
    power = abs(z)**2/(48000*math.fsum(win*win))
    cross = z[:, 0]*z[:, 1].conj()/(48000*math.fsum(win*win))
    power[1:-1] *= 2
    cross[1:-1] *= 2
    error = max(abs(math.fsum(power[:, c])*48000/16384-amp**2/2) for c, amp in enumerate((.2, .12)))
    assert error < 1e-14
    assert abs(sum(cross)*48000/16384-.2*.12/2*np.exp(-.4j)) < 1e-14
    ct = np.arange(16384)/1024
    known = np.column_stack([np.cos(2*np.pi*3*ct), .8*np.cos(2*np.pi*3*ct+.2)])
    assert np.max(abs(coherence(known, 3)-1)) < 1e-14
    r['known_before_source'] = dict(power_error_FS2=error, signed_cross='L*conj(R)', direct_carrier=True)
    fit = load(consume(a.fit/'report.json'))
    plan = load(consume(repo/'research/F3_fifth_voice_v1_plan.json'))
    assert fit['result'] == 'fixed_F3_fifth_local_cases_checked'
    assert fit['qualified'] == 2 and fit['excluded'] == 0
    assert fit['export_protocol'] == 'vsl.sound-dna-raw-export/1'
    for name, digest in fit['sources'].items():
        assert sha(repo/name) == digest == sha(a.fit/'exact_sources'/name)
    for name, digest in fit['inputs'].items():
        assert sha(consume(Path(name))) == digest
    registry = load(consume(a.workspace/'references/segments_v1.json'))
    assert sha(repo/'references/segments_v1.json') == sha(a.workspace/'references/segments_v1.json')
    source = registry['sources']['F3']
    for key in ('raw', 'master'):
        assert sha(consume(a.workspace/source[key])) == source[key+'_sha256']
    window = .5-.5*np.cos(2*np.pi*np.arange(3840)/3840)
    all_hz = np.arange(8193)*48000/16384
    bands = ((28, 120), (120, 400), (400, 1200), (1200, 3000), (3000, 8000), (8000, 16000))
    fig, axes = plt.subplots(2, 2, figsize=(11, 6), layout='constrained')
    total = 0
    for i, case in enumerate(plan['cases']):
        folder = a.fit/case['name']
        row = fit['cases'][i]
        assert row == load(consume(folder/'result.json'))
        assert row['case'] == case
        segment = registry['segments'][case['segment']]
        assert segment['source'] == 'F3' and case['use'] in segment['allowed_uses']
        with sf.SoundFile(a.workspace/source['master']) as stream:
            assert stream.channels == 2 and stream.samplerate == 48000 and stream.subtype == 'FLOAT'
            stream.seek(round(case['seconds'][0]*48000))
            native = stream.read(round((case['seconds'][1]-case['seconds'][0])*48000), always_2d=True, dtype='float64')
        saved, rate = sf.read(consume(folder/'native.wav'), always_2d=True)
        assert rate == 48000 and np.array_equal(native, saved)
        with np.load(consume(folder/'observed.npz')) as f:
            observed = {k: f[k] for k in f.files}
        times, hz = observed['seconds'], observed['hz']
        nodes, all_peaks = [], []
        maximum_power = maximum_cross = maximum_band = 0.
        for j, start in enumerate(range(0, len(native)-3840+1, 240)):
            assert abs(times[j]-(case['seconds'][0]+(start+1920)/48000)) < 1e-12
            z = np.fft.rfft(native[start:start+3840]*window[:, None], 16384, axis=0)
            power = abs(z)**2/(48000*math.fsum(window*window))
            power[1:-1] *= 2
            cross = z[:, 0]*z[:, 1].conj()/(48000*math.fsum(window*window))
            cross[1:-1] *= 2
            low = power[:len(hz)].mean(axis=1)
            maximum_power = max(maximum_power, float(abs(low-observed['power_low'][:, j]).max()))
            for b, (bottom, top) in enumerate(bands):
                keep = (all_hz >= bottom) & (all_hz < top)
                values = np.array([math.fsum(power[keep, c])*48000/16384 for c in (0, 1)])
                maximum_band = max(maximum_band, float(abs(values-observed['power_LR'][:, b, j]).max()))
                maximum_cross = max(maximum_cross, float(abs(sum(cross[keep])*48000/16384-observed['cross_LR'][b, j])))
            found = peaks(hz, low)
            all_peaks.append(found)
            n = []
            for f, prominence in found:
                root = f/5
                if not 20 <= root <= 90:
                    continue
                support = []
                for multiple in (2, 3, 7):
                    distance, prom = min((abs(v-multiple*root), q) for v, q in found)
                    support.append(min(prom, 40)/40 if distance <= max(6, .025*multiple*root) else 0.)
                n.append(dict(root=root, score=min(prominence, 40)/40+sum(support)))
            nodes.append(n)
        assert len(nodes) == len(times) == len(row['family']['rows']) == 185
        assert max(maximum_power, maximum_band, maximum_cross) < 1e-12
        anchor_index = min(range(len(times)), key=lambda j: abs(times[j]-case['anchor_seconds']))
        candidates = sorted([(v, q) for v, q in all_peaks[anchor_index] if 100 <= v <= 450], key=lambda pair: (-pair[1], pair[0]))
        assert anchor_index == row['anchor']['frame_index']
        assert abs(candidates[0][0]/5-row['anchor']['root_hz']) < 1e-10
        trace = path(nodes, times, candidates[0][0]/5, 32)
        root_error = max(abs(nodes[j][k]['root']-expected['root_hz']) for j, (k, expected) in enumerate(zip(trace, row['family']['rows'])))
        assert root_error < 1e-10
        with np.load(consume(folder/'coordinates.npz')) as f:
            positions = f['source_seconds']
        recomputed_positions, cutoff, root = coordinates(native, case['seconds'][0], row['family']['rows'], case['center_seconds'], plan)
        coordinate_error = float(abs(positions-recomputed_positions).max())
        assert coordinate_error < 1e-10
        assert abs(cutoff-row['extraction']['phase']['source_cutoff_hz']) < 1e-8
        assert abs(root-row['extraction']['root_hz']) < 1e-5
        normalized, rate = sf.read(consume(folder/'normalized.wav'), always_2d=True)
        exact = rebuild(native, case['seconds'][0], positions, cutoff)
        assert rate == 48000 and np.array_equal(exact.astype('float32').astype('float64'), normalized)
        coh = {str(order): coherence(exact, order).tolist() for order in (3, 7)}
        coherence_error = max(abs(x-y) for order in coh for x, y in zip(coh[order], row['extraction']['heldout_coherence'][order]))
        assert coherence_error < 1e-10
        observations = len(range(0, len(exact)-4096+1, 256))
        qualified = observations >= 32 and min(v for values in coh.values() for v in values) > .8
        assert observations == row['observations'] and qualified == row['qualified']
        result = dict(name=case['name'], frames=len(nodes), direct_power_error=maximum_power,
                      direct_band_error=maximum_band, direct_cross_error=maximum_cross,
                      path_root_error_hz=root_error, inverse_coordinate_error_seconds=coordinate_error,
                      normalized_FLOAT_exact=True, direct_carrier_error=coherence_error,
                      heldout_coherence=coh, qualified=qualified)
        if qualified:
            model, model_root = model_load(consume(folder/'voice.model'))
            assert model_root == row['extraction']['root_hz']
            h, k = model['basis'].shape[:2]
            w = .5-.5*np.cos(2*np.pi*np.arange(4096)/4096)
            kernel = np.exp(-2j*np.pi*np.arange(1, h+1)[:, None]*np.arange(4096)[None, :]/1024)*w[None, :]*2/math.fsum(w)
            samples = []
            for start in range(0, len(exact)-4096+1, 256):
                z = kernel@exact[start:start+4096]*np.exp(-2j*np.pi*np.arange(1, h+1)*start/1024)[:, None]
                samples.append(np.column_stack([z[:, 0].real, z[:, 0].imag, z[:, 1].real, z[:, 1].imag]).ravel())
            values = np.array(samples)
            centered = values-values.mean(axis=0)
            flat = model['basis'].transpose(1, 0, 2).reshape(k, -1)
            mean_error = float(abs(values.mean(axis=0).reshape(h, 4)-model['mean']).max())
            assert mean_error < 1e-10
            scores = (centered@flat.T)/np.sum(flat*flat, axis=1)[None, :]
            rho = np.clip(np.sum(scores[1:]*scores[:-1], axis=0)/np.sum(scores[:-1]**2, axis=0), -.95, .95)
            assert abs(rho-model['rho']).max() < 1e-9
            residual = (centered-scores@flat).reshape(-1, h, 4)
            cov = np.einsum('nhc,nhd->hcd', residual, residual)/(len(values)-1)
            restored = np.einsum('hcj,hdj->hcd', model['root'], model['root'])
            cov_error = float(abs(cov-restored).max())
            residual_rho = np.clip(np.sum(residual[1:]*residual[:-1], axis=(0, 2))/np.maximum(np.sum(residual[:-1]**2, axis=(0, 2)), 1e-30), -.95, .95)
            rho_errors = abs(residual_rho-model['residual_rho'])
            rho_denominator = np.sum(residual[:-1]**2, axis=(0, 2))
            worst_rho = int(np.argmax(rho_errors))
            # Preserve the original audit1 absolute ratio gate as a reported
            # failure. Tiny high-order residuals make the quotient sensitive
            # to direct-demodulation/SVD roundoff; do not relabel it passed.
            rho_check = dict(absolute_gate=1e-9, absolute_gate_passed=bool(rho_errors.max() < 1e-9),
                             maximum_error=float(rho_errors.max()), order=worst_rho+1,
                             residual_sum_squares_at_maximum=float(rho_denominator[worst_rho]),
                             failures=int(np.sum(rho_errors >= 1e-9)),
                             interpretation='Ratio audit remains unresolved; covariance and C output checks are separate. No source fit/gate changed.')
            assert cov_error < 1e-10
            indices = [0, 1, 239, 240, 255, 256, 511, 512, 4800, 11999, 47999, 95999, 191999, 383999]
            errors, waves = [], []
            for seed in plan['seeds']:
                wave, rate = sf.read(consume(folder/f'DNA_{seed}.wav'), always_2d=True)
                expected = seeded_samples(model, model_root, seed, indices)
                error = float(abs(wave[indices]-expected).max())
                assert wave.shape == (384000, 2) and rate == 48000 and error < 1e-7
                assert np.isfinite(wave).all() and abs(wave).max()*.5 < .95
                errors.append(error)
                waves.append(wave)
            assert all(not np.array_equal(x, y) for j, x in enumerate(waves) for y in waves[j+1:])
            result.update(model_mean_error=mean_error, residual_covariance_error=cov_error,
                          residual_rho_check=rho_check, seeded_C_sparse_sample_errors_FS=errors,
                          three_seeds_distinct=True)
        else:
            assert not (folder/'voice.model').exists() and not list(folder.glob('DNA_*.wav'))
        r['cases'].append(result)
        total += len(nodes)
        db = 10*np.log10(np.maximum(observed['power_low'], 1e-30))
        axes[i, 0].pcolormesh(times, hz, db, shading='auto', vmin=db.max()-50, vmax=db.max(), cmap='magma', rasterized=True)
        axes[i, 0].plot(times, [v['reference_hz'] for v in row['family']['rows']], color='cyan', lw=.8)
        axes[i, 0].set(title=case['name'], ylabel='Observed Hz', ylim=(35, 650))
        for order in (3, 7):
            axes[i, 1].plot((0, 1), coh[str(order)], 'o-', label=f'order{order}')
        axes[i, 1].axhline(.8, color='red', ls=':')
        axes[i, 1].set(ylim=(0, 1.05), xticks=(0, 1), xticklabels=('L', 'R'), ylabel='Carrier coherence')
        axes[i, 1].legend()
        save(a.out/'report.json', r)
    assert total == 370
    for filename, count in [('C_files_sha256.json', 650), ('voice_files_sha256.json', 76)]:
        records = load(consume(a.workspace/'baselines/catalog_F3_v1/inputs'/filename))
        assert len(records) == count and all(sha(repo/n) == digest for n, digest in records.items())
    fig.savefig(a.out/'diagnostic.png', dpi=140)
    plt.close(fig)
    rho_passed = all(v.get('residual_rho_check', {}).get('absolute_gate_passed', True) for v in r['cases'])
    r.update(result='passed' if rho_passed else 'audit_complete_with_unresolved_residual_rho_ratio',
             residual_rho_absolute_gate_passed=rho_passed,
             frames_checked=total, protected_C_H_exact=650, protected_voice_parameters_exact=76,
             source_gates_unchanged=True, human_hearing=False, physical_RPM_or_load=False,
             runtime_changed=False, generic_phase_qualification=False)
except Exception as exc:
    r.update(result='failed', error=repr(exc))
    raise
finally:
    save(a.out/'report.json', r)
print({k: r.get(k) for k in ('result', 'frames_checked', 'cases')})
