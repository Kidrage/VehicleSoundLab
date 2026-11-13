"""Show every tested output budget and separate input linkage from filter effects."""
import argparse
import shutil
import sys
from pathlib import Path
p = argparse.ArgumentParser(description=__doc__)
for key in ['workspace', 'input', 'audit', 'diagnostic', 'diagnostic-audit', 'out']:
    p.add_argument('--'+key, type=Path, required=True)
a = p.parse_args(); sys.path.insert(0, str(a.workspace/'tools/python_deps'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from research_archive_v1 import load, save, sha

observed, audit = load(a.input/'report.json'), load(a.audit/'report.json')
diagnostic, daudit = load(a.diagnostic/'report.json'), load(a.diagnostic_audit/'report.json')
assert audit['result'] == 'all8_wave_cases_15partition_and_independent_convolution_verified'
assert daudit['result'] == 'all_source_runtime_input_response_diagnostics_independently_verified'
assert audit['input_report_sha256'] == daudit['input_report_sha256'] == sha(a.input/'report.json')
assert daudit['diagnostic_report_sha256'] == sha(a.diagnostic/'report.json')
a.out.mkdir(parents=True, exist_ok=False); shutil.copy2(__file__, a.out/'executed_plot.py')
r = dict(result='running', images=[], inputs={}, comparisons=[])
tables = {}
for name in ['idle_joint_lag_v1', 'idle_excitation_moments_v1']:
    root = a.workspace/'baselines'/name; r['inputs'][str(root/'manifest.json')] = sha(root/'manifest.json')
    tables[name] = {v['path']: v['sha256'] for v in load(root/'manifest.json')['files']}

def parent(name, file):
    path = a.workspace/'baselines'/name/file; assert sha(path) == tables[name][file]
    r['inputs'][str(path)] = sha(path); return path


source = {}
for part in ['training', 'check']:
    with np.load(parent('idle_joint_lag_v1', f'evidence/observe1/{part}.npz')) as archive:
        source[part] = dict(lags=archive['lags'], normalized=archive['raw_normalized'])
    with np.load(parent('idle_excitation_moments_v1', f'evidence/observe1/{part}.npz')) as archive:
        source[part]['mean_power'] = np.mean(archive['filtered']**2, axis=0)
cases = {}
for row in observed['cases']:
    assert sha(a.input/row['file']) == row['sha256']
    with np.load(a.input/row['file']) as archive: cases[row['label']] = {key: archive[key] for key in archive.files}
    for part, reference in source.items():
        arrays = cases[row['label']]
        r['comparisons'].append(dict(label=row['label'], source=part,
            curve_RMSE=np.sqrt(np.mean((arrays['normalized']-reference['normalized'])**2, axis=1)).tolist(),
            mean_power_error_dB=(10*np.log10(arrays['mean_power']/reference['mean_power'])).tolist()))
labels = ['1.2-2.2k', '2.2-4k', '4-8k', '8-14k']
pairs = [(b, c) for b in range(4) for c in range(b, 4)]
cross = [j for j, (b, c) in enumerate(pairs) if b != c]

for kind in ['cross', 'auto']:
    selected = cross if kind == 'cross' else [j for j, (b, c) in enumerate(pairs) if b == c]
    fig, axes = plt.subplots(2, 3 if kind == 'cross' else 2, figsize=(13, 7.7), layout='constrained')
    for ax, j in zip(axes.flat, selected):
        for part, color in [('training', '#182e39'), ('check', '#c26a27')]:
            ax.plot(source[part]['lags']/48, source[part]['normalized'][j], color=color, lw=1.8, label='F2 '+part+' empirical')
        for row in observed['cases']:
            arrays = cases[row['label']]
            color = '#94a3b8' if row['amount'] == 0 else '#0d9488' if row['distribution'] == 'Gaussian' else '#2563eb'
            style = ':' if row['distribution'] == 'Gaussian' else '--' if row['amount'] == 0 else '-'
            ax.plot(arrays['lags']/48, arrays['normalized'][j], color=color, ls=style,
                    alpha=1 if row['block'] == 0 else .5, lw=1.2,
                    label=('Pre gain'+str(row['amount'])+' '+row['distribution']+' / both blocks') if row['block'] == 0 else None)
        b, c = pairs[j]
        ax.set(title=labels[b]+' / '+labels[c], xlabel='Lag (ms); second band later', ylabel='Normalized fourth cumulant')
        ax.axhline(0, color='black', lw=.5); ax.grid(alpha=.2)
    handles, names = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, names, loc='outside lower center', ncol=3, fontsize=8)
    fig.suptitle('Actual13OSC+6FIR: all '+kind+' budgets, fixed -40..40ms /1ms\nTheory pools time origins + innovations; source is finite empirical, not an unbiased estimator comparison')
    name = kind+'_wave_curves.png'; fig.savefig(a.out/name, dpi=150); plt.close(fig)
    r['images'].append(dict(file=name, sha256=sha(a.out/name)))

fig, axes = plt.subplots(2, 3, figsize=(13, 7.7), layout='constrained')
for ax, j in zip(axes.flat, cross):
    for block in range(2):
        arrays = cases[f'amount1_sparse_block{block}']; terms = arrays['terms'][:, :, :]
        groups = [('Full', arrays['normalized'][j], '#182e39', '-'),
                  ('Periodic variance/covariance mixture', terms[j, :, 1]+terms[j, :, 2], '#0d9488', '--'),
                  ('Sparse innovations', terms[j, :, 6], '#c26a27', '-'),
                  ('Main + all main/random cross terms', terms[j, :, 0]+terms[j, :, 3:6].sum(axis=1), '#9333ea', ':')]
        for label, values, color, style in groups:
            ax.plot(arrays['lags']/48, values, color=color, ls=style, alpha=1 if block == 0 else .45,
                    label=label+' / both blocks' if block == 0 else None)
    b, c = pairs[j]
    ax.set(title=labels[b]+' / '+labels[c], xlabel='Lag (ms)', ylabel='Normalized cumulant contributions')
    ax.axhline(0, color='black', lw=.5); ax.grid(alpha=.2)
handles, names = axes.flat[0].get_legend_handles_labels()
fig.legend(handles, names, loc='outside lower center', ncol=2, fontsize=8)
fig.suptitle('Gain1 sparse: all seven exact terms retained, displayed in three additive groups\nIndependent innovation kurtosis is not a free addition after periodic variance is introduced')
name = 'cross_decomposition.png'; fig.savefig(a.out/name, dpi=150); plt.close(fig)
r['images'].append(dict(file=name, sha256=sha(a.out/name)))

fig, axes = plt.subplots(1, 2, figsize=(13, 4.8), layout='constrained')
names = [labels[b]+'/'+labels[c] for b, c in pairs if b != c]
x = np.arange(6)
for row in diagnostic['observations']:
    source_row = row['label'].startswith('source')
    axes[0].plot(x, row['result']['q_zero_correlations'], '.-' if source_row else 'o--',
                 color='#94a3b8' if source_row else '#0d9488', alpha=.85, label=row['label']+' input q')
    if not source_row:
        axes[0].plot(x, row['output_variance']['q_zero_correlations'], 's-', color='#c26a27', alpha=.65,
                     label=row['label']+' after FIR + observation')
axes[0].set(xticks=x, xticklabels=names, ylabel='Zero-lag conditional-power correlation', title='Two sign reversals occur after filtering')
axes[0].tick_params(axis='x', rotation=24); axes[0].axhline(0, color='black', lw=.7); axes[0].legend(fontsize=7)
x = np.arange(4)
reference = source['training']['mean_power']
axes[1].plot(x, 10*np.log10(source['check']['mean_power']/reference), 'o-', color='#c26a27', label='F2 check / training')
for amount, color in [(0, '#64748b'), (1, '#2563eb')]:
    for block in range(2):
        values = cases[f'amount{amount}_sparse_block{block}']['mean_power']
        axes[1].plot(x, 10*np.log10(values/reference), 's--' if block else 's-', color=color, alpha=.6 if block else 1,
                     label=f'Pre gain{amount}, block{block}')
axes[1].set(xticks=x, xticklabels=labels, ylabel='Mean power difference (dB)', title='Mean powers retained, no per-case compensation')
axes[1].axhline(0, color='black', lw=.7); axes[1].legend(fontsize=8)
for ax in axes: ax.grid(alpha=.2)
fig.suptitle('Hypothesis diagnosis: positive source linkage survives input coordinates, output timing differs')
name = 'input_output_and_energy.png'; fig.savefig(a.out/name, dpi=150); plt.close(fig)
r['images'].append(dict(file=name, sha256=sha(a.out/name)))
with np.load(a.input/'architecture.npz') as archive: h = archive['h']
r['own_band_energy_centroid_ms'] = [float(np.dot(np.arange(h.shape[2]), h[b, b+2]**2)/np.sum(h[b, b+2]**2)/48) for b in range(4)]
r['sparse_2to4k_zero_relative_increase'] = [float(cases[f'amount1_sparse_block{block}']['normalized'][4, 40]/cases[f'amount0_sparse_block{block}']['normalized'][4, 40]-1) for block in range(2)]
r.update(result='all8_cases_full_wave_curves_and_filter_diagnostic_plotted',
    input_report_sha256=sha(a.input/'report.json'), audit_sha256=sha(a.audit/'report.json'),
    diagnostic_report_sha256=sha(a.diagnostic/'report.json'), diagnostic_audit_sha256=sha(a.diagnostic_audit/'report.json'))
save(a.out/'report.json', r)
