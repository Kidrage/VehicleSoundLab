"""All-variant origin heatmaps and signed paired changes; no new sound preset."""
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
    from carrier_transfer_v1.metrics import collect, summarize
    repo = Path(__file__).resolve().parents[1]
    source = load(args.study/'report.json')
    audit = load(args.audit/'report.json')
    assert audit['result'] == 'independent_carrier_transfer_real_passed'
    assert audit['producer_sha256'] == sha(args.study/'report.json')
    args.out.mkdir(parents=True, exist_ok=False)
    names = ['tools/review_carrier_transfer_v1.py', 'tools/carrier_transfer_v1/metrics.py']
    for name in names:
        dest = args.out/'exact_sources'/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo/name, dest)
    parent = args.workspace/'baselines/conditional_phase_time_v1/evidence/real1'
    rows = collect(source, args.study, parent)
    summary, pairs = summarize(rows)
    save(args.out/'figure_inputs.json', rows)
    save(args.out/'paired_inputs.json', pairs)
    save(args.out/'summary.json', summary)
    variants = ('fixed', 'relative', 'parent', 'density', 'variation')
    labels = ['Fixed phase', 'Relative phase', 'Conditional parent', 'Density optimized', 'Gradient optimized']
    heat = [10*np.log10(np.maximum(summary['variants'][name]['broad_median_group_self_over_reference'], 1e-30)).T for name in variants]
    minimum, maximum = min(x.min() for x in heat), max(x.max() for x in heat)
    plt.rcParams.update({'font.size':11})
    fig, axes = plt.subplots(1, 5, figsize=(20, 5.5), layout='constrained', sharey=True)
    for ax, value, label in zip(axes, heat, labels):
        picture = ax.imshow(value, vmin=minimum, vmax=maximum, cmap='viridis', aspect='auto')
        for y in range(6):
            for x in range(4):
                ax.text(x, y, f'{value[y,x]:.1f}', ha='center', va='center', fontsize=8,
                        color='white' if value[y,x] < (minimum+maximum)/2 else 'black')
        ax.set_title(label)
        ax.set_xticks(range(4), ['3–6','6–8','8–10','10–14'], rotation=25)
        ax.set_xlabel('Output band (kHz)')
        ax.set_yticks(range(6), ['<3','3–6','6–8','8–10','10–14','≥14'])
    axes[0].set_ylabel('Nominal carrier-origin group (kHz)')
    fig.colorbar(picture, ax=axes, label='Group self-power / original total band power (dB)', shrink=.85)
    fig.suptitle('Where generated high-frequency energy originates\nMedian across 6 sources × 3 seeds × 2 channels; cross-group terms kept separately', fontsize=14)
    one = args.out/'carrier_origin_power.png'
    fig.savefig(one, dpi=145)
    plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(15, 6), layout='constrained')
    chosen = [row for row in pairs if row['variant'] == 'variation']
    fields = ['low_power', 'rest_power', 'signed_low_rest_cross', 'total_power']
    colors = ['#b87928', '#2d76a3', '#864aa1', '#26835a']
    for ax, prefix in zip(axes, ('line', 'broad')):
        values = [np.asarray([row[prefix+'_'+field+'_over_reference'] for row in chosen]).ravel() for field in fields]
        artists = ax.boxplot(values, tick_labels=['<3k carriers', 'All other carriers', 'Signed low/rest cross', 'Total'], patch_artist=True, whis=(0,100))
        for patch, color in zip(artists['boxes'], colors):
            patch.set_facecolor(color)
            patch.set_alpha(.55)
        ax.set_yscale('symlog', linthresh=.01)
        ax.axhline(0, color='#333333', lw=.8)
        ax.grid(axis='y', alpha=.2)
        ax.set_title('Harmonic projection' if prefix == 'line' else 'Whole-band waveform')
        ax.set_ylabel('Signed change / original source band power')
        ax.tick_params(axis='x', labelrotation=15, labelsize=9)
    fig.suptitle('Gradient-optimized minus relative-phase waveform: retain the signed energy identity\n144 paired band/channel coordinates; ranges are not confidence intervals or physical source fractions', fontsize=14)
    two = args.out/'carrier_signed_changes.png'
    fig.savefig(two, dpi=145)
    plt.close(fig)
    inputs = {str(args.study/'report.json'):sha(args.study/'report.json'), str(args.audit/'report.json'):sha(args.audit/'report.json')}
    for case in source['cases']:
        path = parent/case['label']/'source.npz'
        inputs[str(path)] = sha(path)
    save(args.out/'report.json', dict(result='carrier_transfer_figures_ready', sources={name:sha(repo/name) for name in names},
        inputs=inputs, images={p.name:sha(p) for p in (one,two)}, figure_inputs_sha256=sha(args.out/'figure_inputs.json'),
        paired_inputs_sha256=sha(args.out/'paired_inputs.json'), summary_sha256=sha(args.out/'summary.json')))
    print(one)
    print(two)


if __name__ == '__main__':
    main()
