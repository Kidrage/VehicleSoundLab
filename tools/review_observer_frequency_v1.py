"""Publish all real/known frequency-metric outcomes; no listening or runtime claim."""
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
    from observer_frequency_v1.metrics import collect, summarize, VARIANTS
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    names = ('tools/review_observer_frequency_v1.py', 'tools/observer_frequency_v1/metrics.py',
        'tools/observer_complete_v1/metrics.py')
    for name in names:
        dest = a.out/'exact_sources'/name
        dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(repo/name, dest)
    known = load(a.root/'known1/report.json'); ka = load(a.root/'known_audit1/report.json')
    audit = load(a.root/'real_audit1/report.json')
    assert known['result'] == 'observer_frequency_known_ready'
    assert ka['result'] == 'independent_observer_frequency_known_passed' and ka['producer_sha256'] == sha(a.root/'known1/report.json')
    assert audit['result'] == 'independent_observer_frequency_real_passed' and audit['producer_sha256'] == sha(a.root/'real1/report.json')
    rows, solves, inputs = collect(a.root/'real1'); summary = summarize(rows, solves)
    for name in ('known1', 'known_audit1', 'real_audit1'):
        inputs[str(a.root/name/'report.json')] = sha(a.root/name/'report.json')
    save(a.out/'figure_inputs.json', rows); save(a.out/'solve_inputs.json', solves)
    save(a.out/'known_inputs.json', known['cases']); save(a.out/'summary.json', summary)
    labels = ('Interpolation', 'Old harmonic4k', 'Old correction', 'Global wave4k', 'Shared metric4k')
    colors = ('#888888', '#bd7045', '#8865a3', '#29769d', '#308452')
    x = np.arange(6); short = ('1 early', '1 mid', '1 late', '2 early', '2 mid', '2 late')
    fig, axes = plt.subplots(1, 3, figsize=(17, 6), layout='constrained')
    for law, style in (('constant', '--'), ('curved', '-')):
        cases = sorted((r for r in known['cases'] if r['law'] == law), key=lambda r: r['weak_amplitude'])
        for tag, label, color in (('global_wave', 'Exact global', colors[3]), ('weighted_frame', 'Exact shared', colors[4])):
            axes[0].loglog([r['weak_amplitude'] for r in cases], [r['variants'][tag]['high_component_NRMSE'] for r in cases],
                'o'+style, color=color, label=label+' / '+law)
    axes[0].set_xlabel('Known high-component amplitude')
    axes[0].set_ylabel('Known high-component waveform NRMSE')
    axes[0].set_title('Known exact solutions: objective bias exists')
    for tag, label, color in zip(VARIANTS, labels, colors):
        rr = [r for r in rows if r['variant'] == tag]
        axes[1].semilogy(x, [r['wave_NRMSE'] for r in rr], 'o-', color=color, label=label)
    axes[1].set_xticks(x, short, rotation=25); axes[1].set_ylabel('Full waveform NRMSE')
    axes[1].set_title('All source samples, including fragment edges')
    axes[2].semilogy(x, [r['relative_stationarity'] for r in solves], 'o-', color=colors[4], label='Shared metric4k')
    axes[2].axhline(2e-7, ls='--', color='#555555', label='Gradient gate; stop also required')
    axes[2].set_xticks(x, short, rotation=25); axes[2].set_ylabel('Original-space relative gradient')
    axes[2].set_title('Solver termination is a separate requirement')
    for ax in axes: ax.grid(alpha=.2); ax.legend(fontsize=7)
    fig.suptitle('Shared complete-frequency fitting: known examples and all6 frozen V10 samples\nIn-sample diagnosis; not a sustained source, native48k result or listening score', fontsize=12)
    fig.savefig(a.out/'frequency_known_and_wave.png', dpi=145); plt.close(fig)
    fig, axes = plt.subplots(1, 3, figsize=(17, 6), layout='constrained')
    bands = ('0-3', '3-6', '6-8', '8-10', '10-14', '14-21.6')
    for tag, label, color in zip(VARIANTS, labels, colors):
        rr = [r for r in rows if r['variant'] == tag]
        data = (np.mean(abs(np.array([r['broad_power_error_dB'] for r in rr])), axis=(0, 2)),
                np.mean([r['broad_coherence_error'] for r in rr], axis=0),
                np.mean([r['broad_CV_error'] for r in rr], axis=(0, 2)))
        for ax, values in zip(axes, data): ax.plot(range(6), values, 'o-', color=color, label=label)
    for ax, title in zip(axes, ('Band-power MAE (dB)', 'Complex L/R error', 'Band-power CV error')):
        ax.set_xticks(range(6), bands, rotation=25); ax.set_xlabel('Band (kHz)')
        ax.set_ylabel(title); ax.grid(alpha=.2); ax.legend(fontsize=7)
    fig.suptitle('Original Hann4096/hop256 observer: all frequency bands and stereo/CV regressions retained\nOne fixed metric rule across sources; no per-band winners or gain normalization', fontsize=12)
    fig.savefig(a.out/'frequency_bands.png', dpi=145); plt.close(fig)
    report = dict(result='observer_frequency_review_ready', rows=30, solves=6, known_cases=6, inputs=inputs,
        sources={n: sha(repo/n) for n in names},
        images={n: sha(a.out/n) for n in ('frequency_known_and_wave.png', 'frequency_bands.png')},
        **{key+'_sha256': sha(a.out/(key+'.json')) for key in ('figure_inputs', 'solve_inputs', 'known_inputs', 'summary')})
    save(a.out/'report.json', report); print(report['result'], flush=True)


if __name__ == '__main__':
    main()
