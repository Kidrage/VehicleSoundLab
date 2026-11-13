"""Display every placement/block/band comparison, including MC uncertainty."""
import argparse
import shutil
import sys
from pathlib import Path
p = argparse.ArgumentParser(description=__doc__)
for key in ['workspace', 'input', 'audit', 'out']: p.add_argument('--'+key, type=Path, required=True)
a = p.parse_args(); sys.path.insert(0, str(a.workspace/'tools/python_deps'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from research_archive_v1 import load, save, sha

a.out.mkdir(parents=True, exist_ok=False); shutil.copy2(__file__, a.out/'executed_plot.py')
r = load(a.input/'report.json'); audit = load(a.audit/'report.json')
assert audit['result'] == 'all64paired_renders_known_and_crossseed_statistics_verified'
assert audit['input_report_sha256'] == sha(a.input/'report.json')
with np.load(a.input/'powers.npz') as data: target = data['target']
fig, axes = plt.subplots(2, 2, figsize=(15, 9.5), constrained_layout=True)
fig.suptitle('Idle detail: amplitude before / after resonant FIR | 64 paired Gaussian seeds\n'
             '1 ms conditional-power diagnostic; finite-ensemble intervals; no hearing claim', fontsize=14)
band = ['1.2-2.2', '2.2-4', '4-8', '8-14']
x = np.arange(8); labels = [f'{b}\nB{k}' for k in range(2) for b in band]
for placement, color, offset in [('pre', '#bc5a3a', -.13), ('post', '#187b8c', .13)]:
    rows = [next(z for z in r['observations'] if z['block'] == k and z['placement'] == placement) for k in range(2)]
    values = np.array([z['point'][4:8] for z in rows]).ravel()
    errors = np.array([np.array(z['high'][4:8])-z['point'][4:8] for z in rows]).ravel()
    axes[0, 0].errorbar(x+offset, values, yerr=errors, fmt='o', capsize=3, color=color, label=placement.upper())
    corr = np.array([z['point'][8:12] for z in rows]).ravel()
    errors = np.array([np.array(z['high'][8:12])-z['point'][8:12] for z in rows]).ravel()
    axes[0, 1].errorbar(x+offset, corr, yerr=errors, fmt='o', capsize=3, color=color, label=placement.upper())
    mean = np.array([z['point'][:4] for z in rows]).ravel()
    errors = np.array([np.array(z['high'][:4])-z['point'][:4] for z in rows]).ravel()
    axes[1, 1].errorbar(x+offset, mean, yerr=errors, fmt='o', capsize=3, color=color, label=placement.upper())
axes[0, 0].set_yscale('log'); axes[0, 0].set_title('Squared error vs generated q (pointwise 95% MC intervals)')
axes[0, 1].set_title('Correlation with own q (bias-corrected variance estimate)')
axes[1, 1].set_title('Mean detail power / frozen unit-input reference')
axes[1, 1].axhline(1, color='gray', linewidth=.7)
for ax in [axes[0, 0], axes[0, 1], axes[1, 1]]:
    ax.set_xticks(x, labels); ax.grid(alpha=.18); ax.legend()
pairlabels = ['1/2', '1/3', '1/4', '2/3', '2/4', '3/4']
for block, style in [(0, '-'), (1, '--')]:
    selection = slice(block*3000+100, (block+1)*3000-100)
    matrix = np.corrcoef(target[selection], rowvar=False)
    guide = [matrix[b, c] for b in range(4) for c in range(b+1, 4)]
    axes[1, 0].plot(np.arange(6), guide, style, color='black', alpha=.65, label=f'q B{block}')
    for placement, color in [('pre', '#bc5a3a'), ('post', '#187b8c')]:
        row = next(z for z in r['observations'] if z['block'] == block and z['placement'] == placement)
        axes[1, 0].errorbar(np.arange(6), row['point'][12:],
                         yerr=np.array(row['high'][12:])-row['point'][12:], fmt='o'+style, color=color,
                         capsize=2, label=f'{placement.upper()} B{block}')
axes[1, 0].set_xticks(np.arange(6), pairlabels)
axes[1, 0].axhline(0, color='gray', linewidth=.7); axes[1, 0].grid(alpha=.18)
axes[1, 0].set_title('All six conditional-power pairs (bands numbered above)')
axes[1, 0].legend(ncol=3, fontsize=9, loc='lower right')
image = a.out/'placement_all_bands.png'; fig.savefig(image, dpi=145); plt.close(fig)
reductions = []
for block in range(2):
    pre = next(z for z in r['observations'] if z['block'] == block and z['placement'] == 'pre')
    post = next(z for z in r['observations'] if z['block'] == block and z['placement'] == 'post')
    reductions.append((1-np.asarray(post['point'][4:8])/pre['point'][4:8]).tolist())
save(a.out/'report.json', dict(result='all8cells_and_all6pairs_plotted', input_report_sha256=sha(a.input/'report.json'),
                              audit_sha256=sha(a.audit/'report.json'), images=[dict(file=image.name, sha256=sha(image))],
                              mse_relative_reductions=reductions, pre_exact_coverage=r['all_pointwise_pre_coverage']))
print(dict(result='plot_complete', reductions=reductions), flush=True)
