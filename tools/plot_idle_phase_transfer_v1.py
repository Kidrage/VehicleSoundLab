"""Show ALL long-run q samples and phase/moment drift, with recorded-phase contrast."""
import argparse
import shutil
import sys
from pathlib import Path
p = argparse.ArgumentParser(description=__doc__)
for key in ['workspace', 'input', 'audit', 'out']: p.add_argument('--'+key, type=Path, required=True)
a = p.parse_args(); repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(a.workspace/'tools/python_deps'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from research_archive_v1 import load, save, sha


def correlation(cov):
    scale = np.sqrt(np.diag(cov)); return cov/scale[:, None]/scale[None, :]


a.out.mkdir(parents=True, exist_ok=False); shutil.copy2(__file__, a.out/'executed_plot.py')
r = dict(result='running', images=[])
try:
    observed = load(a.input/'report.json'); audit = load(a.audit/'report.json')
    assert audit['result'] == 'all60_native_blocks_and_both_recorded_phase_portions_verified'
    assert audit['input_report_sha256'] == sha(a.input/'report.json')
    with np.load(a.input/observed['data_file']) as archive: data = {k: archive[k] for k in archive.files}
    sources = []
    for row in observed['source_observations']:
        with np.load(a.input/row['file']) as archive: sources.append({k: archive[k] for k in archive.files})
    circular = data['block_circular'][:, -1]; times = np.arange(60)*3+1.5
    labels = ['1.2-2.2 kHz', '2.2-4 kHz', '4-8 kHz', '8-14 kHz']; colors = ['#007f78', '#b06713', '#506cbe', '#a34887']
    cov = np.array([row['covariance'] for row in observed['runtime']]); corr = np.array([correlation(x) for x in cov])
    source_corr = np.array([correlation(x['covariance']) for x in sources]); pairs = [(b, c) for b in range(4) for c in range(b+1, 4)]
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    ax = axes[0, 0]; angle = np.linspace(-np.pi, np.pi, 361); ax.plot(np.cos(angle), np.sin(angle), color='#cccccc')
    scatter = ax.scatter(circular.real, circular.imag, c=times, cmap='viridis', s=28)
    for source, marker, name in zip(sources, ['*', 'x'], ['F2 train', 'F2 check']):
        v = source['circular'][-1]; ax.scatter(v.real, v.imag, s=140, c='#ad2828', marker=marker, label=name)
    ax.set_aspect('equal'); ax.set(xlim=(-1.15, 1.15), ylim=(-1.15, 1.15), xlabel='Mean closure real', ylabel='Mean closure imaginary',
        title='Acoustic phase combination z2 conj(z1) conj(z0)')
    ax.legend(loc='lower left'); fig.colorbar(scatter, ax=ax, label='Runtime block midpoint (s)')
    ax = axes[0, 1]
    ratios = np.asarray(observed['block_q_power_db_relative_first12'])
    for b, name in enumerate(labels): ax.plot(times, ratios[:, b], label=name, color=colors[b])
    ax.axhline(0, color='#888888', linewidth=.7); ax.set(xlabel='Runtime (s)', ylabel='10log10(mean q / first12s mean q)',
        title='ALL60 block means: q-level ratios, NOT audio dB'); ax.legend(fontsize=9)
    ax = axes[1, 0]
    for b, name in enumerate(labels): ax.plot(times, np.sqrt(cov[:, b, b])/data['block_means'][:, b], color=colors[b], label=name)
    for b in range(4):
        for source in sources:
            ax.axhline(np.sqrt(source['covariance'][b, b])/source['mean'][b], color=colors[b], linestyle='--', alpha=.45, linewidth=.8)
    ax.set(xlabel='Runtime (s)', ylabel='Native q standard deviation / mean', title='Detail depth: dashed = both recorded-phase portions')
    ax.legend(fontsize=9)
    ax = axes[1, 1]
    paircolors = plt.get_cmap('tab10')(np.arange(6))
    for j, (b, c) in enumerate(pairs):
        ax.plot(times, corr[:, b, c], color=paircolors[j], label=f'{b+1}/{c+1}')
        ax.axhspan(source_corr[:, b, c].min(), source_corr[:, b, c].max(), color=paircolors[j], alpha=.05)
    ax.axhline(0, color='#888888', linewidth=.7)
    ax.set(xlabel='Runtime (s)', ylabel='Native q correlation', ylim=(-1.05, 1.05), title='ALL6 band pairs; shading = both source portions')
    ax.legend(ncol=3, fontsize=9)
    for ax in axes.flat: ax.grid(alpha=.15)
    fig.suptitle('Recorded-phase power law transferred to free modal oscillators: 180s\nFrozen coefficients; diagnostics only, no new synthesis or listening conclusion', fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, .94]); path = a.out/'transfer.png'; fig.savefig(path, dpi=140); plt.close(fig)
    r['images'].append(dict(file=path.name, sha256=sha(path)))
    fig, axes = plt.subplots(4, 1, figsize=(14, 11), sharex=True)
    t = (np.arange(180000)+.5)/1000
    for b, ax in enumerate(axes):
        # Every1ms sample is passed to the renderer; native samples are used for moments above.
        ax.plot(t, data['q_mean1ms'][:, b], color=colors[b], alpha=.45, linewidth=.3, rasterized=True)
        ax.plot(times, data['block_means'][:, b], color='#111111', linewidth=1., label='Native3s mean')
        reference = np.concatenate([s['q_mean1ms'][:, b] for s in sources]); lo, hi = np.quantile(reference, [.01, .99])
        ax.axhline(lo, color='#666666', linestyle='--', linewidth=.8); ax.axhline(hi, color='#666666', linestyle='--', linewidth=.8)
        ax.set_ylabel(labels[b]+'\nq'); ax.grid(alpha=.15); ax.set_xlim(0, 180)
    axes[0].legend(loc='upper right'); axes[-1].set_xlabel('Runtime (s)')
    fig.suptitle('ALL180000 one-millisecond q means per band (no sample selection)\nDashed: pooled source1ms q 1%/99%; NOT original waveform or audio loudness', fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, .94]); path = a.out/'all1ms.png'; fig.savefig(path, dpi=140); plt.close(fig)
    r['images'].append(dict(file=path.name, sha256=sha(path)))
    metrics = dict(pairs=pairs, source_correlations=source_corr.tolist(),
        block_correlations=corr.tolist(), pair_min=[float(corr[:, b, c].min()) for b, c in pairs],
        pair_max=[float(corr[:, b, c].max()) for b, c in pairs],
        block_coefficient_of_variation=(np.sqrt(np.diagonal(cov, axis1=1, axis2=2))/data['block_means']).tolist(),
        source_coefficient_of_variation=[(np.sqrt(np.diag(s['covariance']))/s['mean']).tolist() for s in sources],
        q_level_db_min=ratios.min(axis=0).tolist(), q_level_db_max=ratios.max(axis=0).tolist())
    save(a.out/'metrics.json', metrics)
    r.update(result='complete180s_phase_transfer_plots', input_report_sha256=sha(a.input/'report.json'),
             audit_sha256=sha(a.audit/'report.json'), metrics_sha256=sha(a.out/'metrics.json'),
             all60_blocks_and_all180000_1ms_samples=True, q_only_NOT_waveform=True)
except Exception as exc: r.update(result='failed', error=repr(exc)); raise
finally: save(a.out/'report.json', r)
print(r, flush=True)
