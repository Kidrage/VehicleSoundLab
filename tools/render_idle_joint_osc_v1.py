"""Render declared joint-vs-own-block comparison despite failed source transfer.

This is a diagnostic, not an adopted idle improvement. Do not sweep the failed fit.
"""
import argparse
import shutil
import sys
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
for key in ['workspace', 'fit', 'out']:
    p.add_argument('--'+key, type=Path, required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal
from research_archive_v1 import load, save, sha
from idle_joint_osc_v1.synthesis import white_nodes, render
from idle_phase_recipe_v1.phase import spline, phasors
from idle_phase_recipe_v1.render2 import phase_audio, noise
from idle_phase_difference_v1.features import matrix
from idle_positive_power_v1.model import predict

a.out.mkdir(parents=True, exist_ok=False)
r = dict(result='running', sources={}, inputs={}, renders=[], diagnostic_only=True)


def track(path):
    r['inputs'][str(path)] = sha(path)
    return path


try:
    names = ['tools/render_idle_joint_osc_v1.py', 'tools/idle_joint_osc_v1/synthesis.py',
             'tools/idle_joint_osc_v1/kernel.py', 'tools/research_archive_v1.py',
             'research/idle_joint_osc_v1_plan.json', 'tools/idle_phase_recipe_v1/phase.py',
             'tools/idle_phase_recipe_v1/render2.py', 'tools/idle_phase_difference_v1/features.py',
             'tools/idle_positive_power_v1/model.py', 'tools/idle_modal_v1/modal.py']
    for name in names:
        dest = a.out/'exact_sources'/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo/name, dest)
        r['sources'][name] = sha(repo/name)
    fit = load(track(a.fit/'report.json'))
    assert fit['result'] == 'joint_osc_moment_fit_retained_pending_generation'
    with np.load(track(a.fit/'source.npz')) as f:
        model = {key: f[key] for key in f.files}
    parents = a.workspace/'baselines'
    phase_root = parents/'idle_phase_recipe_v1/evidence/render2'
    phase_model = load(track(phase_root/'model.json'))
    profile = load(track(parents/'fixed_source_profiles_v1/evidence/trial1/F2_tailpipe/profile.json'))
    law = fit['law']
    frames = 24 * 48000
    for seed in [149921, 277139, 381611]:
        with np.load(track(phase_root/f'motion_{seed}.npz')) as f:
            values = f['coordinate_nodes']
        motion = spline(phase_model, values)
        t = np.arange(frames)/48000
        z = phasors(phase_model, motion, t)
        phase = np.unwrap(np.angle(z[:, 1] * z[:, 0].conj()))
        q = predict(law, matrix(z, hop=1, trim=0))
        instantaneous = np.diff(phase)*48000/(2*np.pi)
        _, main = phase_audio(profile, phase_model, motion, frames, 48000)
        lower = np.zeros_like(main)
        for band in range(2):
            kernel = profile['kernels'][band]
            count = frames+profile['warmup_frames']
            white = noise(seed, band, count, 'gaussian')
            y = signal.oaconvolve(white, kernel['taps'])[profile['warmup_frames']:count]*kernel['gain']
            lower += y[:, None]*[1., kernel['right_over_left']]
        source, white = white_nodes(model['node_kernel'], seed, 24, 2*len(model['harmonics']))
        upper, nodes = render(model, phase, q, profile, source)
        old_path = track(phase_root/f'related_detail_{seed}.wav')
        old_detail, rate = sf.read(old_path, frames=frames, always_2d=True)
        assert rate == 48000
        buses = dict(main=main, lower=lower, old_detail=old_detail, old_mix=main+old_detail)
        for name, y in upper.items():
            buses[name+'_upper'] = y
            buses[name+'_detail'] = lower+y
            buses[name+'_mix'] = main+lower+y
        row = dict(seed=seed, files={}, coordinate_hz_range=[float(instantaneous.min()), float(instantaneous.max())],
                   highest_instantaneous_carrier_hz=float(instantaneous.max()*model['harmonics'][-1]))
        for name, y in buses.items():
            if not np.isfinite(y).all() or np.max(abs(y)) >= 1:
                raise ValueError((seed, name, 'Nonfinite/overload; no peak normalization'))
            path = a.out/f'{name}_{seed}.wav'
            sf.write(path, y, 48000, subtype='FLOAT')
            row['files'][name] = dict(file=path.name, sha256=sha(path), peak=float(abs(y).max()),
                                      rms=float(np.sqrt(np.mean(y*y))))
        traces = a.out/f'traces_{seed}.npz'
        np.savez_compressed(traces, phase=phase, q=q, whitened_nodes=source,
                            joint_nodes=nodes['joint'], independent_nodes=nodes['independent'])
        row.update(traces=traces.name, traces_sha256=sha(traces))
        before, _ = sf.read(track(phase_root/f'relation_full_{seed}.wav'), frames=frames, always_2d=True)
        reconstructed, _ = sf.read(a.out/row['files']['old_mix']['file'], always_2d=True)
        row['old_mix_maximum_error_FS'] = float(abs(before-reconstructed).max())
        assert row['old_mix_maximum_error_FS'] <= 3e-8
        r['renders'].append(row)
        save(a.out/'report.json', r)
        print(dict(stage='rendered', seed=seed, max_peak=max(v['peak'] for v in row['files'].values())), flush=True)
    r.update(result='diagnostic_joint_osc_audio_pending_audit', seconds=24, sample_rate=48000,
             fit_check=fit['observations'][0]['check'],
             transfer_improved=False, source_trajectory_replayed=False, runtime_changed=False,
             physical_clock_identified=False, listening_accepted=False,
             expected_cell_variances_equal=True, realized_PSD_or_RMS_matched=False)
except Exception as exc:
    r.update(result='failed', error=repr(exc))
    raise
finally:
    save(a.out/'report.json', r)
print(dict(result=r['result'], renders=len(r['renders'])), flush=True)
