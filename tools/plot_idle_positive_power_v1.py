"""All positive-model outcomes, remaining mean debt and complete time budgets."""
import argparse
import shutil
import sys
from pathlib import Path
p = argparse.ArgumentParser(description=__doc__)
for key in ['workspace', 'input', 'audit', 'out']:
    p.add_argument('--'+key, type=Path, required=True)
a = p.parse_args(); sys.path.insert(0, str(a.workspace/'tools/python_deps'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from research_archive_v1 import load, save, sha

observed, audit = load(a.input/'report.json'), load(a.audit/'report.json')
assert audit['result'] == 'all8_positive_models32_KKT_fits_and800_lag_curves_verified'
assert audit['input_report_sha256'] == sha(a.input/'report.json')
a.out.mkdir(parents=True, exist_ok=False); shutil.copy2(__file__, a.out/'executed_plot.py')
row = observed['observations'][0]
labels = ['1.2-2.2k', '2.2-4k', '4-8k', '8-14k']; x = np.arange(4)
images = []
fig, axes = plt.subplots(1, 3, figsize=(15, 4.8), layout='constrained')
for j, control in enumerate(observed['observations'][1:]):
    axes[0].plot(x, np.asarray(control['incremental_check_improvement'])*100, '.-', color='#94a3b8',
                 alpha=.8, label='All3 same-PSD controls' if j == 0 else None)
axes[0].plot(x, np.asarray(row['incremental_check_improvement'])*100, 'o-', color='#0d9488', lw=2, label='Against native positive')
axes[0].plot(x, np.asarray(row['check_improvement_over_old_native_OLS'])*100, 's--', color='#2563eb', label='Against old native OLS')
axes[0].axhline(0, color='black', lw=.7)
axes[0].set(ylabel='Check MSE reduction (%)', title='All4bands retain predictive improvement')
axes[0].legend(fontsize=8)
for kind, offset, color in [('native', -.1, '#64748b'), ('expanded', .1, '#0d9488')]:
    bound = row['models'][kind]['bounds']
    low, high = np.asarray(bound['power_lower']), np.asarray(bound['power_upper'])
    axes[1].vlines(x+offset, low, high, color=color, lw=3, label=kind+' global power bounds')
    axes[1].scatter(x+offset, low, color=color, marker='_', s=100)
    axes[1].scatter(x+offset, high, color=color, marker='_', s=100)
axes[1].set(yscale='log', ylabel='Normalized sample power (log scale)', title='Positive finite bounds for EVERY phase')
axes[1].axhline(1, color='black', lw=.5); axes[1].legend(fontsize=8)
for offset, values, label, color in [(-.23, row['assessment']['expanded']['check']['mean_target'], 'F2 check target', '#c26a27'),
                                     (0., row['assessment']['native']['check']['mean_prediction'], 'Native prediction', '#64748b'),
                                     (.23, row['assessment']['expanded']['check']['mean_prediction'], 'Expanded prediction', '#0d9488')]:
    axes[2].bar(x+offset, values, .22, color=color, label=label)
axes[2].set(ylabel='Mean power / TRAIN mean', ylim=(.8, 1.28), title='Longer-term source-level change remains')
axes[2].axhline(1, color='black', lw=.5); axes[2].legend(fontsize=8)
for ax in axes:
    ax.set(xticks=x, xticklabels=labels); ax.grid(axis='y', alpha=.2)
fig.suptitle('Positive idle conditional power: source prediction, not generated-waveform or timbre acceptance')
name = 'prediction_bounds_means.png'; fig.savefig(a.out/name, dpi=150); plt.close(fig)
images.append(dict(file=name, sha256=sha(a.out/name)))

with np.load(a.input/row['file']) as archive: data = {key: archive[key] for key in archive.files}
pairs = [(b, c) for b in range(4) for c in range(b, 4)]
cross = [j for j, (b, c) in enumerate(pairs) if b != c]
for kind in ['prediction', 'budget']:
    fig, axes = plt.subplots(2, 3, figsize=(13, 7.7), layout='constrained')
    for ax, j in zip(axes.flat, cross):
        if kind == 'prediction':
            for part, color in [('train', '#182e39'), ('check', '#c26a27')]:
                ax.plot(data['lags_ms'], data['expanded_'+part+'_TT'][j], color=color, lw=1.8, label=part+' measured')
                ax.plot(data['lags_ms'], data['native_'+part+'_PP'][j], color=color, lw=.9, ls=':', label=part+' native positive')
                ax.plot(data['lags_ms'], data['expanded_'+part+'_PP'][j], color=color, lw=1.2, ls='--', label=part+' expanded positive')
        else:
            for term, color, style in [('TT', '#182e39', '-'), ('PP', '#0d9488', '--'),
                                       ('PR', '#2563eb', ':'), ('RP', '#9333ea', ':'), ('RR', '#c26a27', '-')]:
                ax.plot(data['lags_ms'], data['expanded_check_'+term][j], color=color, ls=style, label=term)
        b, c = pairs[j]
        ax.set(title=labels[b]+' / '+labels[c], xlabel='Lag (ms); second band later', ylabel='Normalized power covariance')
        ax.axhline(0, color='black', lw=.5); ax.grid(alpha=.2)
    handles, names = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, names, loc='outside lower center', ncol=3 if kind == 'prediction' else 5, fontsize=9)
    fig.suptitle('Positive idle power: all six cross curves, fixed -40..40ms / 1ms\n'+
                 ('Exact mean48(exp(sample feature law)); not exp(mean48(feature law))'
                  if kind == 'prediction' else 'Check portion: TT = PP + PR + RP + RR; residual and mixed terms remain'))
    name = 'cross_'+kind+'.png'; fig.savefig(a.out/name, dpi=150); plt.close(fig)
    images.append(dict(file=name, sha256=sha(a.out/name)))
save(a.out/'report.json', dict(result='all_positive_power_outcomes_and_cross_budgets_plotted', images=images,
    input_report_sha256=sha(a.input/'report.json'), audit_sha256=sha(a.audit/'report.json')))
