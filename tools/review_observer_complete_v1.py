"""Publish all six complete-record fits and every original-window regression."""
import argparse, os, shutil, sys
from pathlib import Path
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'root', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from observer_complete_v1.metrics import collect, summarize, VARIANTS
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    names = ('tools/review_observer_complete_v1.py', 'tools/observer_complete_v1/metrics.py')
    for name in names:
        dest = a.out/'exact_sources'/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo/name, dest)
    audit = load(a.root/'real_audit1/report.json')
    assert audit['result'] == 'independent_observer_complete_real_passed'
    assert audit['producer_sha256'] == sha(a.root/'real1/report.json')
    rows, solves, inputs = collect(a.root/'real1')
    summary = summarize(rows, solves)
    inputs[str(a.root/'real_audit1/report.json')] = sha(a.root/'real_audit1/report.json')
    save(a.out/'figure_inputs.json', rows)
    save(a.out/'solve_inputs.json', solves)
    save(a.out/'summary.json', summary)
    labels = ('Old interpolation', 'Old harmonic 4k', 'Old correction', 'New complete 4k')
    colors = ('#777777', '#bc693e', '#7d63a2', '#177f92')
    short = ('1 early', '1 mid', '1 late', '2 early', '2 mid', '2 late')
    x = np.arange(6)
    fig, axes = plt.subplots(1, 3, figsize=(17, 6), layout='constrained')
    axes[0].semilogy(x, [r['relative_stationarity'] for r in solves], 'o-', color=colors[-1], label='New complete 4k')
    axes[0].axhline(2e-7, color='#555555', ls='--', label='Gradient gate; stop also required')
    axes[0].set_title('All6 stop7 / 4000 iterations: not converged')
    axes[0].set_ylabel('Original-space relative gradient')
    for name, label, color in zip(VARIANTS, labels, colors):
        rr = [r for r in rows if r['variant'] == name]
        axes[1].semilogy(x, [r['wave_NRMSE'] for r in rr], 'o-', color=color, label=label)
        axes[2].semilogy(x, [r['wave_region_NRMSE'][1] for r in rr], 'o-', color=color, label=label)
    axes[1].set_title('All samples including first/last edges')
    axes[2].set_title('Interior excludes first/last2048 samples')
    axes[1].set_ylabel('Full-waveform NRMSE')
    axes[2].set_ylabel('Interior waveform NRMSE')
    for ax in axes:
        ax.set_xticks(x, short, rotation=25); ax.grid(alpha=.2); ax.legend(fontsize=8)
    fig.suptitle('NEW complete-data objective versus frozen harmonic-only baselines\nSix local samples of one V10; in-sample fits, not sustained sounds', fontsize=12)
    fig.savefig(a.out/'complete_waveform.png', dpi=145); plt.close(fig)
    fig, axes = plt.subplots(1, 3, figsize=(17, 6), layout='constrained')
    bands = ('0-3', '3-6', '6-8', '8-10', '10-14', '14-21.6')
    for name, label, color in zip(VARIANTS, labels, colors):
        rr = [r for r in rows if r['variant'] == name]
        data = (np.mean(abs(np.array([r['broad_power_error_dB'] for r in rr])), axis=(0, 2)),
                np.mean([r['broad_coherence_error'] for r in rr], axis=0),
                np.mean([r['broad_CV_error'] for r in rr], axis=(0, 2)))
        for ax, values in zip(axes, data):
            ax.plot(range(6), values, 'o-', color=color, label=label)
    for ax, title in zip(axes, ('Band-power MAE (dB)', 'Complex L/R error', 'Band-power CV error')):
        ax.set_xticks(range(6), bands, rotation=25); ax.set_xlabel('Band (kHz)')
        ax.set_ylabel(title); ax.grid(alpha=.2); ax.legend(fontsize=8)
    fig.suptitle('Original Hann4096/hop256 observer: retain all frequency-band regressions\nSmall global error does not establish weak-band, stereo or timbre fidelity', fontsize=12)
    fig.savefig(a.out/'complete_bands.png', dpi=145); plt.close(fig)
    report = dict(result='observer_complete_review_ready', rows=24, solves=6, inputs=inputs,
        sources={n: sha(repo/n) for n in names},
        images={n: sha(a.out/n) for n in ('complete_waveform.png', 'complete_bands.png')},
        figure_inputs_sha256=sha(a.out/'figure_inputs.json'),
        solve_inputs_sha256=sha(a.out/'solve_inputs.json'), summary_sha256=sha(a.out/'summary.json'))
    save(a.out/'report.json', report)
    print(report['result'], flush=True)


if __name__ == '__main__':
    main()
