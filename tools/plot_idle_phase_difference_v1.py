"""Show all prediction outcomes, complete six cross curves and residual budgets."""
import argparse
import shutil
import sys
from pathlib import Path
p = argparse.ArgumentParser(description=__doc__)
for key in ['workspace', 'input', 'audit', 'bound', 'bound-audit', 'out']:
    p.add_argument('--'+key, type=Path, required=True)
a = p.parse_args(); sys.path.insert(0, str(a.workspace/'tools/python_deps'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from research_archive_v1 import load, save, sha

observed, audit = load(a.input/'report.json'), load(a.audit/'report.json')
bounds, baudit = load(a.bound/'report.json'), load(a.bound_audit/'report.json')
assert audit['result'] == 'all_nested_features_models_and_800_direct_lag_curves_verified'
assert baudit['result'] == 'all10_models_full32768point_bounds_independently_verified'
assert audit['input_report_sha256'] == baudit['input_report_sha256'] == sha(a.input/'report.json')
assert baudit['bound_report_sha256'] == sha(a.bound/'report.json')
a.out.mkdir(parents=True, exist_ok=False); shutil.copy2(__file__, a.out/'executed_plot.py')
labels = ['1.2-2.2k', '2.2-4k', '4-8k', '8-14k']
images = []

fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), layout='constrained')
x = np.arange(4)
for row in observed['observations'][1:]:
    axes[0].plot(x, np.array(row['incremental_check_improvement'])*100, '.-', color='#94a3b8', alpha=.8,
                 label='Same-PSD controls' if row == observed['observations'][1] else None)
row = observed['observations'][0]
axes[0].plot(x, np.array(row['incremental_check_improvement'])*100, 'o-', color='#0d9488', lw=2, label='F2 source')
axes[0].axhline(0, color='black', lw=.7)
axes[0].set(xticks=x, xticklabels=labels, ylabel='Incremental check MSE reduction (%)',
            title='TRAIN-only native -> native + all differences')
axes[0].legend()
cert = bounds['observations'][0]['certificate']
axes[1].bar(x-.2, row['models']['expanded']['lower_bound'], .2, label='Triangle sufficient bound', color='#64748b')
axes[1].bar(x, cert['global_lower_bound'], .2, label='Dependent-phase covering lower bound', color='#2563eb')
axes[1].bar(x+.2, cert['grid_minimum'], .2, label='Actual grid value / negative witness', color='#c26a27')
axes[1].axhline(0, color='black', lw=.7)
axes[1].set(xticks=x, xticklabels=labels, ylabel='Normalized predicted power', title='2.2-4k has a real negative phase combination')
axes[1].legend(fontsize=8)
for ax in axes: ax.grid(axis='y', alpha=.2)
fig.suptitle('Idle phase-difference study: predictive improvement is not a deployable power law')
name = 'prediction_and_bounds.png'; fig.savefig(a.out/name, dpi=150); plt.close(fig)
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
                ax.plot(data['lags_ms'], data['native_'+part+'_PP'][j], color=color, lw=.9, ls=':', label=part+' native prediction')
                ax.plot(data['lags_ms'], data['expanded_'+part+'_PP'][j], color=color, lw=1.2, ls='--', label=part+' expanded prediction')
        else:
            for term, color, style in [('TT', '#182e39', '-'), ('PP', '#0d9488', '--'),
                                        ('PR', '#2563eb', ':'), ('RP', '#9333ea', ':'), ('RR', '#c26a27', '-')]:
                ax.plot(data['lags_ms'], data['expanded_check_'+term][j], color=color, ls=style, label=term)
        b, c = pairs[j]
        ax.set(title=labels[b]+' / '+labels[c], xlabel='Lag (ms); second band later', ylabel='Normalized power covariance')
        ax.axhline(0, color='black', lw=.5); ax.grid(alpha=.2)
    handles, names = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, names, loc='outside lower center', ncol=3 if kind == 'prediction' else 5, fontsize=9)
    fig.suptitle('F2 idle: all six cross-band curves, fixed -40..40ms / 1ms\n'+
                 ('Measured1ms powers versus predicted powers; not generated waveform cumulants'
                  if kind == 'prediction' else 'Check portion: exact TT = PP + PR + RP + RR; mixed/residual terms remain'))
    name = 'cross_'+kind+'.png'; fig.savefig(a.out/name, dpi=150); plt.close(fig)
    images.append(dict(file=name, sha256=sha(a.out/name)))
save(a.out/'report.json', dict(result='all_phase_difference_outcomes_and_cross_budgets_plotted', images=images,
    input_report_sha256=sha(a.input/'report.json'), audit_sha256=sha(a.audit/'report.json'),
    bound_report_sha256=sha(a.bound/'report.json'), bound_audit_sha256=sha(a.bound_audit/'report.json')))
