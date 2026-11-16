"""Publish physical native-clock evidence without changing source admission."""
import argparse
import csv
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('workspace', 'study', 'audit', 'out'):
        p.add_argument('--'+key, type=Path, required=True)
    a = p.parse_args(); sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', inputs={}, sources={})
    repo = Path(__file__).resolve().parents[1]
    for name in ('tools/review_clock_native_bridge_v1.py', 'tools/audit_clock_native_bridge_review_v1.py'):
        dest = a.out/'exact_sources'/name; dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo/name, dest); r['sources'][name] = sha(dest)
    try:
        info, proof = load(a.study/'report.json'), load(a.audit/'report.json')
        assert info['result'] == 'clock_native_bridge_real_measured' and proof['verification_passed']
        assert proof['producer_sha256'] == sha(a.study/'report.json')
        for path in (a.study/'report.json', a.study/'sound.npz', a.audit/'report.json'):
            r['inputs'][str(path)] = sha(path)
        with np.load(a.study/'sound.npz') as z:
            d = {k:z[k] for k in z.files}
        names = ('raw', 'FIR_only', 'C1_16', 'C1_32', 'PL_16', 'PL_32')
        tables = {}
        def table(name, columns, rows):
            with (a.out/name).open('w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f, lineterminator='\n'); writer.writerow(columns); writer.writerows(rows)
            tables[name] = sha(a.out/name)
        # All signed comparison fields, including covariance and all lag matrices.
        leaves = []
        def flatten(value, path):
            if isinstance(value, dict):
                for key, child in value.items(): flatten(child, path+'/'+key)
            elif isinstance(value, list):
                for i, child in enumerate(value): flatten(child, path+'/'+str(i))
            else:
                assert value is None or isinstance(value, (int, float))
                leaves.append((path, '' if value is None else value))
        flatten(info['comparisons'], '')
        table('comparisons.csv', ['field_path', 'original_scale_value_or_empty_undefined'], leaves)
        rows = []
        for name in names:
            for i, label in enumerate(('0-3k', '3-6k', '6-8k', '8-10k', '10-14k', '14-24k')):
                coh = d[name+'_broad_complex_coherence'][i]
                rows.append([name, label, *d[name+'_broad_mean_power'][i],
                    *d[name+'_broad_mean_mid_side'][i], *d[name+'_broad_CV'][i], coh.real, coh.imag])
        table('bands.csv', ['signal', 'physical_band_Hz', 'L_FS2', 'R_FS2', 'Mid_FS2', 'Side_FS2',
            'CV_L', 'CV_R', 'complex_coherence_real', 'complex_coherence_imag'], rows)
        rows = []
        for name in names:
            for i, label in enumerate(('14-16k', '16-20k', '20-22k', '22-24k')):
                cross = d[name+'_upper_cross'][:, i].mean()
                rows.append([name, label, *d[name+'_upper_power'][:, i].mean(axis=0),
                    *d[name+'_upper_mid_side'][:, i].mean(axis=0), cross.real, cross.imag])
        table('upper_bands.csv', ['signal', 'physical_band_Hz', 'L_FS2', 'R_FS2', 'Mid_FS2', 'Side_FS2',
            'cross_real_FS2', 'cross_imag_FS2'], rows)
        fields, columns = [d['raw_frequency']], ['physical_Hz']
        for name in names:
            power = d[name+'_bin_power'].mean(axis=0)
            cross = d[name+'_bin_cross'].mean(axis=0)
            ms = d[name+'_bin_mid_side'].mean(axis=0)
            fields.extend((power[:, 0], power[:, 1], cross.real, cross.imag, ms[:, 0], ms[:, 1]))
            columns.extend(name+'_'+key for key in ('L_FS2', 'R_FS2', 'cross_real_FS2', 'cross_imag_FS2', 'Mid_FS2', 'Side_FS2'))
        table('spectra.csv', columns, zip(*fields))
        def db(x):
            x = np.asarray(x); out = np.full(x.shape, np.nan)
            np.log10(x, out=out, where=x>0); return 10*out
        frequency = d['raw_frequency']/1000
        show = ('raw', 'FIR_only', 'PL_32', 'C1_32')
        fig, axes = plt.subplots(2, 2, figsize=(13, 8), constrained_layout=True)
        for name in show:
            power = d[name+'_bin_power'].mean(axis=0)
            for c in (0, 1):
                axes[c, 0].plot(frequency, db(power[:, c]), label=name, linewidth=1)
        for c in (0, 1):
            axes[c, 0].set(xlabel='Physical kHz', ylabel=('L' if c == 0 else 'R')+' Welch power/bin (dB FS^2)')
            axes[c, 0].axvline(14, color='gray', linestyle=':'); axes[c, 0].axvline(22, color='gray', linestyle=':')
            axes[c, 0].legend(fontsize=8)
        for pair in ('C1_32_vs_FIR_only', 'PL_32_vs_FIR_only', 'FIR_only_vs_raw'):
            row = info['comparisons'][pair]
            axes[0, 1].plot(range(6), row['band_complex_NRMSE'], '.-', label=pair)
        axes[0, 1].set(ylabel='Complex band NRMSE', yscale='log')
        axes[0, 1].set_xticks(range(6), ['0-3k', '3-6k', '6-8k', '8-10k', '10-14k', '14-24k'], rotation=30)
        axes[0, 1].legend(fontsize=8)
        for name in show:
            axes[1, 1].plot(range(4), db(d[name+'_upper_power'].mean(axis=0).sum(axis=1)), '.-', label=name)
        axes[1, 1].set(ylabel='Upper-band LR sum (dB FS^2)')
        axes[1, 1].set_xticks(range(4), ['14-16k', '16-20k', '20-22k', '22-24k']); axes[1, 1].legend(fontsize=8)
        fig.suptitle('Supported clock roundtrip at native 48 kHz; raw and source-FIR references remain separate')
        figures = {}
        for ext in ('png', 'svg'):
            name = 'native_bridge.'+ext; fig.savefig(a.out/name, dpi=150); figures[name] = sha(a.out/name)
        plt.close(fig)
        fig, axes = plt.subplots(2, 2, figsize=(13, 8), constrained_layout=True)
        for name in show:
            ms = d[name+'_broad_mean_mid_side']
            axes[0, 0].plot(range(6), db(ms[:, 1])-db(ms[:, 0]), '.-', label=name)
            coh = d[name+'_broad_complex_coherence']
            axes[0, 1].plot(range(6), coh.real, '.-', label=name+' real')
            axes[0, 1].plot(range(6), coh.imag, '.--', label=name+' imag')
            for c in (0, 1): axes[1, c].plot(range(6), d[name+'_broad_CV'][:, c], '.-', label=name)
        axes[0, 0].set(ylabel='Side/Mid (dB)'); axes[0, 1].set(ylabel='Complex LR coherence')
        for c in (0, 1): axes[1, c].set(ylabel=('L' if c == 0 else 'R')+' window-power CV')
        for ax in axes.ravel():
            ax.set_xticks(range(6), ['0-3k', '3-6k', '6-8k', '8-10k', '10-14k', '14-24k'], rotation=30)
            ax.legend(fontsize=7)
        fig.suptitle('Recorded LR relationships and temporal power; no width processor, room, normalization or source promotion')
        for ext in ('png', 'svg'):
            name = 'stereo_time.'+ext; fig.savefig(a.out/name, dpi=150); figures[name] = sha(a.out/name)
        plt.close(fig)
        r.update(result='clock_native_bridge_review_published', study=str(a.study), audit=str(a.audit), tables=tables,
            figures=figures, signed_comparison_leaves=len(leaves), all_weak_band_failures_retained=True,
            no_actual_target_source_admission_or_runtime_promotion=True)
        save(a.out/'report.json', r); print('BRIDGE_REVIEW_COMPLETE', len(leaves), flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error)); save(a.out/'report.json', r); raise


if __name__ == '__main__':
    main()
