"""Independently audit retained/rejected carriers, native samples and C spectra."""
import argparse
import math
import os
from pathlib import Path
import shutil
import sys

p = argparse.ArgumentParser(description=__doc__)
for key in ('workspace', 'fit', 'out'):
    p.add_argument('--'+key, type=Path, required=True)
p.add_argument('--stereo', type=Path)
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
from research_archive_v1 import load, save, sha
from stationary_bridge_v1.diagnose import carrier_diagnostics

a.out.mkdir(parents=True, exist_ok=False)
r = dict(result='running', inputs={}, sources={}, cases=[])


def consume(path):
    r['inputs'][str(path)] = sha(path)
    return path


def band_power(audio, bands):
    # Direct frame loop, no scipy Welch or production matrices helper.
    size, hop = 2048, 512
    window = .5-.5*np.cos(2*np.pi*np.arange(size)/size)
    total = np.zeros((size//2+1, 2))
    count = 0
    for start in range(0, len(audio)-size+1, hop):
        z = np.fft.rfft(audio[start:start+size]*window[:, None], axis=0)
        power = abs(z)**2/(48000*math.fsum(window*window))
        power[1:-1] *= 2
        total += power
        count += 1
    total /= count
    hz = np.arange(size//2+1)*48000/size
    return np.array([[math.fsum(total[(hz >= lo) & (hz < hi), c])*48000/size
                      for c in range(2)] for lo, hi in bands])


def band_cross(audio, bands):
    size, hop = 2048, 512
    window = .5-.5*np.cos(2*np.pi*np.arange(size)/size)
    total = np.zeros(size//2+1, complex)
    count = 0
    for start in range(0, len(audio)-size+1, hop):
        z = np.fft.rfft(audio[start:start+size]*window[:, None], axis=0)
        cross = z[:, 0].conj()*z[:, 1]/(48000*math.fsum(window*window))
        cross[1:-1] *= 2
        total += cross
        count += 1
    total /= count
    hz = np.arange(size//2+1)*48000/size
    return np.array([sum(total[(hz >= lo) & (hz < hi)])*48000/size for lo, hi in bands])


try:
    for name in ('tools/audit_E_decel_source_v1.py', 'tools/stationary_bridge_v1/diagnose.py',
                 'tools/exterior_clock_v1/warp.py', 'tools/research_archive_v1.py'):
        target = a.out/'exact_sources'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo/name, target)
        r['sources'][name] = sha(repo/name)
    # Independent FFT/power formula control before real source/model reads.
    t = np.arange(8192)/48000
    known = np.column_stack([.2*np.cos(2*np.pi*1500*t), .12*np.cos(2*np.pi*1500*t+.4)])
    power = band_power(known, [(1400, 1600)])
    known_error = float(abs(power-np.array([[.2**2/2, .12**2/2]])).max())
    assert known_error < 1e-14
    r['known_power_before_source_FS2'] = known_error
    known_cross = band_cross(known, [(1400, 1600)])[0]
    assert abs(known_cross-.2*.12/2*np.exp(.4j)) < 1e-14
    r['known_signed_cross_before_source_FS2'] = float(abs(known_cross-.2*.12/2*np.exp(.4j)))
    fit = load(consume(a.fit/'report.json'))
    assert fit['result'] == 'fixed_centers_checked'
    assert fit['known_controls_before_source']['result'] == 'pass'
    for name, digest in fit['sources'].items():
        assert sha(repo/name) == digest == sha(a.fit/'exact_sources'/name)
    plan = load(consume(repo/'research/E_decel_source_v1_plan.json'))
    registry = load(consume(a.workspace/'references/segments_v1.json'))
    entry = registry['sources']['E']
    for key in ('raw', 'master'):
        assert sha(consume(a.workspace/entry[key])) == entry[key+'_sha256']
    baseline = a.workspace/'baselines/catalog_bridge_v1/inputs'
    for key, count in [('C_files_sha256.json', 643), ('voice_files_sha256.json', 72)]:
        frozen = load(consume(baseline/key))
        assert len(frozen) == count and all(sha(repo/name) == digest for name, digest in frozen.items())
    r['existing_C_H_exact'] = 643
    r['existing_voice_parameters_exact'] = 72
    clock = load(consume(a.fit/'consumed_clock.json'))['selected_rows']
    clock_times = np.array([v['seconds'] for v in clock])
    clock_hz = np.array([v['root_hz'] for v in clock])
    # A second scalar prefix, avoiding the producer's numpy cumulative sum.
    prefix = [0.]
    terms = []
    for i in range(1, len(clock)):
        terms.append((clock_times[i]-clock_times[i-1])*(clock_hz[i]+clock_hz[i-1])/2)
        prefix.append(math.fsum(terms))
    fig, axes = plt.subplots(len(plan['cases']), 2, figsize=(11, 6.5), layout='constrained')
    for i, case in enumerate(plan['cases']):
        folder = a.fit/case['name']
        extraction = load(consume(folder/'extraction.json'))
        normalized, rate = sf.read(consume(folder/'normalized.wav'), always_2d=True)
        assert rate == 48000
        result = carrier_diagnostics(normalized)
        for order in ('3', '7'):
            difference = float(abs(np.array(result['orders'][order]['coherence'])-
                                   extraction['heldout_coherence'][order]).max())
            assert difference < 1e-7
        start, stop = extraction['aperture_source_seconds']
        center_cycle = float(np.interp(case['center_seconds'], clock_times, prefix))
        actual = np.interp([start, stop], clock_times, prefix)
        aperture_error = float(abs(actual-center_cycle-np.array([-.5, .5])*plan['aperture_cycles']).max())
        assert aperture_error < 1e-10
        coordinates = consume(folder/'coordinates.npz')
        with np.load(coordinates) as z:
            where = z['source_seconds']
        assert len(where) == len(normalized) and np.all(np.diff(where) > 0)
        inferred = 1/(1024*np.diff(where))
        assert abs(float(np.median(inferred))-extraction['root_hz']) < 1e-12
        first, last = [round(t*48000) for t in extraction['phase']['source_seconds']]
        with sf.SoundFile(a.workspace/entry['master']) as stream:
            stream.seek(first)
            native = stream.read(last-first, dtype='float64', always_2d=True)
        saved, rate = sf.read(consume(folder/'raw_source.wav'), always_2d=True)
        assert rate == 48000 and np.array_equal(saved, native)
        gate = extraction['statistics']['observation_frames'] >= plan['gates']['minimum_observations'] and min(
            v for values in extraction['heldout_coherence'].values() for v in values) > plan['gates']['heldout_carrier_coherence']
        retained = any(v['case']['name'] == case['name'] for v in fit['accepted'])
        assert retained == gate
        checks = []
        if retained:
            model = load(consume(folder/'model.json'))
            reference, rate = sf.read(consume(folder/'reference.wav'), always_2d=True)
            bands = [v['hz'] for v in model['renders'][0]['metrics']]
            reference_power = band_power(reference, bands)
            for render in model['renders']:
                mixed, rate = sf.read(consume(folder/f"candidate_{render['seed']}.wav"), always_2d=True)
                measured = 10*np.log10(band_power(mixed[plan['crop_frames']:], bands)/reference_power)
                expected = np.array([v['power_delta_db'] for v in render['metrics']])
                difference = float(abs(measured-expected).max())
                # File storage is FLOAT32; the producer fitted FLOAT64 arrays.
                assert difference < 2e-5
                checks.append(dict(seed=render['seed'], maximum_spectral_difference_db=difference))
        else:
            assert not (folder/'voice.model').exists() and not list(folder.glob('candidate_*.wav'))
        result.update(name=case['name'], root_hz=extraction['root_hz'], retained=retained,
                      aperture_cycle_error=aperture_error, native_source_samples_exact=True,
                      independent_C_spectra=checks)
        r['cases'].append(result)
        for order, values in result['orders'].items():
            normalized_time = np.array(values['centers'])/48000
            axes[i, 0].plot(normalized_time, np.array(values['magnitude'])[:, 0], label='line '+order)
            axes[i, 1].plot(normalized_time, np.array(values['phase_radians'])[:, 0], label='line '+order)
        axes[i, 0].set(title=case['name']+(' | retained' if retained else ' | excluded'),
                       xlabel='Normalized seconds', ylabel='Left carrier amplitude')
        axes[i, 1].set(xlabel='Normalized seconds', ylabel='Left relative phase, radians')
        for axis in axes[i]:
            axis.grid(alpha=.2)
            axis.legend(fontsize=8)
    fig.savefig(a.out/'carriers.png', dpi=130)
    plt.close(fig)
    if a.stereo:
        stereo = load(consume(a.stereo/'report.json'))
        assert stereo['result'] == 'stereo_extension_rendered' and stereo['same_main'] and stereo['same_withdrawal']
        for name, digest in stereo['sources'].items():
            assert sha(repo/name) == digest == sha(a.stereo/'exact_sources'/name)
        for name, digest in stereo['inputs'].items():
            assert sha(consume(Path(name))) == digest
        r['stereo_certificate_checks'] = []
        for model in stereo['models']:
            coefficient = np.array(model['a'])
            n = 2*len(coefficient)
            f = np.zeros((n, n)); f[:2] = coefficient.transpose(1, 0, 2).reshape(2, n)
            f[2:, :-2] = np.eye(n-2)
            cert = np.array(model['certificate'])
            margin = cert-f.T@cert@f
            minimum = float(np.linalg.eigvalsh((margin+margin.T)/2).min())
            assert np.linalg.eigvalsh(cert).min() > 0 and minimum > 0
            r['stereo_certificate_checks'].append(dict(band=model['band_hz'], minimum_margin=minimum))
        retained = fit['accepted'][0]
        reference, rate = sf.read(consume(a.fit/retained['case']['name']/'reference.wav'), always_2d=True)
        bands = [v['hz'] for v in stereo['trials'][0]['short_mixed_vs_reference']]
        reference_power = band_power(reference, bands)
        reference_cross = band_cross(reference, bands)
        reference_coherence = reference_cross/np.sqrt(np.prod(reference_power, axis=1))
        r['stereo_trials'] = []
        for trial in stereo['trials']:
            mixed, rate = sf.read(consume(a.stereo/f"candidate_{trial['seed']}.wav"), always_2d=True)
            power = band_power(mixed[24000:], bands)
            cross = band_cross(mixed[24000:], bands)
            coherence = cross/np.sqrt(np.prod(power, axis=1))
            db = 10*np.log10(power/reference_power)
            dc = abs(coherence-reference_coherence)
            expected = trial['short_mixed_vs_reference']
            power_error = float(abs(db-np.array([v['power_delta_db'] for v in expected])).max())
            cross_error = float(abs(dc-np.array([v['complex_coherence_error'] for v in expected])).max())
            assert power_error < 2e-5 and cross_error < 2e-6
            r['stereo_trials'].append(dict(seed=trial['seed'], power_error_db=power_error,
                                           complex_coherence_error_difference=cross_error))
    r.update(result='passed', scope='Input/sample/aperture/carrier/PSD arithmetic; no physical state or listening acceptance')
except Exception as exc:
    r.update(result='failed', error=repr(exc))
    raise
finally:
    save(a.out/'report.json', r)
