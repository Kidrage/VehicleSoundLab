"""Observe every fixed F3 acceleration tile without exporting a synthesis profile."""
import argparse
import json
from pathlib import Path
import shutil
import sys

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(a.workspace / 'tools' / x) for x in ('ipm_deps', 'qp_deps', 'python_deps')]
import numpy as np
from drive_evidence_v1.sources import read, sha
from accel_material_v1.features import compare
from accel_material_v1.checks import controls


def save(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


a.out.mkdir(parents=True, exist_ok=False)
r = dict(schema='vsl.acceleration-material/1', result='running', sources={}, observations=[],
         synthesis_profile_exported=False, RPM_measured=False, runtime_changed=False)
try:
    plan_path = repo / 'research/accel_material_v1_plan.json'
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    assert plan['tile_seconds'] == plan['hop_seconds'] == .25
    for path in [Path(__file__), plan_path, repo / 'tools/drive_evidence_v1/sources.py',
                 repo / 'tools/idle_material_v1/features.py',
                 *sorted((repo / 'tools/accel_material_v1').glob('*.py'))]:
        relative = path.relative_to(repo)
        target = a.out / 'exact_sources' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        r['sources'][relative.as_posix()] = sha(path)
    r['controls'] = controls(plan)
    print(json.dumps(dict(stage='known_controls', **r['controls'])), flush=True)
    for segment in plan['segments']:
        audio, provenance = read(a.workspace, segment, 'fixed_window_spectral_observation')
        rows, arrays = compare(audio, plan['bands_hz'], plan['spectral_scale'])
        arrays_path = a.out / (segment + '.npz')
        np.savez_compressed(arrays_path, audio=audio, **arrays)
        for row in rows:
            row['source_center_seconds'] = provenance['seconds'][0] + row['relative_center_seconds']
        observation = dict(segment=segment, provenance=provenance, tiles=rows,
                           arrays=arrays_path.name, arrays_sha256=sha(arrays_path),
                           supported_tiles=sum(row['spectral_scale']['supported'] for row in rows))
        r['observations'].append(observation)
        print(json.dumps(dict(stage='observed', segment=segment, tiles=len(rows),
                              supported=observation['supported_tiles'],
                              last_scale=rows[-1]['spectral_scale']['ratio'])), flush=True)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    figure, axes = plt.subplots(3, len(r['observations']), figsize=(13, 9), layout='constrained')
    for col, obs in enumerate(r['observations']):
        arr = np.load(a.out / obs['arrays'])
        centers = np.array([row['relative_center_seconds'] for row in obs['tiles']])
        freq = arr['frequency']; selected = (freq >= 200) & (freq <= 8000)
        image = 10 * np.log10(np.maximum(arr['cells'][:, selected, :].mean(axis=2).T, 1e-16))
        axes[0, col].pcolormesh(centers, freq[selected], image, shading='nearest', vmin=-90, vmax=-25)
        axes[0, col].set(yscale='log', ylim=(200, 8000), ylabel='Native frequency (Hz)', title=obs['segment'])
        ratio = [row['spectral_scale']['ratio'] for row in obs['tiles']]
        good = np.array([row['spectral_scale']['supported'] for row in obs['tiles']])
        axes[1, col].plot(centers, ratio, color='.7')
        axes[1, col].scatter(centers[good], np.array(ratio)[good], color='C0', label='Supported')
        axes[1, col].scatter(centers[~good], np.array(ratio)[~good], color='C3', marker='x', label='Ambiguous')
        axes[1, col].set(ylabel='Relative spectral scale', xlabel='Local time (s)', ylim=(.8, 1.42))
        axes[1, col].legend(fontsize=8)
        residual = np.array([row['colour_residual_db_LR'] for row in obs['tiles']]).mean(axis=2).T
        residual[:, ~good] = np.nan
        im = axes[2, col].pcolormesh(centers, np.arange(len(plan['bands_hz'])), residual,
                                    shading='nearest', cmap='coolwarm', vmin=-6, vmax=6)
        axes[2, col].set(yticks=np.arange(len(plan['bands_hz'])),
                         yticklabels=[f'{lo}-{hi}' for lo, hi in plan['bands_hz']],
                         ylabel='Band (Hz)', xlabel='Local time (s)')
    figure.colorbar(im, ax=axes[2, :], label='Band power vs scaled first window + global gain (dB)')
    figure.suptitle('F3 cabin observations only: no engine clock, RPM/load or independent takes established')
    figure.savefig(a.out / 'F3_acceleration_material.png', dpi=150)
    plt.close(figure)
    r.update(result='fixed_native_acceleration_observations_complete_not_a_synthesis_profile', plan=plan,
             plot_sha256=sha(a.out / 'F3_acceleration_material.png'),
             limitations=['Relative spectral-scale candidates are not fundamental/RPM measurements.',
                          'Pitch-only comparison approximates finite-window spectral cells; colour residual is not pure load or an identified physical source.',
                          'Same-video cabin observations; no independent take, calibrated audiovisual timing, ECU RPM or pedal/torque.',
                          'Source F3 stationary speech remains excluded; F2 idle listening remains pending.'])
finally:
    if sys.exc_info()[0]:
        r.update(result='failed', error=repr(sys.exc_info()[1]))
    save(a.out / 'report.json', r)
