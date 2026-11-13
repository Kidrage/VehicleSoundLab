"""Native low spectra, query centers and resolution limits; never source labels."""
import argparse
import shutil
import sys
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
for key in ['workspace', 'input', 'audit', 'out']:
    p.add_argument('--' + key, type=Path, required=True)
a = p.parse_args()
sys.path.insert(0, str(a.workspace / 'tools/python_deps'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from research_archive_v1 import load, save, sha

report = load(a.input / 'report.json')
audit = load(a.audit / 'report.json')
assert audit['result'] == 'all48_native_low_power_descriptors_scanned_peaks_and_graphs_verified'
assert audit['input_report_sha256'] == sha(a.input / 'report.json')
a.out.mkdir(parents=True, exist_ok=False)
shutil.copy2(__file__, a.out / 'executed_plot.py')
fig, axes = plt.subplots(2, 3, figsize=(15, 8), layout='constrained')
details = []
parent = a.workspace / 'baselines/accel_ridges_v1/evidence/observe2'
for col, name in enumerate(report['plan']['segments']):
    data = load(a.input / name / 'observations.json')
    rows = data['rows']
    old = load(parent / (name + '.json'))
    tt = (np.arange(len(rows)) + .5) * .25
    cells = np.stack([np.load(a.input / name / f'tile_{i:02d}.npz')['cells'][:66].mean(axis=1) for i in range(len(rows))])
    ax = axes[0, col]
    im = ax.imshow(10 * np.log10(np.maximum(cells.T, 1e-30)), origin='lower', aspect='auto',
                   extent=[0, len(rows) * .25, -2, 262], vmin=-75, vmax=-15, cmap='magma')
    for k, f in enumerate(data['reference_hz']):
        ax.plot(tt, [f * v['guide']['ratio'] for v in rows], color='cyan', lw=.7, alpha=.7)
    for row in rows:
        hz = [v for v in row['observed_union_hz'] if 20 <= v <= 260]
        ax.scatter(np.full(len(hz), (row['tile'] + .5) * .25), hz, s=10, facecolor='none', edgecolor='white', lw=.6)
    ax.axhline(200, color='lime', ls='--', lw=1)
    ax.set_title(name + ' / source power, L+R average')
    ax.set_ylim(20, 260)
    ax.set_xlabel('Passage time (s)')
    ax.set_ylabel('Native frequency (Hz)')
    fig.colorbar(im, ax=ax, label='Windowed cell power (dBFS)')
    ax = axes[1, col]
    for band, label, color in [(2, '30-75 Hz', 'C0'), (3, '75-150 Hz', 'C1'), (4, '150-200 Hz', 'C2')]:
        for c, style in [(0, '-'), (1, '--')]:
            ax.plot(tt, [v['band_fraction_of_full_native_LR'][band][c] * 100 for v in rows], style,
                    color=color, lw=1, label=label + (' / L' if c == 0 else ' / R'))
    ax.set_xlabel('Passage time (s)')
    ax.set_ylabel('Fraction of all native power (%)')
    ax.set_title('All windows / same native bands')
    ax.grid(alpha=.2)
    ax.legend(fontsize=7, ncol=2)
    per_reference = []
    for k, f in enumerate(data['reference_hz']):
        selected = [v for v in rows if v['original_separation_eligible'][k]]
        original = load(a.input.parent / 'observe2' / name / 'observations.json')['rows']
        per_reference.append(dict(reference_hz=f, eligible_tiles=[v['tile'] for v in selected],
            moving_unique=sum(v['moving']['state'][k] == 'unique' for v in selected),
            fixed_unique=sum(v['fixed']['state'][k] == 'unique' for v in selected),
            censored_original_moving_unique=sum(v['moving']['state'][k] == 'unique' for v in original if v['original_separation_eligible'][k])))
    details.append(dict(segment=name, references=per_reference))
fig.suptitle('F3 omitted low band: raw native spectra and every low query\nWhite circles: observed peaks; cyan: moving query centers, NOT tracks; green boundary: old lower-band cutoff; upper observations reused from frozen inventory', fontsize=11)
fig.savefig(a.out / 'native_low.png', dpi=150)
plt.close(fig)

fig, axes = plt.subplots(1, 3, figsize=(15, 4.8), layout='constrained')
for ax, item in zip(axes, details):
    rows = item['references']
    xx = np.arange(len(rows))
    for offset, values, label, color in [
        (-.25, [len(v['eligible_tiles']) for v in rows], 'Geometrically eligible', '0.7'),
        (0, [v['moving_unique'] for v in rows], 'Moving query unique', 'C0'),
        (.25, [v['fixed_unique'] for v in rows], 'Fixed query unique', 'C1'),
    ]:
        ax.bar(xx + offset, values, width=.24, color=color, label=label)
    ax.set_xticks(xx, [f"{v['reference_hz']:.1f}" for v in rows], rotation=35, ha='right')
    ax.set_xlabel('First-window native low reference (Hz)')
    ax.set_ylabel('Window count / original support rule')
    ax.set_title(item['segment'])
    ax.legend(fontsize=7)
    ax.grid(alpha=.2)
fig.suptitle('Original 4 Hz query resolution cannot distinguish the lowest moving/fixed alternatives\nBoth matches may hit different lines; no old dense-comb classification or source identity is inferred', fontsize=11)
fig.savefig(a.out / 'low_resolution.png', dpi=150)
plt.close(fig)
save(a.out / 'report.json', dict(result='all48_native_low_and_geometric_resolution_plotted',
    input_report_sha256=sha(a.input / 'report.json'), audit_report_sha256=sha(a.audit / 'report.json'),
    reference_diagnostics=details, source_classification=False,
    images={name: sha(a.out / name) for name in ['native_low.png', 'low_resolution.png']}))
print('All native low windows and resolution limits plotted.')
