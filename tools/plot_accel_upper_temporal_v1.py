"""Show all original passages and all phase controls, without seed selection."""
import argparse, shutil, sys
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

audit = load(a.audit / 'report.json')
assert audit['result'] == 'all12_temporal_observations_independently_verified'
assert audit['input_report_sha256'] == sha(a.input / 'report.json')
report = load(a.input / 'report.json')
a.out.mkdir(parents=True, exist_ok=False)
shutil.copy2(__file__, a.out / 'executed_plot.py')
fig, axes = plt.subplots(2, 3, figsize=(14, 7), layout='constrained')
for column, row in enumerate(report['observations']):
    labels = ['Original'] + [str(v['seed']) for v in row['controls']]
    stats = [row['original']] + [v['statistics'] for v in row['controls']]
    for b, (name, color) in enumerate([('4-8kHz', '#0d9488'), ('8-14kHz', '#c26a27')]):
        x = np.arange(4) + (b - .5) * .34
        axes[0, column].bar(x, [v['moments']['excess'][b] for v in stats], width=.32, color=color, label=name)
        axes[1, column].bar(x, [v['energy_CV'][b] for v in stats], width=.32, color=color, label=name)
    axes[0, column].set(title=row['segment'], ylabel='Sample excess kurtosis')
    axes[1, column].set(ylabel='10ms band-energy CV')
    for ax in axes[:, column]:
        ax.set_xticks(np.arange(4), labels, rotation=20)
        ax.axhline(0, color='#65758b', linewidth=.7)
        ax.grid(axis='y', alpha=.2)
        ax.legend(fontsize=8)
fig.suptitle('Original F3 temporal concentration versus every same-PSD phase control\nMixed recording statistics; not identified engine events or a generator', fontsize=12)
path = a.out / 'upper_temporal_all_controls.png'
fig.savefig(path, dpi=150)
plt.close(fig)
save(a.out / 'report.json', dict(result='all3_originals_and9_phase_controls_plotted',
    input_report_sha256=sha(a.input / 'report.json'), audit_sha256=sha(a.audit / 'report.json'),
    image_sha256=sha(path), observations=12))
