"""Summarize and plot measured native-time budgets, without audio candidates."""
import argparse
import csv
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'measure', 'audit', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    repo = Path(__file__).resolve().parents[1]
    for name in ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    a.out.mkdir(parents=True, exist_ok=False)
    m, audit = load(a.measure/'report.json'), load(a.audit/'report.json')
    assert audit['result'] == 'independent_native_stereo_budget_audit_passed'
    assert audit['producer_report_sha256'] == sha(a.measure/'report.json')
    shutil.copy2(__file__, a.out/'executed_review.py')
    plan = load(a.measure/'exact_sources/research/F3_local_detail_budget_v1_plan.json')
    bands = plan['measurement']['bands_hz']
    bandlabels = ['28-120', '120-400', '400-1.2k', '1.2-3k', '3-6k', '6-8k', '8-10k', '10-14k']
    labels = [row['label'].replace('_', ' ') for row in m['cases']]
    power, processed, sm, feasible, spread, correlation, rows = [], [], [], [], [], [], []
    for row in m['cases']:
        d = np.load(a.measure/row['label']/'measurement.npz')
        native = d['native_matrix']
        c = d['C_mean']
        p0 = native.diagonal(axis1=-2, axis2=-1).real.sum(axis=1)
        pc = c.diagonal(axis1=-2, axis2=-1).real.sum(axis=1)
        pr = d['processed_matrix'].diagonal(axis1=-2, axis2=-1).real.sum(axis=1)
        diff = 10*np.log10(pc/p0)
        transform = 10*np.log10(pr/p0)
        variation = np.array([v['C_minus_native_power_db'] for v in row['comparisons']])
        span = np.ptp(variation, axis=0).max(axis=1)
        pd = np.array([v['debt_positive_definite'] for v in row['comparisons']]).sum(axis=0)
        sdiff = np.array(row['C_mean']['side_mid_db'])-row['native']['side_mid_db']
        rho = np.array(row['C_mean']['complex_correlation'])-row['native']['complex_correlation']
        power.append(diff);processed.append(transform);sm.append(sdiff)
        feasible.append(pd);spread.append(span);correlation.append(np.linalg.norm(rho, axis=1))
        for j, (low, high) in enumerate(bands):
            rows.append(dict(case=row['label'], low_hz=low, high_hz=high,
                             C_minus_native_total_dB=float(diff[j]),
                             processed_minus_native_total_dB=float(transform[j]),
                             C_minus_native_side_mid_dB=float(sdiff[j]),
                             C_chunk_max_channel_span_dB=float(span[j]),
                             positive_debt_chunks=int(pd[j]), chunks=9,
                             mean_debt_positive=bool(row['mean_comparison']['debt_positive_definite'][j]),
                             mean_diagonal_debt_positive=bool(row['mean_comparison']['diagonal_debt_positive'][j])))
    power, processed, sm, feasible, spread, correlation = map(np.array, [power, processed, sm, feasible, spread, correlation])

    def heatmap(ax, values, title, vmin, vmax, cmap, fmt):
        im = ax.imshow(values, aspect='auto', vmin=vmin, vmax=vmax, cmap=cmap)
        ax.set(title=title, xticks=range(8), xticklabels=bandlabels, yticks=range(6), yticklabels=labels)
        ax.tick_params(axis='x', rotation=35)
        for j in range(6):
            for k in range(8):
                ax.text(k, j, format(values[j, k], fmt), ha='center', va='center', fontsize=8,
                        color='black', bbox=dict(facecolor='white', alpha=.65, edgecolor='none', pad=.5))
        return im

    fig, axes = plt.subplots(2, 2, figsize=(14, 9), layout='constrained')
    for ax, values, title, vmin, vmax, cmap, fmt in [
        (axes[0, 0], power, 'Generated minus native total power / dB', -9, 0, 'RdBu_r', '.1f'),
        (axes[0, 1], processed, 'Processed reference minus native / dB', -.12, .12, 'RdBu_r', '.2f'),
        (axes[1, 0], sm, 'Generated minus native side/mid ratio / dB', -6, 6, 'RdBu_r', '.1f'),
        (axes[1, 1], feasible, 'Positive-definite additive debt: chunks out of 9', 0, 9, 'YlGn', '.0f')]:
        fig.colorbar(heatmap(ax, values, title, vmin, vmax, cmap, fmt), ax=ax, shrink=.75)
    fig.suptitle('Six F3 local anchors: original-time stereo budgets\nShort apertures; no gain matching, widening, room model or new synthesis candidate')
    fig.savefig(a.out/'native_budget.png', dpi=150)
    plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(14, 5), layout='constrained')
    fig.colorbar(heatmap(axes[0], spread, 'Generated chunk span / dB (largest channel)', 0, 8, 'YlOrRd', '.1f'), ax=axes[0], shrink=.8)
    fig.colorbar(heatmap(axes[1], correlation, 'Complex L/R correlation distance', 0, .3, 'YlOrRd', '.2f'), ax=axes[1], shrink=.8)
    fig.suptitle('Same-length generated chunks: 3 seeds x 3 times\nModel variability, not uncertainty across independent source recordings')
    fig.savefig(a.out/'generated_spread.png', dpi=150)
    plt.close(fig)
    with (a.out/'bands.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)
    summary = dict(result='six_native_stereo_budget_plots_ready',
        measure_report_sha256=sha(a.measure/'report.json'), audit_report_sha256=sha(a.audit/'report.json'),
        cases=labels, bands_hz=bands,
        C_minus_native_total_dB=power.tolist(), processed_minus_native_total_dB=processed.tolist(),
        side_mid_difference_dB=sm.tolist(), positive_debt_chunks_out_of_nine=feasible.tolist(),
        generated_chunk_span_dB=spread.tolist(), complex_correlation_distance=correlation.tolist(),
        HF_3_to_14k_C_minus_native_band_extrema_dB=[float(power[:, 4:].min()), float(power[:, 4:].max())],
        mean_debt_PD_all_six_by_band=[all(row['mean_comparison']['debt_positive_definite'][j] for row in m['cases']) for j in range(8)],
        processed_native_max_band_abs_dB=float(abs(processed).max()),
        images={name: sha(a.out/name) for name in ['native_budget.png', 'generated_spread.png']},
        listening=False, new_audio_candidate=False, static_fit_qualifies_dynamic_detail=False)
    save(a.out/'report.json', summary)
    print(dict(result=summary['result'], HF_dB=summary['HF_3_to_14k_C_minus_native_band_extrema_dB'],
               max_processed_difference_dB=summary['processed_native_max_band_abs_dB']))


if __name__ == '__main__':
    main()
