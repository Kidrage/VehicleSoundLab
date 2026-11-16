"""Publish all-node/all-bin C1 counterfactual tables and diagnostic figures."""
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
    for name in ('tools/review_clock_c1_v1.py', 'tools/audit_clock_c1_review_v1.py'):
        dest = a.out/'exact_sources'/name; dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo/name, dest); r['sources'][name] = sha(dest)
    try:
        info, proof = load(a.study/'report.json'), load(a.audit/'report.json')
        assert info['result'] == 'clock_c1_real_measured' and proof['verification_passed']
        assert proof['producer_sha256'] == sha(a.study/'report.json')
        assert info['capture_sha256'] == sha(a.study/'capture.npz')
        for path in (a.study/'report.json', a.study/'capture.npz', a.audit/'report.json'):
            r['inputs'][str(path)] = sha(path)
        with np.load(a.study/'capture.npz') as z:
            d = {k:z[k] for k in z.files}
        def table(name, columns, values):
            with (a.out/name).open('w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f, lineterminator='\n'); writer.writerow(columns)
                writer.writerows(values)
        q, old, new = d['query'], d['old_positions'], d['positions']
        change = (new-old)*1e6
        table('clock.csv', ['query', 'original_seconds', 'C1_seconds', 'change_microseconds'], zip(q, old, new, change))
        table('intervals.csv', ['x_left', 'x_right', 'y_left', 'y_right', 'cubic', 'quadratic', 'linear', 'constant_local', 'minimum_derivative'],
            zip(d['x'][:-1], d['x'][1:], d['y'][:-1], d['y'][1:], *d['coefficients'], d['interval_minimum_derivative']))
        frequency = np.arange(2049)*16.
        po, pn = d['original_Welch_FS2'], d['C1_Welch_FS2']
        table('spectra.csv', ['virtual_Hz', 'original_L_FS2', 'original_R_FS2', 'C1_L_FS2', 'C1_R_FS2'], zip(frequency, *po.T, *pn.T))
        columns = ['band', 'old_L_FS2', 'old_R_FS2', 'C1_L_FS2', 'C1_R_FS2', 'change_L_dB', 'change_R_dB',
            'complex_coherence_change', 'old_Side_Mid_dB', 'C1_Side_Mid_dB', 'CV_change_L', 'CV_change_R',
            'transform_difference_NRMSE', 'time_difference_NRMSE']
        rows = []
        for b in info['stereo']['bands']:
            group = info['observations']['comparisons']['C1']['groups'][b['band']]
            rows.append([b['band'], *b['old_Welch_FS2_LR'], *b['C1_Welch_FS2_LR'], *b['power_change_dB_LR'],
                b['coherence_complex_difference'], b['old_Side_Mid_dB'], b['C1_Side_Mid_dB'], *b['CV_change_LR'],
                group['transform_difference_NRMSE'], group['time_difference_NRMSE']])
        table('bands.csv', columns, rows)
        fig, axes = plt.subplots(2, 2, figsize=(12, 7.5), constrained_layout=True)
        axes[0, 0].plot(q, change); axes[0, 0].set(ylabel='Clock change (microseconds)', xlabel='Virtual sample coordinate')
        axes[0, 1].plot(q[:-1], np.diff(old)*1e6, label='Original PL', alpha=.8)
        axes[0, 1].plot(q[:-1], np.diff(new)*1e6, label='Node-preserving C1', alpha=.8)
        axes[0, 1].set(ylabel='First difference (microseconds/sample)', xlabel='Virtual sample coordinate'); axes[0, 1].legend()
        axes[1, 0].plot(q[1:-1], np.diff(old, 2)*1e9, label='Original PL', alpha=.75)
        axes[1, 0].plot(q[1:-1], np.diff(new, 2)*1e9, label='C1', alpha=.75)
        axes[1, 0].set(ylabel='Second difference (nanoseconds)', xlabel='Virtual sample coordinate'); axes[1, 0].legend()
        axes[1, 1].plot(d['x'][:-1], d['interval_minimum_derivative']*1e6, '.-')
        axes[1, 1].set(ylabel='Analytic interval minimum derivative (us/sample)', xlabel='Original observed knot coordinate')
        fig.suptitle('Same 89 observed nodes; C1 changes only between nodes. Diagnostic, not a replacement clock.')
        figures = {}
        for ext in ('png', 'svg'):
            name = 'clock.'+ext; fig.savefig(a.out/name, dpi=150); figures[name] = sha(a.out/name)
        plt.close(fig)
        fig, axes = plt.subplots(2, 2, figsize=(13, 8), constrained_layout=True)
        for c, color in ((0, 'tab:blue'), (1, 'tab:orange')):
            axes[0, 0].plot(frequency/1000, 10*np.log10(po[:, c]), color=color, label='Original '+('L' if c == 0 else 'R'))
            axes[0, 0].plot(frequency/1000, 10*np.log10(pn[:, c]), color=color, linestyle='--', label='C1 '+('L' if c == 0 else 'R'))
        axes[0, 0].axvline(18.432, color='gray', linestyle=':')
        axes[0, 0].set(xlabel='Virtual kHz (not physical source kHz)', ylabel='Welch power / bin (dB FS^2)'); axes[0, 0].legend(fontsize=8)
        labels = [row[0] for row in rows]; ids = np.arange(10)
        changes = np.array([row[5:7] for row in rows], float)
        axes[0, 1].bar(ids-.18, changes[:, 0], .36, label='L'); axes[0, 1].bar(ids+.18, changes[:, 1], .36, label='R')
        axes[0, 1].set(ylabel='Band power change (dB)'); axes[0, 1].legend()
        side = np.array([row[9]-row[8] for row in rows]); axes[1, 0].bar(ids, side)
        axes[1, 0].set(ylabel='Side/Mid change (dB)')
        cv = np.array([row[10:12] for row in rows], float)
        axes[1, 1].plot(ids, cv[:, 0], '.-', label='L'); axes[1, 1].plot(ids, cv[:, 1], '.-', label='R')
        axes[1, 1].set(ylabel='Window-power CV change'); axes[1, 1].legend()
        for ax in (axes[0, 1], axes[1, 0], axes[1, 1]):
            ax.set_xticks(ids, labels, rotation=45, ha='right', fontsize=8); ax.axvline(4.5, color='gray', linestyle=':')
        fig.suptitle('C1 counterfactual: main bands nearly unchanged; weak tail statistics change greatly. No listening claim.')
        for ext in ('png', 'svg'):
            name = 'spectra_stereo.'+ext; fig.savefig(a.out/name, dpi=150); figures[name] = sha(a.out/name)
        plt.close(fig)
        r.update(result='clock_c1_review_published', study=str(a.study), audit=str(a.audit),
            figures=figures, tables={name:sha(a.out/name) for name in ('clock.csv', 'intervals.csv', 'spectra.csv', 'bands.csv')},
            all_6bands_and_4subgroups_retained=True, all_weak_band_regressions_retained=True,
            no_actual_clock_or_audio_promotion=True)
        save(a.out/'report.json', r)
        print('C1_REVIEW_COMPLETE', flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error)); save(a.out/'report.json', r); raise


if __name__ == '__main__':
    main()
