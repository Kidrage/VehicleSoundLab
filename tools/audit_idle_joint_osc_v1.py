"""Independent algebra, node-convolution and native sample checks for the diagnostic."""
import argparse
import math
import shutil
import sys
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
for key in ['workspace', 'fit', 'input', 'out']:
    p.add_argument('--'+key, type=Path, required=True)
a = p.parse_args()
sys.path.insert(0, str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal
from research_archive_v1 import load, save, sha
from idle_joint_osc_v1.analysis import observe

a.out.mkdir(parents=True, exist_ok=False)
shutil.copy2(__file__, a.out/'executed_auditor.py')
r = dict(result='running', fit_report_sha256=sha(a.fit/'report.json'),
         input_report_sha256=sha(a.input/'report.json'), observations=[], renders=[])
try:
    fit, report = load(a.fit/'report.json'), load(a.input/'report.json')
    assert report['result'] == 'diagnostic_joint_osc_audio_pending_audit'
    for source in fit['observations']:
        with np.load(a.fit/source['file']) as f:
            data = {k: f[k] for k in f.files}
        m = len(data['harmonics'])
        # Explicit outer products through a separate contraction, not the fitter.
        errors = {}
        for part in ['train', 'check']:
            c = data[part]
            real = np.concatenate([c.real, c.imag], axis=1)*data['row_scale']
            moment = np.einsum('ti,tj->ij', real, real, optimize=False)/len(real)
            errors[part] = float(abs(moment-data['moment' if part == 'train' else 'check_moment']).max())
            assert errors[part] < 2e-18
        block = np.zeros_like(data['moment'])
        for j in range(m):
            ids = [j, j+m]
            block[np.ix_(ids, ids)] = data['moment'][np.ix_(ids, ids)]
        assert np.array_equal(block, data['independent_moment'])
        for name in ['joint', 'independent']:
            target = data['moment' if name == 'joint' else 'independent_moment']
            factor = data[name+'_factor']
            error = float(np.linalg.norm(factor@factor.T-target)/np.linalg.norm(target))
            assert error < 3e-13
            errors[name+'_factor_relative'] = error
        for band, target in enumerate(fit['targets']):
            ids = np.flatnonzero(data['groups'] == band)
            ids = np.r_[ids, ids+m]
            assert abs(np.trace(data['moment'][np.ix_(ids, ids)])/2-target) < 1e-18
        check = data['check_moment']
        distances = {name+'_relative_distance': float(np.linalg.norm(data[key]-check)/np.linalg.norm(check))
                     for name, key in [('joint', 'moment'), ('independent', 'independent_moment')]}
        assert max(abs(distances[k]-source['check'][k]) for k in distances) < 1e-13
        r['observations'].append(dict(seed=source['seed'], errors=errors, check=distances))
    with np.load(a.fit/'source.npz') as f:
        model = {k: f[k] for k in f.files}
    # A declared known amplitude/phase observation, independent of the car recording.
    carrier = fit['spacing_hz']
    t = np.arange(144000)/48000
    phi = 2*np.pi*carrier*t+.2
    known_amplitudes = np.array([.4, .3, .2, .1])*np.exp(1j*np.array([.1, -.4, .7, -.2]))
    z = np.exp(1j*phi[:,None]*[2, 3, 5])
    known_errors = []
    for band, first in enumerate([40, 70, 140, 270]):
        known_harmonics = np.arange(first, first+4)
        x = np.real(np.exp(1j*phi[:,None]*known_harmonics)@known_amplitudes)
        measured, _ = observe(np.column_stack([x, x]), z, {'coefficients':np.zeros((13,4)).tolist()},
                              known_harmonics, np.full(4,band), model['native_kernel'])
        sos = signal.butter(4, [[1200,2200], [2200,4000], [4000,8000], [8000,14000]][band],
                            btype='bandpass', fs=48000, output='sos')
        _, transfer = signal.sosfreqz(sos, worN=known_harmonics*carrier, fs=48000)
        error = float(abs(measured-known_amplitudes*transfer).max())
        assert error < .002, (band, error)
        known_errors.append(error)
    r['known_fixed_multitone_demodulation_errors_FS'] = known_errors
    profile = load(a.workspace/'baselines/fixed_source_profiles_v1/evidence/trial1/F2_tailpipe/profile.json')
    for row in report['renders']:
        seed = row['seed']
        with np.load(a.input/row['traces']) as f:
            trace = {k: f[k] for k in f.files}
        frames = len(trace['phase'])
        for item in row['files'].values():
            path = a.input/item['file']
            assert sha(path) == item['sha256']
            y, rate = sf.read(path, always_2d=True)
            assert rate == 48000 and len(y) == frames and np.isfinite(y).all() and abs(y).max() < 1
        h = model['node_kernel']/np.linalg.norm(model['node_kernel'])
        warm = len(h)-1
        node_count = len(trace['whitened_nodes'])
        rng = np.random.Generator(np.random.PCG64(seed ^ 0x682D7439A851))
        raw = rng.standard_normal((node_count+warm, 2*m))
        node_ids = np.unique(np.r_[0, 1, 2, 170, 171, node_count-2, node_count-1,
                                  np.linspace(0, node_count-1, 33).astype(int)])
        direct = np.array([h @ raw[j:j+len(h)][::-1] for j in node_ids])
        node_error = float(abs(direct-trace['whitened_nodes'][node_ids]).max())
        assert node_error < 1e-13
        coefficient_errors = {}
        for name in ['joint', 'independent']:
            factor = model[name+'_factor']
            reference = np.einsum('tj,ij->ti', trace['whitened_nodes'], factor, optimize=False)
            error = float(abs(reference-trace[name+'_nodes']).max())
            assert error < 1e-14
            coefficient_errors[name] = error
        # Every interpolation phase, both ends, block/node boundaries and all 24 seconds.
        ids = np.unique(np.r_[np.arange(384), np.arange(frames-384, frames),
                              np.arange(1915, 1926), np.arange(48000, frames, 48000),
                              np.linspace(0, frames-1, 4096).astype(int)])
        node_index, fraction = np.divmod(ids, 96)
        u = fraction/96
        w = np.column_stack([-.5*u+u*u-.5*u**3, 1-2.5*u*u+1.5*u**3,
                             .5*u+2*u*u-1.5*u**3, -.5*u*u+.5*u**3])
        autocorrelation = signal.correlate(h, h, mode='full', method='direct')[len(h)-1:]
        covariance = autocorrelation[abs(np.arange(4)[:, None]-np.arange(4))]
        variance = np.array([float(x@covariance@x) for x in w])
        assert variance.min() > 0
        w /= np.sqrt(variance[:, None])
        rotation = np.exp(1j*trace['phase'][ids, None]*model['harmonics'])
        waveform_errors = {}
        for name in ['joint', 'independent']:
            data = trace[name+'_nodes']
            z = data[:, :m]+1j*data[:, m:]
            interpolated = np.einsum('tk,tkm->tm', w, z[node_index[:, None]+np.arange(4)])
            oscillator = (interpolated*rotation).real
            oracle = np.zeros((len(ids), 2))
            for band in range(4):
                y = oscillator[:, model['groups'] == band].sum(axis=1)*np.sqrt(trace['q'][ids, band])
                oracle += y[:, None]*[1., profile['kernels'][band+2]['right_over_left']]
            actual, _ = sf.read(a.input/row['files'][name+'_upper']['file'], always_2d=True)
            error = float(abs(actual[ids]-oracle).max())
            assert error < 1e-8
            waveform_errors[name] = error
            lower, _ = sf.read(a.input/row['files']['lower']['file'], always_2d=True)
            main, _ = sf.read(a.input/row['files']['main']['file'], always_2d=True)
            detail, _ = sf.read(a.input/row['files'][name+'_detail']['file'], always_2d=True)
            mix, _ = sf.read(a.input/row['files'][name+'_mix']['file'], always_2d=True)
            assert abs(detail-lower-actual).max() < 3e-8
            assert abs(mix-main-detail).max() < 3e-8
        r['renders'].append(dict(seed=seed, direct_node_count=len(node_ids), all_node_coordinates=2*m,
                                native_sample_count=len(ids), direct_filter_error=node_error,
                                all_coefficient_nodes_errors=coefficient_errors,
                                sampled_native_waveform_errors=waveform_errors))
        print(dict(stage='audited', seed=seed, sample_errors=waveform_errors), flush=True)
    # Technical correctness does not reverse the failed independent CHECK comparison.
    r.update(result='passed', cross_portion_improvement=False, runtime_changed=False,
             native_waveform_check_is_sampled=True, all_mixing_relations_checked=True,
             listening_accepted=False, scope='Diagnostic renderer only, not perceptual or engine-clock qualification')
except Exception as exc:
    r.update(result='failed', error=repr(exc))
    raise
finally:
    save(a.out/'report.json', r)
