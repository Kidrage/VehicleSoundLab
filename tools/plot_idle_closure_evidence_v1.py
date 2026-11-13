"""Complete source/control closure curves and both-coordinate runtime support."""
import argparse
import shutil
import sys
from pathlib import Path
p = argparse.ArgumentParser(description=__doc__)
for key in ['workspace', 'input', 'extension', 'audit', 'extension-audit', 'out']:
    p.add_argument('--'+key, type=Path, required=True)
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
    observed = load(a.input/'report.json'); extension = load(a.extension/'report.json')
    audit = load(a.audit/'report.json'); extra = load(a.extension_audit/'report.json')
    assert audit['result'] == 'all8_closure_501lag_curves_and180000_arc_decisions_verified'
    assert extra['result'] == 'all8_eta_501lag_curves_and180000_joint_decisions_verified'
    assert audit['input_report_sha256'] == extra['input_report_sha256'] == sha(a.input/'report.json')
    assert extra['extension_report_sha256'] == sha(a.extension/'report.json')
    fig, axes = plt.subplots(2, 3, figsize=(16, 9))
    for rowindex, (report, folder, name) in enumerate([(observed, a.input, 'psi = theta187 - theta112 - theta75'),
                                                    (extension, a.extension, 'eta = 3theta75 - 2theta112')]):
        for row in report['observations']:
            with np.load(folder/row['file']) as archive: data = {k: archive[k] for k in archive.files}
            source = row['group'] == 'source'; color = '#0c817b' if row['part'] == 'train' else '#9d3424'
            if not source: color = '#90949a'
            style = '-' if row['part'] == 'train' else '--'; alpha = 1. if source else .35
            label = ('F2 '+row['part']) if source else None
            edges = np.linspace(-np.pi, np.pi, 73); counts, _ = np.histogram(np.angle(data['closure']), bins=edges)
            axes[rowindex, 0].plot((edges[:-1]+edges[1:])/2, counts/len(data['closure']), color=color, linestyle=style, alpha=alpha, label=label)
            axes[rowindex, 1].plot(data['lags_frames']/48, data['residual_correlation'], color=color, linestyle=style, alpha=alpha, label=label)
            axes[rowindex, 2].plot(data['lags_frames']/48, data['phase_increment_second'], color=color, linestyle=style, alpha=alpha, label=label)
        axes[rowindex, 0].set(title=name+'\nNative phase histogram', xlabel='Principal phase (rad)', ylabel='Probability per fixed bin')
        axes[rowindex, 1].set(title='Detrended residual: ALL501lags', xlabel='Lag (ms)', ylabel='Correlation')
        axes[rowindex, 2].set(title='Raw phase increments: ALL501lags', xlabel='Lag (ms)', ylabel='Mean squared increment (rad^2)')
        for ax in axes[rowindex]: ax.grid(alpha=.16); ax.legend(fontsize=9)
    fig.suptitle('BOTH source portions and ALL3 same-PSD phase controls (grey), no excluded curve\nShort-record statistics do not identify long-run coupling or a mechanical clock', fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, .93]); path = a.out/'source_controls.png'; fig.savefig(path, dpi=140); plt.close(fig)
    r['images'].append(dict(file=path.name, sha256=sha(path)))
    with np.load(a.input/observed['runtime_arc_file']) as archive: base = {k: archive[k] for k in archive.files}
    with np.load(a.extension/extension['runtime_file']) as archive: more = {k: archive[k] for k in archive.files}
    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True); t = base['time_seconds']
    for ax, report, values, name in [(axes[0], observed, base, 'psi'), (axes[1], extension, more, 'eta')]:
        train = next(x for x in report['observations'] if x['label'] == 'source_train')
        d = np.angle(values['closure']*np.exp(-1j*train['circular_center_rad']))
        ax.plot(t, d, linewidth=.5, color='#0c817b'); ax.axhspan(*train['empirical_arc_rad'], color='#777777', alpha=.15)
        ax.set(ylabel=name+' relative to TRAIN center (rad)', ylim=(-3.3, 3.3))
    times = (np.arange(60)+.5)*3
    for key, values, label, color in [('inside_train_arc', base, 'psi arc', '#9d3424'),
                                      ('inside_train_arc', more, 'eta arc', '#5e67a9'),
                                      ('inside_joint_rectangle', more, 'Both arcs', '#0c817b')]:
        axes[2].plot(times, values[key].reshape(60, 3000).mean(axis=1), label=label, color=color)
    axes[2].axhline(extension['source_joint_check_coverage'], color='#333333', linestyle='--', label='F2 CHECK joint coverage')
    axes[2].set(ylabel='3s fraction within empirical arcs', xlabel='Runtime (s)', ylim=(-.03, 1.03)); axes[2].legend(ncol=2)
    for ax in axes:
        ax.axvspan(0, 12, color='#d59436', alpha=.12); ax.grid(alpha=.15); ax.set_xlim(0, 180)
    fig.suptitle('ALL180000fixed1ms centers: empirical TRAIN coordinate arcs (grey), first12s (gold)\nCoverage is descriptive, NOT a confidence region or audio quality score', fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, .93]); path = a.out/'joint_support.png'; fig.savefig(path, dpi=140); plt.close(fig)
    r['images'].append(dict(file=path.name, sha256=sha(path)))
    r.update(result='all_source_control_curves_and_joint_support_plotted', input_report_sha256=sha(a.input/'report.json'),
        extension_report_sha256=sha(a.extension/'report.json'), audit_sha256=sha(a.audit/'report.json'),
        extension_audit_sha256=sha(a.extension_audit/'report.json'), all16_portions_501lags=True,
        all180000_runtime_decisions=True)
except Exception as exc: r.update(result='failed', error=repr(exc)); raise
finally: save(a.out/'report.json', r)
print(r, flush=True)
