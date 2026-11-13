"""All six dominant transfers, both channels and all target-window observations."""
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

r = load(a.input / 'report.json')
audit = load(a.audit / 'report.json')
assert audit['result'] == 'all3_source_models_full_graphs_and6_dominant_transfers_verified'
assert audit['input_report_sha256'] == sha(a.input / 'report.json')
a.out.mkdir(parents=True, exist_ok=False)
shutil.copy2(__file__, a.out / 'executed_plot.py')
fits_root = a.workspace / 'baselines/accel_reference_selection_v1/evidence/accel_full_inventory_v1/observe1'
fits = {name: load(fits_root / name / 'fits.json') for name in r['plan']['segments']}
fig, axes = plt.subplots(3, 4, figsize=(17, 11), layout='constrained')
diagnostics = []
for index, pair in enumerate(r['pairs']):
    assert pair['status'] == 'compared'
    source, target = pair['source'], pair['target']
    k, j = pair['source_reference'], pair['target_reference']
    model = r['sources_data'][source]['model']
    ratio = pair['original_scale_match']['ratio']
    diagnostics.append(dict(source=source, target=target, per_channel={}))
    for c in range(2):
        ax = axes[index // 2, (index % 2) * 2 + c]
        for window in fits[source]:
            if window['guide_supported']:
                for line in window['lines']:
                    if line['reference_index'] == k and line['eligible']:
                        ax.plot(window['ratio'], 20 * np.log10(line['amplitude_LR'][c]), 'o', color='C0', ms=4)
        for window in fits[target]:
            for line in window['lines']:
                if line['reference_index'] != j:
                    continue
                x = float(np.log(ratio * window['ratio']))
                eligible = line['eligible'] and window['guide_supported']
                inside = model['coordinate_min'] <= x <= model['coordinate_max']
                marker, color = ('x', 'C3') if eligible and inside else ('D', '0.45') if eligible else ('+', '0.7')
                ax.plot(np.exp(x), 20 * np.log10(line['amplitude_LR'][c]), marker, color=color, ms=5, markerfacecolor='none')
        x = np.linspace(model['coordinate_min'], model['coordinate_max'], 100)
        mean, slope = model['log_amplitude_mean_LR'][c], model['slope_LR'][c]
        ax.plot(np.exp(x), np.full(100, 20 * np.log10(model['RMS_amplitude_LR'][c])), ':', color='C0', label='Source RMS')
        ax.plot(np.exp(x), np.full(100, 20 / np.log(10) * mean), '--', color='C2', label='Source geometric')
        ax.plot(np.exp(x), 20 / np.log(10) * (mean + slope * (x - model['coordinate_mean'])), color='C1', label='Source log-linear')
        ax.set_title(source.replace('F3_', '') + ' -> ' + target.replace('F3_', '') + ' / ' + ['L', 'R'][c], fontsize=10)
        ax.grid(alpha=.2)
        ax.set_xlabel('Relative acoustic scale / NOT RPM', fontsize=8)
        ax.set_ylabel('Native line amplitude (dBFS)', fontsize=8)
        inside = [v for v in pair['rows'] if v['within_source_range']]
        diagnostics[-1]['per_channel'][['L', 'R'][c]] = {
            key: dict(median_absolute_db=float(np.median([abs(v['error_db_LR'][key][c]) for v in inside])),
                      maximum_absolute_db=max(abs(v['error_db_LR'][key][c]) for v in inside))
            for key in ['RMS', 'geometric', 'log_linear']
        }
axes[0, 0].legend(fontsize=7)
fig.suptitle('Previously omitted dominant lines: all six source-only transfers, both channels\nBlue circles: source training; red x: eligible target inside source range; gray diamond: outside; light +: rejected diagnostic\nCurves never consume target amplitudes; all source-range, fit and guide exclusions remain', fontsize=12)
fig.savefig(a.out / 'dominant_laws.png', dpi=150)
plt.close(fig)

fig, axes = plt.subplots(1, 2, figsize=(12, 4.6), layout='constrained')
xx = np.arange(6)
labels = [v['source'].replace('F3_', '') + ' -> ' + v['target'].replace('F3_', '') for v in r['pairs']]
for offset, key, color in [(-.24, 'RMS', 'C0'), (0, 'geometric', 'C2'), (.24, 'log_linear', 'C1')]:
    axes[0].bar(xx + offset, [v['median_absolute_error_db'][key] for v in r['pairs']], width=.23, label=key, color=color)
axes[0].axhline(3, color='0.5', ls='--', lw=1)
axes[0].set_ylabel('Median absolute amplitude error / L+R (dB)')
axes[0].set_title('All laws / identical source-domain target rows')
axes[0].legend(fontsize=8)
axes[1].bar(xx, [v['maximum_frequency_error_hz'] for v in r['pairs']], color='C0')
axes[1].axhline(4, color='0.5', ls='--', lw=1)
axes[1].set_title('Maximum conditional frequency error')
axes[1].set_ylabel('Hz')
for ax in axes:
    ax.set_xticks(xx, labels, rotation=35, ha='right', fontsize=8)
    ax.grid(alpha=.2)
fig.suptitle('Dominant line transferable over observed narrow ranges; sloped law is not consistently better\nSame previously inspected recording + observed target eligibility + acoustic guide; no engine identity or full waveform claim', fontsize=11)
fig.savefig(a.out / 'dominant_errors.png', dpi=150)
plt.close(fig)
save(a.out / 'report.json', dict(result='all6_both_channels_and_all_target_windows_plotted',
    input_report_sha256=sha(a.input / 'report.json'), audit_report_sha256=sha(a.audit / 'report.json'),
    diagnostics=diagnostics, no_prediction_or_model_changed=True,
    images={name: sha(a.out / name) for name in ['dominant_laws.png', 'dominant_errors.png']}))
print('All six dominant transfers and both channels plotted.')
