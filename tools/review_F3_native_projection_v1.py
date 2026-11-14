"""Plot why a conditional native remainder cannot be an independent detail bus."""
import argparse
import csv
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'study', 'audit', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import SymLogNorm
    a.out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, a.out/'executed_review.py')
    m, audit = load(a.study/'report.json'), load(a.audit/'report.json')
    assert audit['result'] == 'independent_native_projection_audit_passed'
    assert audit['producer_report_sha256'] == sha(a.study/'report.json')
    bandlabels = ['28-120', '120-400', '400-1.2k', '1.2-3k', '3-6k', '6-8k', '8-10k', '10-14k']
    labels = [r['label'].replace('_', ' ') for r in m['cases']]
    source, generated, rows = [], [], []
    trace = lambda v: v.diagonal(axis1=-2, axis2=-1).real.sum(axis=-1)
    for row in m['cases']:
        for suffix, output in [('source', source), ('C', generated)]:
            d = np.load(a.study/(row['label']+'_'+suffix)/'arrays.npz')
            p0 = trace(d['P_full'].mean(axis=(0, 1)))
            ph = trace(d['P_harmonic'].mean(axis=(0, 1)))
            pr = trace(d['P_remainder'].mean(axis=(0, 1)))
            cross = trace(d['cross_HR_RH'].mean(axis=(0, 1)))
            ratio = np.stack([ph/p0, pr/p0, cross/p0])
            assert np.allclose(ratio.sum(axis=0), 1, atol=1e-11, rtol=1e-11)
            output.append(ratio)
            for b in range(8):
                rows.append(dict(case=row['label'], route=suffix, band=bandlabels[b],
                                 harmonic_full_power_ratio=float(ratio[0, b]),
                                 remainder_full_power_ratio=float(ratio[1, b]),
                                 signed_cross_full_power_ratio=float(ratio[2, b])))
    source, generated = np.array(source), np.array(generated)
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.7), layout='constrained')
    panels = [(10*np.log10(source[:, 0]), 'Harmonic / original power, dB', dict(vmin=-25, vmax=16, cmap='RdBu_r'), '.1f'),
              (10*np.log10(source[:, 1]), 'Remainder / original power, dB', dict(vmin=-25, vmax=16, cmap='RdBu_r'), '.1f'),
              (source[:, 2], 'Signed H/R cross / original power', dict(norm=SymLogNorm(linthresh=.05, vmin=-64, vmax=64), cmap='RdBu_r'), '.2f')]
    for ax, (values, title, colors, fmt) in zip(axes, panels):
        im = ax.imshow(values, aspect='auto', **colors)
        ax.set(title=title, xticks=range(8), xticklabels=bandlabels, yticks=range(6), yticklabels=labels)
        ax.tick_params(axis='x', rotation=45)
        for j in range(6):
            for k in range(8):
                ax.text(k, j, format(values[j, k], fmt), ha='center', va='center', fontsize=8,
                        bbox=dict(facecolor='white', edgecolor='none', alpha=.7, pad=.5))
        fig.colorbar(im, ax=ax, shrink=.75)
    fig.suptitle('Native projection: original = harmonic + remainder + signed cross\nWhole-aperture orthogonality does not imply per-band independence; no audio candidate')
    fig.savefig(a.out/'native_cross_budget.png', dpi=150)
    plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8), layout='constrained')
    captured, names = [], []
    for row in m['known']:
        if row['label'].startswith('known_white_mix_'):
            d = np.load(a.study/row['label']/'arrays.npz')
            harmonic_noise = d['noise']-d['remainder']
            captured.append(float(np.sum(harmonic_noise**2)/np.sum(d['noise']**2)))
            names.append(row['label'].removeprefix('known_white_mix_'))
    axes[0].bar(names, np.array(captured)*100)
    axes[0].axhline(577/10500*100, ls='--', color='black', label='rank / sample count expectation')
    axes[0].set(title='White noise also enters harmonic projection', ylabel='Projected noise power / total noise (%)', xlabel='All four declared seeds')
    axes[0].legend(fontsize=8)
    for j, label in enumerate(labels):
        axes[1].plot(range(4), 10*np.log10(source[j, 1, 4:]), marker='o', label=label)
    axes[1].axhline(0, ls='--', color='black', label='Remainder power equals original')
    axes[1].set(title='Source high-band remainder may exceed original', ylabel='Remainder / original power (dB)',
                xticks=range(4), xticklabels=bandlabels[4:])
    axes[1].legend(fontsize=8, ncol=2)
    fig.suptitle('Known AM sidebands and finite noise projection prevent a physical-noise interpretation')
    fig.savefig(a.out/'projection_limits.png', dpi=150)
    plt.close(fig)
    with (a.out/'bands.csv').open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    r = dict(result='native_projection_limits_plotted', producer_report_sha256=sha(a.study/'report.json'),
             audit_report_sha256=sha(a.audit/'report.json'),
             source_ratios_H_R_cross=source.tolist(), C_ratios_H_R_cross=generated.tolist(),
             maximum_HF_source_remainder_full_ratio=float(source[:, 1, 4:].max()),
             minimum_HF_source_signed_cross_full_ratio=float(source[:, 2, 4:].min()),
             captured_white_noise_power_fractions=captured,
             images={name: sha(a.out/name) for name in ['native_cross_budget.png', 'projection_limits.png']},
             numerical_projection_verified=True, independent_detail_target_qualified=False,
             no_strength_or_clock_rescue=True, no_new_audio_candidate=True)
    save(a.out/'report.json', r)
    print({k: v for k, v in r.items() if k.startswith(('maximum_', 'minimum_', 'result'))})


if __name__ == '__main__':
    main()
