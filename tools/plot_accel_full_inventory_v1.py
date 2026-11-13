"""Compare frozen native coverage and show every corrected dominant-mode row."""
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

r = load(a.audit / 'report.json')
assert r['result'] == 'all_original_inventory_native_fits_maps_and_coverage_verified'
assert r['input_report_sha256'] == sha(a.input / 'report.json')
oldroot = a.workspace / 'references/analysis/accel_coverage_v1/observe1'
old = load(oldroot / 'report.json')
a.out.mkdir(parents=True, exist_ok=False)
shutil.copy2(__file__, a.out / 'executed_plot.py')
labels = ['30-150', '150-300', '300-1k', '1-2.2k', '2.2-4k', '4-8k', '8-14k']
x = np.arange(7)
fig, axes = plt.subplots(2, 3, figsize=(15, 8), layout='constrained')
for col, row in enumerate(r['summaries']):
    name = row['segment']
    prior = next(v for v in old['observations'] if v['segment'] == name)
    ax = axes[0, col]
    for values, label, style in [
        (prior['aggregate']['all_parts']['model_over_source'], 'Old all fits', 'o--'),
        (prior['aggregate']['eligible_parts']['model_over_source'], 'Old eligible', 's--'),
        (row['aggregate']['all']['model_over_source'], 'Corrected all fits', 'o-'),
        (row['aggregate']['eligible']['model_over_source'], 'Corrected eligible', 's-'),
    ]:
        ax.plot(x, np.asarray(values)[:, 0] * 100, style, label=label, lw=1)
    ax.set_title(name + ' / all original windows, L')
    ax.set_xticks(x, labels, rotation=35, ha='right', fontsize=8)
    ax.set_ylabel('Model/source power (%) / NOT explained power')
    ax.grid(alpha=.2)
    ax.legend(fontsize=7)
    saved = np.load(a.input / name / 'tile_00.npz')
    first = load(a.input / name / 'fits.json')[0]
    n = len(saved['audio'])
    w = np.hanning(n + 1)[:-1]
    hz = np.fft.rfftfreq(n, 1 / 48000)
    ax = axes[1, col]
    prior_first = np.load(oldroot / name / 'tile_00.npz')
    for samples, label in [
        (saved['audio'], 'Native source'),
        (prior_first['all_model'], 'Old all fitted lines'),
        (saved['reconstructed'], 'Corrected all fitted lines'),
    ]:
        power = abs(np.fft.rfft(samples[:, 0] * w)) ** 2 / (n * np.sum(w * w))
        ax.semilogx(hz[1:], 10 * np.log10(np.maximum(power[1:], 1e-25)), label=label, lw=.7)
    ax.set_title('First tile / corrected optimizer ' + ('PASS' if first['success'] else 'FAIL: diagnostic only'))
    ax.set_xlim(30, 14000)
    ax.set_ylim(-160, -10)
    ax.set_xlabel('Native frequency (Hz)')
    ax.set_ylabel('Windowed cell power (dBFS)')
    ax.grid(alpha=.2)
    ax.legend(fontsize=7)
fig.suptitle('Reference selection correction: restore original 200-7000 Hz inventory\nAll fits remain diagnostic; failed windows have no eligible lines; no source compensation', fontsize=12)
fig.savefig(a.out / 'coverage_correction.png', dpi=150)
plt.close(fig)

fig, axes = plt.subplots(3, 3, figsize=(15, 9), layout='constrained')
for col, summary in enumerate(r['summaries']):
    name = summary['segment']
    rows = load(a.input / name / 'fits.json')
    k = summary['dominant_reference']
    for row in rows:
        t = (row['tile'] + .5) * .25
        lines = [v for v in row['lines'] if v['reference_index'] == k]
        for ax in axes[:, col]:
            if not row['success']:
                ax.axvspan(t - .125, t + .125, color='red', alpha=.10)
            if not row['guide_supported']:
                ax.axvspan(t - .125, t + .125, facecolor='none', edgecolor='0.5', hatch='//')
        if not lines:
            for ax in axes[:, col]:
                ax.axvline(t, color='0.75', ls=':', lw=.7)
            continue
        line = lines[0]
        eligible = line['eligible'] and row['guide_supported']
        marker, color = ('o', 'C0') if eligible else ('x', 'C3')
        axes[0, col].plot(t, line['frequency_hz'], marker, color=color)
        for c, filled in [(0, True), (1, False)]:
            axes[1, col].plot(t, line['amplitude_LR'][c], marker, color=color,
                              markerfacecolor=color if filled else 'none')
        axes[2, col].plot(t, min(line['local_explained_fraction_LR']), marker, color=color)
    axes[0, col].set_title(name + f" / initial {summary['dominant_initial_hz']:.3f} Hz")
    axes[0, col].set_ylabel('Independent fitted frequency (Hz)')
    axes[1, col].set_ylabel('Amplitude (FS), L solid / R hollow')
    axes[2, col].set_ylabel('Minimum local conditional support')
    axes[2, col].axhline(.8, ls='--', color='0.5', lw=.8)
    for ax in axes[:, col]:
        ax.grid(alpha=.2)
        ax.set_xlabel('Passage time (s)')
fig.suptitle('Previously omitted strongest reference / every original window\nBlue: eligible + guide; red x: rejected diagnostic; red shading: optimizer failure; hatch: guide failure; dotted: missing/ambiguous', fontsize=11)
fig.savefig(a.out / 'dominant_observations.png', dpi=150)
plt.close(fig)
save(a.out / 'report.json', dict(
    result='all_passages_coverage_and_dominant_rows_plotted',
    audit_report_sha256=sha(a.audit / 'report.json'),
    input_report_sha256=sha(a.input / 'report.json'),
    old_coverage_sha256=sha(oldroot / 'report.json'),
    images={name: sha(a.out / name) for name in ['coverage_correction.png', 'dominant_observations.png']},
    no_window_or_failed_fit_removed=True, no_audio_or_profile=True,
))
print('Coverage correction and every dominant-mode observation plotted.')
