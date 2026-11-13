"""Complete finite lag curves: all seeds/blocks, source portions, no chosen trace."""
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

a.out.mkdir(parents=True, exist_ok=False); shutil.copy2(__file__, a.out/'executed_plot.py')
r = dict(result='running', images=[])
try:
    observed = load(a.input/'report.json'); audit = load(a.audit/'report.json')
    assert audit['result'] == 'passed' and audit['input_report_sha256'] == sha(a.input/'report.json')
    records = {}
    for row in observed['observations']:
        assert sha(a.input/row['file']) == row['sha256']
        with np.load(a.input/row['file']) as z: records[row['label']] = z['normalized']
    pairs = [(b, c) for b in range(4) for c in range(b, 4)]
    labels = ['1.2-2.2', '2.2-4', '4-8', '8-14']; lags = np.arange(-40, 41)
    colors = dict(static='#748493', sparse='#ba7c22', post='#007f78')
    names = dict(static='Static Gaussian', sparse='Old sparse', post='POST + allocated sparse')
    source = [records[x] for x in ['training', 'check']]
    arrays = {method: np.array([records[z['label']] for z in observed['observations'] if z.get('method') == method])
              for method in colors}
    assert all(x.shape == (12, 10, 81) for x in arrays.values())
    for kind, indices in [('auto', [j for j, (b, c) in enumerate(pairs) if b == c]),
                          ('cross', [j for j, (b, c) in enumerate(pairs) if b != c])]:
        fig, axes = plt.subplots(len(indices)//2, 2, figsize=(14, 4*len(indices)//2), squeeze=False)
        for ax, j in zip(axes.flat, indices):
            for method in colors:
                ax.plot(lags, arrays[method][:, j, :].T, color=colors[method], alpha=.16, linewidth=.7)
                ax.plot(lags, arrays[method][:, j, :].mean(axis=0), color=colors[method], linewidth=1.6, label=names[method])
            ax.plot(lags, source[0][j], color='#111111', linewidth=1.5, label='F2 TRAIN 6-9s')
            ax.plot(lags, source[1][j], color='#555555', linestyle='--', linewidth=1.3, label='F2 check 9-12s')
            b, c = pairs[j]; ax.set_title(f'{labels[b]} / {labels[c]} kHz')
            ax.axhline(0, color='#999999', linewidth=.6); ax.set_xlabel('Lag (ms)'); ax.set_ylabel('Normalized fourth cumulant')
            ax.grid(alpha=.18); ax.set_xlim(-40, 40)
        handles, legend = axes.flat[0].get_legend_handles_labels()
        fig.legend(handles, legend, loc='lower center', ncol=3, fontsize=9)
        fig.suptitle(f'Idle finite audio: {kind} curves | thin = ALL 3 seeds x 4 blocks; thick = mean\nEmpirical audio statistics, NOT theoretical expectations or listening acceptance', fontsize=13)
        fig.tight_layout(rect=[0, .065, 1, .94]); path = a.out/(kind+'.png'); fig.savefig(path, dpi=140); plt.close(fig)
        r['images'].append(dict(file=path.name, sha256=sha(path)))
    # Descriptive distances to EACH source, retaining all12 windows and81lags; not a pass/fail score.
    metrics = {}
    mask = (abs(lags) >= 8) & (abs(lags) <= 20)
    for method, data in arrays.items():
        metrics[method] = dict(zero_mean=data[:, :, 40].mean(axis=0).tolist(),
            zero_min=data[:, :, 40].min(axis=0).tolist(), zero_max=data[:, :, 40].max(axis=0).tolist(),
            late_means=data[:, :, mask].mean(axis=(0, 2)).tolist(),
            RMSE_each_window_to_each_source=[np.sqrt(np.mean((data-x[None, :, :])**2, axis=2)).tolist() for x in source])
    save(a.out/'metrics.json', dict(pairs=pairs, source_zero=[x[:, 40].tolist() for x in source], methods=metrics))
    r.update(result='all38_finite_audio_curves_plotted', input_report_sha256=sha(a.input/'report.json'),
             audit_sha256=sha(a.audit/'report.json'), metrics_sha256=sha(a.out/'metrics.json'),
             all36_generated_curves_shown_per_pair=True, no_statistical_or_hearing_acceptance=True)
except Exception as exc: r.update(result='failed', error=repr(exc)); raise
finally: save(a.out/'report.json', r)
print(r, flush=True)
