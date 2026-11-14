"""Publish conditional region coverage and untouched full-band stereo envelopes."""
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
    a.out.mkdir(parents=True, exist_ok=False);shutil.copy2(__file__, a.out/'executed_review.py')
    m, audit = load(a.study/'report.json'), load(a.audit/'report.json')
    assert audit['result'] == 'independent_native_regions_audit_passed'
    assert audit['producer_report_sha256'] == sha(a.study/'report.json')
    labels = [row['label'].replace('_', ' ') for row in m['cases']]
    bandlabels = ['28-120', '120-400', '400-1.2k', '1.2-3k', '3-6k', '6-8k', '8-10k', '10-14k']
    trace = lambda v: v.diagonal(axis1=-2, axis2=-1).real.sum(axis=-1)
    fractions, gaps, differences, rows, full_features = [], [], [], [], []
    fig_env, axes_env = plt.subplots(2, 3, figsize=(14, 7), layout='constrained')
    for index, row in enumerate(m['cases']):
        source = np.load(a.study/row['source']['label']/'arrays.npz')
        c = np.load(a.study/row['C']['label']/'arrays.npz')
        mean = source['P_regions'].mean(axis=(0, 1))
        power = trace(mean)
        f = power/power.sum(axis=1)[:, None]
        counts = source['region_bin_counts'][:, :, 1].sum(axis=0)
        fractions.append(f);gaps.append(counts)
        p0, pc = source['P_total'].mean(axis=(0, 1)), c['P_total'].mean(axis=(0, 1))
        difference = 10*np.log10(trace(pc)/trace(p0));differences.append(difference)
        for band in range(8):
            rows.append(dict(case=row['label'], band=bandlabels[band],
                             interline_bins_over_windows=int(counts[band]),
                             neighborhood_energy_fraction=float(f[band, 0]), interline_energy_fraction=float(f[band, 1]),
                             overlap_energy_fraction=float(f[band, 2]), unsupported_energy_fraction=float(f[band, 3]),
                             full_C_minus_native_dB=float(difference[band])))
        # Retain full-band joint observations even where line/interline cannot
        # be separated. This receipt is not a synthesis preset or fitted law.
        total = source['P_total'][0]
        full_features.append(dict(label=row['label'], stereo_power_LR=total.diagonal(axis1=-2, axis2=-1).real.tolist(),
                                  cross_L_conjR_real_imag=np.stack([total[:, :, 0, 1].real, total[:, :, 0, 1].imag], axis=-1).tolist(),
                                  native_window_times=source['window_times'].tolist(),
                                  region_bin_counts=source['region_bin_counts'].tolist(),
                                  mean_power_matrix_real=p0.real.tolist(), mean_power_matrix_imag=p0.imag.tolist()))
        native_hf = trace(total[:, 4:].sum(axis=1))
        generated_hf = trace(c['P_total'][:, :, 4:].sum(axis=2))
        level = native_hf.mean();times = (source['window_starts']+2048)/48000
        ax = axes_env.flat[index]
        ax.fill_between(times, 10*np.log10(generated_hf.min(axis=0)/level), 10*np.log10(generated_hf.max(axis=0)/level), alpha=.2, color='tab:orange', label='9C chunk range')
        ax.plot(times, 10*np.log10(generated_hf.mean(axis=0)/level), '--', color='tab:orange', label='C mean')
        ax.plot(times, 10*np.log10(native_hf/level), '-o', markersize=3, color='tab:blue', label='native')
        ax.set(title=labels[index], xlabel='Time within original aperture / s', ylabel='3-14kHz power / native mean, dB')
        ax.grid(alpha=.2);ax.legend(fontsize=7)
    fig_env.suptitle('Full-band short-window envelopes retained without residual subtraction\nSource changes pitch; C is stationary. Chunk range is model variability, not confidence across recordings.')
    fig_env.savefig(a.out/'full_band_envelopes.png', dpi=150);plt.close(fig_env)
    fractions, gaps = np.array(fractions), np.array(gaps)
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.5), layout='constrained')
    for ax, values, title, vmax, fmt in [
        (axes[0], gaps, 'Clean interline bin count across source windows', 320, '.0f'),
        (axes[1], 100*fractions[:, :, 2], 'Overlap / unresolved source energy, %', 100, '.1f')]:
        im = ax.imshow(values, aspect='auto', vmin=0, vmax=vmax, cmap='YlOrRd')
        ax.set(title=title, xticks=range(8), xticklabels=bandlabels, yticks=range(6), yticklabels=labels)
        ax.tick_params(axis='x', rotation=45)
        for j in range(6):
            for k in range(8):
                ax.text(k, j, format(values[j, k], fmt), ha='center', va='center', fontsize=8,
                        bbox=dict(facecolor='white', edgecolor='none', alpha=.7, pad=.5))
        fig.colorbar(im, ax=ax, shrink=.75)
    known = np.load(a.study/'known_slow_AM/arrays.npz');window = .5-.5*np.cos(2*np.pi*np.arange(4096)/4096)
    expected = np.array([np.average(known['known_envelope'][s:s+4096]**2, weights=window**2) for s in known['window_starts']])*.13**2/2
    measured = known['P_total'][0, :, 6, 0, 0].real
    times = (known['window_starts']+2048)/48000
    axes[2].plot(times, expected, color='black', label='exact weighted envelope')
    axes[2].plot(times, measured, '.', color='tab:cyan', markersize=3, label='native band measurement')
    axes[2].set(title='Known4Hz AM: full8-10kHz band', xlabel='Time / s', ylabel='L power / FS squared')
    axes[2].legend(fontsize=8);axes[2].grid(alpha=.2)
    fig.suptitle('Native frequency regions: zero clean-gap bins means unresolved, not absence of noise\nConditional on frozen clock and declared Hann support; no new synthesis candidate')
    fig.savefig(a.out/'regions_and_control.png', dpi=150);plt.close(fig)
    with (a.out/'bands.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    save(a.out/'full_band_observations.json', dict(schema='vsl.native-stereo-band-observation/1',
        kind='observations_not_synthesis_preset', bands_hz=load(a.study/'exact_sources/research/F3_native_regions_v1_plan.json')['measurement']['bands_hz'],
        independent_source_or_modulation_law=False, observations=full_features))
    result = dict(result='native_regions_and_full_envelopes_published',
        producer_report_sha256=sha(a.study/'report.json'), audit_report_sha256=sha(a.audit/'report.json'),
        source_region_power_fractions=fractions.tolist(), source_interline_bin_counts=gaps.tolist(),
        full_C_native_power_dB=np.array(differences).tolist(),
        no_clean_interline_bins_at_or_above_6k=bool(np.all(gaps[:, 5:] == 0)),
        source_6_to14k_overlap_fraction_extrema=[float(fractions[:, 5:, 2].min()), float(fractions[:, 5:, 2].max())],
        full_observations_sha256=sha(a.out/'full_band_observations.json'),
        images={name: sha(a.out/name) for name in ['regions_and_control.png', 'full_band_envelopes.png']},
        new_audio=False, gap_zero_means_physical_noise_zero=False, runtime_changed=False)
    save(a.out/'report.json', result)
    print({k: v for k, v in result.items() if k.startswith(('result', 'no_clean', 'source_6'))})


if __name__ == '__main__':
    main()
