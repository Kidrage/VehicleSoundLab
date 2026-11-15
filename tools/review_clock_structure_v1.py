"""Publish complete clock-node/curvature tables and controlled transfer figures."""
import argparse
import csv
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('workspace', 'study', 'out'):
        p.add_argument('--'+key, type=Path, required=True)
    a = p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[key] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', sources={}, inputs={}, tables={}, figures={})
    try:
        reports, captures = {}, {}
        for mode, stage, audit_stage in (('known', 'known1', 'known_audit1'), ('real', 'real1', 'audit1')):
            report = load(a.study/stage/'report.json'); proof = load(a.study/audit_stage/'report.json')
            assert report['result'] == 'clock_structure_'+mode+'_measured'
            assert proof['result'] == 'independent_clock_structure_'+mode+'_verified' and proof['verification_passed']
            assert proof['producer_sha256'] == sha(a.study/stage/'report.json')
            assert proof['capture_sha256'] == sha(a.study/stage/'capture.npz') == report['capture_sha256']
            for path in (a.study/stage/'report.json', a.study/stage/'capture.npz', a.study/audit_stage/'report.json'):
                r['inputs'][str(path)] = sha(path)
            reports[mode] = report
            with np.load(a.study/stage/'capture.npz') as f:
                captures[mode] = {key: f[key] for key in f.files}
        for name in ('tools/review_clock_structure_v1.py', 'tools/audit_clock_structure_review_v1.py',
                     'tools/research_archive_v1.py', 'research/clock_structure_v1_plan.json'):
            dest = a.out/'exact_sources'/name; dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, dest); r['sources'][name] = sha(dest)
        known, real = captures['known'], captures['real']
        r.update(study=str(a.study), geometry=reports['real']['geometry'], known=reports['known']['known'],
            known_observations=reports['known']['observations'],
            old_source_highest_NRMSE=reports['real']['old_source_highest_NRMSE'],
            original_source_fidelity_qualified=False, eligible_for_later_source_statistics=False,
            clock_curvature_is_not_acoustic_power=True, no_actual_clock_or_audio_or_target_change=True,
            controlled_smooth_is_not_actual_clock_candidate=True,
            no_causal_percentage_of_real_audio_tail_or_naturalness_qualification=True)
        obs = r['known_observations']['signals']
        powers = {name: dict(Welch_FS2_LR=values['above18432']['Welch_FS2_LR'],
            weighted_mass_LR=values['above18432']['weighted_mass_LR']) for name, values in obs.items()}
        r['controlled_above_centre'] = dict(signals=powers,
            C0_to_exact_smooth_power_ratio=sum(powers['manufactured_C0']['Welch_FS2_LR'])/sum(powers['exact_smooth']['Welch_FS2_LR']),
            sampled_to_exact_smooth_power_ratio=sum(powers['sampled_smooth_PL']['Welch_FS2_LR'])/sum(powers['exact_smooth']['Welch_FS2_LR']))
        with (a.out/'all_nodes.csv').open('w', encoding='utf-8', newline='') as f:
            w = csv.writer(f, lineterminator='\n')
            w.writerow(['event_index', 'virtual_sample', 'observed_phase_node', 'source_seconds',
                        'left_seconds_per_sample', 'right_seconds_per_sample', 'jump_seconds_per_sample'])
            for i in range(len(real['jumps'])):
                w.writerow([i, real['jump_node'][i], int(real['graph_special'][i+1]), real['graph_y'][i+1],
                            real['slopes'][i], real['slopes'][i+1], real['jumps'][i]])
        with (a.out/'all_curvature.csv').open('w', encoding='utf-8', newline='') as f:
            w = csv.writer(f, lineterminator='\n')
            w.writerow(['virtual_sample', 'actual_d2_seconds', 'observed_phase_nodes', 'other_coarse_nodes',
                        'preservation_join', 'floating_remainder', 'observed_support'])
            for i in range(len(real['actual_d2'])):
                w.writerow([real['query'][i+1], real['actual_d2'][i], *real['components'][:, i], int(real['special_support'][i])])
        r.update(node_rows=len(real['jumps']), curvature_rows=len(real['actual_d2']))
        for name in ('all_nodes.csv', 'all_curvature.csv'):
            r['tables'][name] = sha(a.out/name)
        frequency = np.arange(2049)*16.
        plot = dict(virtual_frequency=frequency, query=real['query'], actual=real['actual'],
                    actual_d2=real['actual_d2'], components=real['components'], special_support=real['special_support'],
                    jump_node=real['jump_node'], jumps=real['jumps'], graph_special=real['graph_special'], Gram=real['Gram'])
        plot.update({name+'_Welch_FS2': known[name+'_Welch_FS2'] for name in obs})
        np.savez_compressed(a.out/'plot_data.npz', **plot)
        r['plot_data_sha256'] = sha(a.out/'plot_data.npz')
        fig, axes = plt.subplots(3, 1, figsize=(13.2, 9.2), layout='constrained')
        time = real['query']/65536
        axes[0].plot(time[:-1], np.diff(real['actual'])*1e6, lw=1)
        axes[0].set_ylabel('Source µs / virtual sample'); axes[0].set_title('Original clock slope; no target or clock changes')
        center = time[1:-1]
        axes[1].plot(center, real['actual_d2']*1e9, label='actual clock curvature', lw=1.1)
        axes[1].plot(center, real['components'][0]*1e9, label='observed-node hinge contribution', lw=.8, alpha=.8)
        axes[1].plot(center, real['components'][1]*1e9, label='all other coarse nodes', lw=.8)
        axes[1].set_ylabel('Clock second difference (ns)'); axes[1].legend(fontsize=8)
        peak = int(np.argmax(abs(real['actual_d2'])))
        lo, hi = max(0, peak-10), min(len(center), peak+11)
        axes[2].plot(real['query'][1:-1][lo:hi], real['actual_d2'][lo:hi]*1e9, 'o-', label='actual')
        for c, label in enumerate(('observed nodes', 'other coarse nodes', 'preservation join', 'floating remainder')):
            axes[2].plot(real['query'][1:-1][lo:hi], real['components'][c, lo:hi]*1e9, '.-', label=label)
        axes[2].set_xlabel('Virtual sample (largest-curvature region)'); axes[2].set_ylabel('Clock second difference (ns)')
        axes[2].legend(fontsize=8); axes[2].set_title('Exact signed decomposition around the largest feature')
        for ax in axes:
            ax.grid(alpha=.23)
        for ax in axes[:2]:
            ax.set_xlabel('Virtual time (seconds)')
        g = r['geometry']
        fig.suptitle('F3 First Mid · all 22,529 clock nodes / 18,434 queries\n'
            f"Observed-node support: {g['special_support_samples']} / {len(real['actual_d2'])} samples; "
            f"{100*g['special_support_squared_d2_fraction']:.3f}% of squared clock curvature (NOT acoustic power)", fontsize=12)
        for ext in ('png', 'svg'):
            name = 'real_clock.'+ext; fig.savefig(a.out/name, dpi=150); r['figures'][name] = sha(a.out/name)
        plt.close(fig)
        fig, axes = plt.subplots(1, 2, figsize=(13.2, 4.8), layout='constrained')
        for name in obs:
            y = known[name+'_Welch_FS2'].sum(axis=1); mask = y>0
            axes[0].plot(frequency[mask]/1000, 10*np.log10(y[mask]), label=name, lw=1.05)
        axes[0].set_xlim(14, 32.768); axes[0].set_xlabel('Virtual frequency (kHz; not physical Hz)')
        axes[0].set_ylabel('Welch bin power (dB FS²; L+R)'); axes[0].legend(fontsize=8)
        axes[0].axvline(18.432, ls=':', color='grey'); axes[0].set_title('Manufactured slope jumps create a weak tail')
        bands = ['14_16k', '16_18432', 'centre18432', 'above18432']
        for name in ('affine', 'manufactured_C0', 'sampled_smooth_PL'):
            groups = r['known_observations']['comparisons'][name]['groups']
            axes[1].semilogy(range(4), [groups[b]['transform_difference_NRMSE'] for b in bands], 'o-', label=name)
        axes[1].set_xticks(range(4), ['14–16k', '16–18.432k', 'centre', '>18.432k'])
        axes[1].set_ylabel('Complex NRMSE vs exact smooth control'); axes[1].legend(fontsize=8)
        axes[1].set_title('Fixed smooth width256; endpoint matched')
        for ax in axes:
            ax.grid(alpha=.23)
        fig.suptitle('Analytic stereo controls only · includes finite-window leakage\nNo new actual-clock candidate or fitted source admission', fontsize=12)
        for ext in ('png', 'svg'):
            name = 'controlled_transfer.'+ext; fig.savefig(a.out/name, dpi=150); r['figures'][name] = sha(a.out/name)
        plt.close(fig)
        r['result'] = 'clock_structure_review_published'; save(a.out/'report.json', r)
        print('CLOCK_REVIEW_PUBLISHED', r['node_rows'], r['curvature_rows'], flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error)); save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
