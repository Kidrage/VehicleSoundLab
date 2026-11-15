"""Plot all time-probe alternatives; no selection, tuning or listening promotion."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'study', 'audit', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(args.workspace/'tools/python_deps'))
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from conditional_phase_time_v1.metrics import comparisons, summarize
    repo = Path(__file__).resolve().parents[1]
    source = load(args.study/'report.json')
    audit = load(args.audit/'report.json')
    assert audit['result'] == 'independent_conditional_time_real_audit_passed'
    assert audit['producer_sha256'] == sha(args.study/'report.json')
    args.out.mkdir(parents=True, exist_ok=False)
    names = ['tools/review_conditional_phase_time_v1.py', 'tools/conditional_phase_time_v1/metrics.py']
    for name in names:
        target = args.out/'exact_sources'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo/name, target)
    rows = comparisons(source, args.study)
    summary = summarize(rows)
    save(args.out/'figure_inputs.json', rows)
    save(args.out/'summary.json', summary)
    variants = ('fixed', 'relative', 'parent', 'density', 'variation')
    labels = ['Fixed phase', 'Relative phase', 'Conditional parent', 'Density optimized', 'Gradient optimized']
    colors = ['#6c737f', '#a56628', '#b74349', '#3072a5', '#268663']
    def box(ax, field, title, ylabel, absolute=False):
        data = [np.concatenate([np.asarray(r[field]).ravel() for r in rows if r['variant'] == variant]) for variant in variants]
        if absolute:
            data = [abs(v) for v in data]
        parts = ax.boxplot(data, tick_labels=labels, patch_artist=True, showfliers=True, whis=(0, 100))
        for patch, color in zip(parts['boxes'], colors):
            patch.set_facecolor(color)
            patch.set_alpha(.55)
        ax.set(title=title, ylabel=ylabel)
        ax.tick_params(axis='x', labelrotation=16, labelsize=9)
        ax.grid(axis='y', alpha=.2)
        if field.endswith('_dB'):
            ax.axhline(0, color='#333333', lw=.7)
    plt.rcParams.update({'font.size': 11})
    fig, axes = plt.subplots(2, 2, figsize=(15, 9), layout='constrained')
    box(axes[0, 0], 'instantaneous_power_error_dB', 'Instantaneous coefficient power vs source lines', 'Signed error (dB)')
    box(axes[0, 1], 'reobserved_line_power_error_dB', 'Generated wave through original harmonic observer', 'Signed line-power error (dB)')
    box(axes[1, 0], 'line_to_instantaneous_power_dB', 'Projected line power / instantaneous coefficient power', 'Signed transfer (dB)')
    box(axes[1, 1], 'reobserved_broad_power_error_dB', 'Whole-band generated power vs whole-band source', 'Signed broadband-power error (dB)')
    fig.suptitle('Same amplitudes do not imply the same generated high-frequency energy\n6 sources × 3 seeds × 4 bands × 2 channels; all alternatives retained', fontsize=14)
    first = args.out/'conditional_time_power.png'
    fig.savefig(first, dpi=145)
    plt.close(fig)
    fig, axes = plt.subplots(2, 3, figsize=(19, 9), layout='constrained')
    box(axes[0, 0], 'instantaneous_coherence_error', 'Instantaneous complex stereo-coherence error', 'Absolute complex error')
    box(axes[0, 1], 'reobserved_line_coherence_error', 'Reobserved harmonic stereo-coherence error', 'Absolute complex error')
    box(axes[0, 2], 'matched_chunk_line_coherence_error', 'Same source-row-count chunks: harmonic stereo error', 'Absolute complex error')
    box(axes[1, 0], 'reobserved_broad_coherence_error', 'Whole-band stereo-coherence error', 'Absolute complex error')
    box(axes[1, 1], 'reobserved_broad_CV_error', 'Whole-band power variation (CV) error', 'Absolute CV error')
    box(axes[1, 2], 'matched_chunk_broad_CV_error', 'Same source-row-count chunks: whole-band CV error', 'Absolute CV error')
    chunk_count = summary['variants']['fixed']['matched_chunk_line_coherence_error']['count']
    fig.suptitle('Static distributional agreement must survive waveform generation\n'
                 f'72 full-trace / {chunk_count} chunk stereo coordinates per alternative; overlapping chunks are not independent trials', fontsize=14)
    second = args.out/'conditional_time_stereo.png'
    fig.savefig(second, dpi=145)
    plt.close(fig)
    save(args.out/'report.json', dict(result='conditional_time_figures_ready',
        sources={name:sha(repo/name) for name in names},
        inputs={str(args.study/'report.json'):sha(args.study/'report.json'), str(args.audit/'report.json'):sha(args.audit/'report.json')},
        images={p.name:sha(p) for p in (first, second)}, figure_inputs_sha256=sha(args.out/'figure_inputs.json'),
        summary_sha256=sha(args.out/'summary.json'), scientific_figures_individually_viewed=0))
    print(first)
    print(second)


if __name__ == '__main__':
    main()
