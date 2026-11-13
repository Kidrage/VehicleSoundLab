"""Draw the saved observations; never refit or re-read source audio."""
import argparse
import json
from pathlib import Path
import shutil
import sys

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True)
p.add_argument('--input', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
sys.path.insert(0, str(a.workspace / 'tools/python_deps'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

a.out.mkdir(parents=True, exist_ok=False)
shutil.copy2(__file__, a.out / 'executed_plot.py')
report = json.loads((a.input / 'report.json').read_text(encoding='utf-8'))
fig = plt.figure(figsize=(14, 9.5), layout='constrained')
layout = fig.add_gridspec(3, 4, width_ratios=[1, 1, 1, .045])
for col, obs in enumerate(report['observations']):
    array = np.load(a.input / obs['arrays'])
    times = np.array([row['relative_center_seconds'] for row in obs['tiles']])
    frequencies = array['frequency']
    use = (frequencies >= 200) & (frequencies <= 8000)
    ax = fig.add_subplot(layout[0, col])
    power = 10 * np.log10(np.maximum(array['cells'][:, use, :].mean(axis=2).T, 1e-16))
    first = ax.pcolormesh(times, frequencies[use], power, shading='nearest', vmin=-90, vmax=-25)
    ax.set(yscale='log', ylim=(200, 8000), ylabel='Frequency (Hz)',
           title=f"{obs['segment']} | {obs['provenance']['seconds'][0]}-{obs['provenance']['seconds'][1]}s")
    ax = fig.add_subplot(layout[1, col])
    ratios = np.array([row['spectral_scale']['ratio'] for row in obs['tiles']])
    good = np.array([row['spectral_scale']['supported'] for row in obs['tiles']])
    ax.plot(times, ratios, color='.75')
    ax.scatter(times[good], ratios[good], color='C0', label='Supported by fixed rule')
    ax.scatter(times[~good], ratios[~good], color='C3', marker='x', label='Unresolved')
    ax.set(xlabel='Local time (s)', ylabel='Relative spectral-scale candidate', ylim=(.8, 1.42))
    ax.legend(fontsize=7)
    ax = fig.add_subplot(layout[2, col])
    colour = np.array([row['colour_residual_db_LR'] for row in obs['tiles']]).mean(axis=2).T
    colour[:, ~good] = np.nan
    last = ax.pcolormesh(times, np.arange(7), colour, shading='nearest', cmap='coolwarm', vmin=-6, vmax=6)
    ax.set(yticks=np.arange(7), yticklabels=[f'{lo}-{hi}' for lo, hi in report['plan']['bands_hz']],
           xlabel='Local time (s)', ylabel='Band (Hz)')
fig.colorbar(first, cax=fig.add_subplot(layout[0, 3]), label='Mean L/R cell power (dBFS)')
fig.colorbar(last, cax=fig.add_subplot(layout[2, 3]), label='Colour residual: mean L/R (dB)')
fig.suptitle('F3 cabin: native spectra / relative acoustic scale / deviation from a pitch-only first-window model\n'
             '48 fixed 0.25s tiles; blank cells are unresolved. No calibrated RPM, load or independent recordings.', fontsize=11)
fig.savefig(a.out / 'F3_acceleration_material.png', dpi=150)
plt.close(fig)
(a.out / 'report.json').write_text(json.dumps(dict(result='saved_observations_plotted_without_refit',
    input=str(a.input), source_audio_read=False, synthesis_changed=False), indent=2) + '\n', encoding='utf-8')
