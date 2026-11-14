"""Independent SciPy CSD/PSD and sparse C oracle for the fixed comparison outputs."""
import argparse
import os
from pathlib import Path
import shutil
import sys

p = argparse.ArgumentParser(description=__doc__)
for key in ('workspace', 'fit', 'comparison', 'out'):
    p.add_argument('--'+key, type=Path, required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(a.workspace/'tools/python_deps'))
for key in ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS'):
    os.environ[key] = '2'
import numpy as np
import soundfile as sf
from scipy import signal
from research_archive_v1 import load, save, sha
from local_voice_batch_v1.audit_kernels import rebuild, seeded_samples
from idle_texture_v1.profile import load as model_load

a.out.mkdir(parents=True, exist_ok=False)
r = dict(result='running', sources={}, inputs={}, cases=[])


def consume(path):
    r['inputs'][str(path)] = sha(path)
    return path


def spectrum(audio, expected, plan):
    kw = dict(fs=48000, window='hann', nperseg=2048, noverlap=1536, nfft=8192,
              detrend=False, return_onesided=True, scaling='density', axis=0)
    hz, psd = signal.welch(audio, **kw)
    # SciPy convention conj(first)*second; reversing R,L yields L*conj(R).
    _, csd = signal.csd(audio[:, 1], audio[:, 0], **kw)
    power_error = cross_error = 0.
    actual = []
    for (lo, hi), band in zip(plan['bands_hz'], expected['bands']):
        keep = (hz >= lo) & (hz < hi)
        pp = np.sum(psd[keep], axis=0)*(48000/8192)
        cross = np.sum(csd[keep])*(48000/8192)/np.sqrt(max(pp[0]*pp[1], 1e-60))
        power_error = max(power_error, float(abs(pp-band['power_LR']).max()))
        cross_error = max(cross_error, float(abs(cross-complex(*band['signed_complex_correlation']))))
        actual.append(pp)
    assert power_error < 1e-12 and cross_error < 1e-10
    return np.array(actual), dict(PSD_band_error_FS2=power_error, signed_complex_correlation_error=cross_error)


try:
    for name in ('tools/verify_F3_fifth_comparison_v1.py', 'tools/local_voice_batch_v1/audit_kernels.py',
                 'tools/idle_texture_v1/profile.py', 'tools/sustain_osc_v1/oracle.py', 'tools/research_archive_v1.py'):
        dest = a.out/'exact_sources'/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo/name, dest)
        r['sources'][name] = sha(repo/name)
    plan = load(consume(repo/'research/F3_fifth_compare_v1_plan.json'))
    report = load(consume(a.comparison/'report.json'))
    fit = load(consume(a.fit/'report.json'))
    assert report['result'] == 'descriptive_comparison_complete' and not report['original_audit_ratio_gate_passed']
    for name, digest in report['sources'].items():
        assert sha(repo/name) == digest == sha(a.comparison/'exact_sources'/name)
    for name, digest in report['inputs'].items():
        assert sha(consume(Path(name))) == digest
    indices = [0, 1, 239, 240, 255, 256, 511, 512, 4800, 11999, 47999, 95999, 191999, 383999]
    references, generated = [], []
    for row, source in zip(report['cases'], fit['cases']):
        folder = a.fit/row['name']
        model, root = model_load(consume(folder/'voice.model'))
        native, _ = sf.read(consume(folder/'native.wav'), always_2d=True)
        with np.load(consume(folder/'coordinates.npz')) as f:
            positions = f['source_seconds']
        exact = rebuild(native, source['case']['seconds'][0], positions, 14000)
        reference = signal.resample_poly(exact, 375, 512, axis=0, window=('kaiser', 8.6))
        saved, rate = sf.read(consume(a.comparison/row['name']/'reference64.wav'), always_2d=True)
        assert rate == 48000 and np.array_equal(reference.astype('float32').astype('float64'), saved)
        reference_power, reference_metrics = spectrum(reference, row['reference'], plan)
        references.append(reference_power)
        seed_metrics, powers = [], []
        for output in row['generated']:
            path = a.comparison/row['name']/f"DNA64_{output['seed']}.wav"
            assert sha(consume(path)) == output['sha256']
            wave, rate = sf.read(path, always_2d=True)
            assert rate == 48000 and wave.shape == (384000, 2)
            expected = seeded_samples(model, 64, output['seed'], indices)
            error = float(abs(wave[indices]-expected).max())
            assert error < 1e-7
            power, metrics = spectrum(wave, output['spectrum'], plan)
            powers.append(power)
            seed_metrics.append(dict(seed=output['seed'], sparse_C_error_FS=error, **metrics))
        generated.append(powers)
        r['cases'].append(dict(name=row['name'], reference_FLOAT_exact=True,
                               reference=reference_metrics, seeds=seed_metrics))
        save(a.out/'report.json', r)
    for i, powers in enumerate(generated):
        for j, reference in enumerate(references):
            differences = 10*np.log10(np.maximum(np.array(powers), 1e-30)/np.maximum(reference[None, :, :], 1e-30))
            saved = report['cross_context'][i*2+j]
            assert abs(differences-saved['band_LR_dB_errors_each_seed']).max() < 1e-8
            assert abs(float(np.mean(abs(differences)))-saved['mean_absolute_band_LR_error_dB']) < 1e-8
    for filename, count in [('C_files_sha256.json', 650), ('voice_files_sha256.json', 76)]:
        records = load(consume(a.workspace/'baselines/catalog_F3_v1/inputs'/filename))
        assert len(records) == count and all(sha(repo/name) == digest for name, digest in records.items())
    r.update(result='comparison_outputs_verified_ratio_gate_still_unresolved',
             generated_waves=6, sparse_samples_per_wave=14, cross_context_pairs=4,
             protected_C_H_exact=650, protected_voice_parameters_exact=76,
             original_ratio_gate_passed=False, hearing=False, live_promoted=False)
except Exception as exc:
    r.update(result='failed', error=repr(exc))
    raise
finally:
    save(a.out/'report.json', r)
print({k: r.get(k) for k in ('result', 'generated_waves', 'cases')})
