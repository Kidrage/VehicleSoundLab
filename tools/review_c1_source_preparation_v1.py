"""Publish physical source-filter bandwidth separately from unqualified fitting."""
import argparse
import csv
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('workspace', 'study', 'out'): p.add_argument('--'+key, type=Path, required=True)
    a = p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'): os.environ[key] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy import signal
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from clock_native_bridge_v1.observation import observe
    a.out.mkdir(parents=True, exist_ok=False); shutil.copy2(__file__, a.out/'executed_review.py')
    r = dict(result='running', inputs={}, original_full_preparation_audit_passed=False,
        no_fit_or_C_runtime_model_or_hearing_change=True)
    def bind(path):
        path = Path(path); r['inputs'][str(path)] = sha(path); return path
    def arrays(path):
        with np.load(bind(path)) as f: return {k:f[k] for k in f.files}
    try:
        info = load(bind(a.study/'report.json')); assert info['result'] == 'c1_source_one_real_prepared'
        row = info['cases'][0]; label = row['label']; assert label == 'F3 Fifth First Late'
        z = arrays(a.study/row['file']); assert sha(a.study/row['file']) == row['sha256']
        source_root = a.workspace/'references/analysis/source_resampling_v1'
        old_info = load(bind(source_root/'real1/report.json'))
        old_audit = load(bind(source_root/'real_audit1/report.json'))
        assert old_audit['verification_passed'] and old_audit['producer_sha256'] == sha(source_root/'real1/report.json')
        old_row = next(c for c in old_info['cases'] if c['label'] == label)
        old = arrays(source_root/'real1'/old_row['file']); assert sha(source_root/'real1'/old_row['file']) == old_row['sha256']
        assert np.array_equal(old['source_coordinates'], z['legacy_source_coordinates'])
        assert float(old['source_start']) == float(z['source_start'])
        first = int(np.ceil(z['source_coordinates'][2048]*48000-1e-6))
        stop = int(np.floor(z['source_coordinates'][-2049]*48000+1e-6))+1
        ids = np.arange(first, stop)-int(round(float(z['source_start'])*48000))
        assert ids[0] >= 0 and ids[-1] < len(z['native'])
        values = dict(raw=z['native'][ids], FIR14=old['filtered'][ids-int(old['crop'][0])],
            FIR22=z['source_filtered'][ids-int(z['source_crop'][0])])
        measured, data = observe(values)
        f = np.linspace(0, 24000, 2049)
        data['filter_frequency'] = f
        for name, taps in (('FIR14', old['taps']), ('FIR22', z['source_filter_taps'])):
            _, response = signal.freqz(taps, worN=2*np.pi*f/48000)
            data[name+'_filter_magnitude'] = abs(response); data[name+'_filter_taps'] = taps
        data.update(native_indices=np.arange(first, stop), source_start=z['source_start'],
            native_source=z['native'], FIR14_full=old['filtered'], FIR14_crop=old['crop'],
            FIR22_full=z['source_filtered'], FIR22_crop=z['source_crop'])
        np.savez_compressed(a.out/'observations.npz', **data)
        rows = []
        bands = ['0-3k', '3-6k', '6-8k', '8-10k', '10-14k', '14-24k']
        uppers = ['14-16k', '16-20k', '20-22k', '22-24k']
        def add(name, scope, labels, p, cross, ms):
            power = p.mean(axis=0); mid_side = ms.mean(axis=0)
            coherence = cross.mean(axis=0)/np.sqrt(power[:, 0]*power[:, 1])
            cv = p.std(axis=0)/power
            for i, band in enumerate(labels):
                rows.append(dict(signal=name, scope=scope, band=band, L_FS2=float(power[i, 0]),
                    R_FS2=float(power[i, 1]), Mid_FS2=float(mid_side[i, 0]), Side_FS2=float(mid_side[i, 1]),
                    coherence_real=float(coherence[i].real), coherence_imag=float(coherence[i].imag),
                    CV_L=float(cv[i, 0]), CV_R=float(cv[i, 1])))
        for name in values:
            add(name, 'broad', bands, data[name+'_broad_power'], data[name+'_broad_Gram'][:, :, 0, 1], data[name+'_broad_mid_side'])
            add(name, 'upper', uppers, data[name+'_upper_power'], data[name+'_upper_cross'], data[name+'_upper_mid_side'])
        with (a.out/'physical_bands.csv').open('w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
        lookup = {(v['signal'], v['scope'], v['band']):v for v in rows}
        metrics = {}
        for name in values:
            full = lookup[name, 'broad', '14-24k']
            power = sum(lookup[name, 'upper', band]['L_FS2']+lookup[name, 'upper', band]['R_FS2'] for band in uppers[:3])
            metrics[name] = dict(LR_14_24k_FS2=full['L_FS2']+full['R_FS2'], LR_14_22k_FS2=power)
        for name in ('FIR14', 'FIR22'):
            for band in ('14_24k', '14_22k'):
                key = 'LR_'+band+'_FS2'
                metrics[name][band+'_power_change_from_raw_dB'] = float(10*np.log10(metrics[name][key]/metrics['raw'][key]))
        fig, axes = plt.subplots(2, 2, figsize=(13.4, 8.4), constrained_layout=True)
        colors = {'raw':'#202b38', 'FIR14':'#c96e35', 'FIR22':'#168a87'}
        for name in ('FIR14', 'FIR22'):
            axes[0, 0].plot(data['filter_frequency']/1000, 20*np.log10(np.maximum(data[name+'_filter_magnitude'], 1e-12)),
                label=name, color=colors[name])
        axes[0, 0].set(xlabel='Physical frequency (kHz)', ylabel='Filter magnitude (dB)', ylim=(-150, 3), title='Explicit physical source FIRs')
        for name in values:
            power = [lookup[name, 'broad', band]['L_FS2']+lookup[name, 'broad', band]['R_FS2'] for band in bands]
            axes[0, 1].plot(bands, 10*np.log10(power), marker='o', label=name, color=colors[name])
            upper = [lookup[name, 'upper', band]['L_FS2']+lookup[name, 'upper', band]['R_FS2'] for band in uppers]
            axes[1, 0].plot(uppers, 10*np.log10(upper), marker='o', label=name, color=colors[name])
            coherence = [abs(complex(lookup[name, 'upper', band]['coherence_real'], lookup[name, 'upper', band]['coherence_imag'])) for band in uppers]
            axes[1, 1].plot(uppers, coherence, marker='o', label=name, color=colors[name])
        axes[0, 1].set(ylabel='L+R mean band power (dB FS2)', title='Same native48k interval; original gain')
        axes[1, 0].set(ylabel='L+R mean band power (dB FS2)', title='Upper-band input detail retained by source filters')
        axes[1, 1].set(ylabel='Magnitude of measured complex LR coherence', ylim=(0, 1.05), title='Stereo observation; no widening or room')
        for ax in axes.ravel(): ax.grid(alpha=.22); ax.legend(fontsize=8)
        fig.suptitle('Physical source-filter diagnostic | F3 Fifth First Late | No fitted or sustained voice', fontsize=12)
        for suffix in ('png', 'svg'): fig.savefig(a.out/('source_bandwidth.'+suffix), dpi=150)
        plt.close(fig)
        r.update(result='c1_source_preparation_bandwidth_published', label=label, first_native_tick=first,
            stop_native_tick=stop, physical_native_frames=stop-first, physical_seconds=[first/48000, stop/48000],
            metrics=metrics, table_rows=len(rows), figures={n:sha(a.out/n) for n in ('source_bandwidth.png', 'source_bandwidth.svg')},
            files={n:sha(a.out/n) for n in ('observations.npz', 'physical_bands.csv')},
            source_filter_comparison_only_not_C1_vs_PL_causality=True,
            finite22kFIR_not_raw_fullband_preservation=True, new_source_fidelity_not_evaluated=True,
            original_full_objective_audit_failure_retained=True)
        save(a.out/'report.json', r); print('C1_SOURCE_BANDWIDTH', r['physical_native_frames'], metrics, flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error)); save(a.out/'report.json', r); raise


if __name__ == '__main__': main()
