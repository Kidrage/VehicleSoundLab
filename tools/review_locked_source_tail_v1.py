"""Publish audited weak-tail sensitivity, without changing the original source."""
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
    r = dict(result='running', sources={}, inputs={}, figures={})
    try:
        stages, captures = {}, {}
        for stage, audit_stage, mode in (('known1', 'known_audit1', 'known'), ('real1', 'audit1', 'real')):
            report = load(a.study/stage/'report.json')
            audit = load(a.study/audit_stage/'report.json')
            assert report['result'] == 'locked_source_tail_'+mode+'_measured'
            assert audit['result'] == 'independent_locked_source_tail_'+mode+'_verified' and audit['verification_passed']
            assert audit['producer_sha256'] == sha(a.study/stage/'report.json')
            assert audit['capture_sha256'] == sha(a.study/stage/'capture.npz') == report['capture_sha256']
            for path in (a.study/stage/'report.json', a.study/stage/'capture.npz', a.study/audit_stage/'report.json'):
                r['inputs'][str(path)] = sha(path)
            stages[mode] = report
            with np.load(a.study/stage/'capture.npz') as f:
                captures[mode] = {key: f[key] for key in f.files}
        names = {'tools/review_locked_source_tail_v1.py', 'tools/audit_locked_source_tail_review_v1.py',
                 'research/locked_source_tail_v1_plan.json', 'tools/research_archive_v1.py'}
        for name in sorted(names):
            dest = a.out/'exact_sources'/name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, dest); r['sources'][name] = sha(dest)
        known, real = stages['known'], stages['real']
        assert not real['source_fidelity_qualified'] and not real['eligible_for_later_source_statistics']
        r.update(study=str(a.study), original_virtual_highest_NRMSE=real['original_metrics']['target_supported_band_complex_NRMSE'][-1],
            source_fidelity_qualified=False, eligible_for_later_source_statistics=False,
            original_gate_unchanged=.02, qualified_known=known['qualification'],
            full_observations={mode: row['observations'] for mode, row in stages.items()},
            all_sources_clocks_weights_amplitude_and_original_failed_reports_retained=True,
            references_are_diagnostics_not_new_fit_targets=True,
            fit_to_new_reference_is_counterfactual_not_admission=True,
            no_acoustic_or_autonomous_sustained_C_or_hearing_qualification=True)
        def power(mode, name, band):
            return sum(stages[mode]['observations']['signals'][name][band]['Welch_FS2_LR'])
        r['real_above_centre'] = dict(original128_Welch_FS2=power('real', 'nominal128', 'above18432'),
            reference2048_Welch_FS2=power('real', 'reference2048', 'above18432'),
            reference2048_to_original128_power_ratio=power('real', 'reference2048', 'above18432')/power('real', 'nominal128', 'above18432'),
            residual_tail_cannot_be_attributed_only_to_finite128_interpolation=True)
        r['known_clock'] = dict(registered_above_centre_Welch_FS2=power('known', 'exact_registered', 'above18432'),
            affine_above_centre_Welch_FS2=power('known', 'exact_affine', 'above18432'),
            registered_to_affine_above_power_ratio=power('known', 'exact_registered', 'above18432')/power('known', 'exact_affine', 'above18432'),
            affine_is_endpoint_matched_counterfactual=True,
            spectra_include_time_warp_modulation_and_finite_window_leakage=True,
            not_a_physical_source_or_exact_real_tail_cause_identification=True)
        k = captures['known']
        delta = k['signal__nominal128']-k['signal__ideal_native_nominal128']
        r['known_FIR_numerical_sensitivity'] = dict(max_FS=float(np.max(abs(delta))),
            NRMSE=float(np.linalg.norm(delta)/np.linalg.norm(k['signal__exact_registered'])))
        fields = ['mode', 'signal', 'band', 'weighted_mass_L', 'weighted_mass_R', 'Welch_FS2_L', 'Welch_FS2_R',
                  'transform_difference_NRMSE', 'time_difference_NRMSE', 'signed_cross_L', 'signed_cross_R']
        rows = []
        for mode, row in stages.items():
            for name, bands in row['observations']['signals'].items():
                for band, numbers in bands.items():
                    comparison = row['observations']['comparisons'][name]['groups'][band]
                    rows.append([mode, name, band, *numbers['weighted_mass_LR'], *numbers['Welch_FS2_LR'],
                        comparison['transform_difference_NRMSE'], comparison['time_difference_NRMSE'], *comparison['signed_cross_mass_LR']])
        with (a.out/'all_bands.csv').open('w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f, lineterminator='\n'); writer.writerow(fields); writer.writerows(rows)
        r['table_rows'] = len(rows)
        r['table_sha256'] = sha(a.out/'all_bands.csv')
        frequency = np.arange(2049)*16.
        plot_data = dict(virtual_frequency=frequency)
        for mode, capture in captures.items():
            for key, value in capture.items():
                if key.endswith(('_Welch_FS2', '_weighted_mass')):
                    plot_data[mode+'__'+key] = value
        np.savez_compressed(a.out/'plot_data.npz', **plot_data)
        r['plot_data_sha256'] = sha(a.out/'plot_data.npz')
        def draw_spectra(ax, mode, names, limits):
            for name in names:
                y = captures[mode][name+'_Welch_FS2'].sum(axis=1)
                good = y > 0
                ax.plot(frequency[good]/1000, 10*np.log10(y[good]), label=name, lw=1.15)
            ax.set_xlim(*limits); ax.set_xlabel('Virtual frequency (kHz; not physical Hz)')
            ax.set_ylabel('Welch bin power (dB FS², L+R)'); ax.grid(alpha=.22)
            ax.legend(fontsize=8)
        fig, axes = plt.subplots(2, 2, figsize=(13.6, 8.5), layout='constrained')
        draw_spectra(axes[0, 0], 'real', ['nominal128', 'reference512', 'reference1024', 'reference2048'], (0, 32.768))
        axes[0, 0].set_title('Same real source, same registered clock')
        draw_spectra(axes[0, 1], 'real', ['nominal64', 'nominal128', 'nominal256', 'reference2048', 'saved_fit'], (14, 32.768))
        axes[0, 1].axvline(18.432, color='grey', ls=':', label='_nolegend_')
        axes[0, 1].set_title('Tail persists with long diagnostic interpolation')
        labels = ['14_16k', '16_18432', 'centre18432', 'above18432']
        for name in ('nominal128', 'nominal256', 'reference512', 'reference1024', 'saved_fit'):
            comp = real['observations']['comparisons'][name]['groups']
            axes[1, 0].semilogy(range(4), [comp[b]['transform_difference_NRMSE'] for b in labels], 'o-', label=name)
        axes[1, 0].set_xticks(range(4), ['14–16k', '16–18.432k', 'centre', '>18.432k'])
        axes[1, 0].set_ylabel('Complex NRMSE vs diagnostic reference2048')
        axes[1, 0].grid(alpha=.22); axes[1, 0].legend(fontsize=8)
        axes[1, 0].set_title('Counterfactual sensitivity; no admission change')
        dx = np.diff(captures['real']['coordinates'])*1e6
        axes[1, 1].plot(np.arange(len(dx))/65536, dx, lw=.9)
        axes[1, 1].set_xlabel('Virtual time (seconds)'); axes[1, 1].set_ylabel('Source µs per virtual sample')
        axes[1, 1].set_title('Actual registered clock (unchanged)'); axes[1, 1].grid(alpha=.22)
        fig.suptitle('F3 First Mid · weak-tail diagnosis · 288 orders / 74 nodes retained\nOriginal highest-band fidelity FAIL remains 0.442484 > 0.02', fontsize=12)
        for ext in ('png', 'svg'):
            name = 'real_tail.'+ext; fig.savefig(a.out/name, dpi=150); r['figures'][name] = sha(a.out/name)
        plt.close(fig)
        fig, axes = plt.subplots(1, 2, figsize=(13.6, 4.6), layout='constrained')
        draw_spectra(axes[0], 'known', ['exact_registered', 'exact_affine', 'nominal128', 'reference2048'], (14, 32.768))
        axes[0].axvline(18.432, color='grey', ls=':')
        axes[0].set_title('Analytic bandlimited tones through two clocks')
        for name in ('nominal128', 'reference512', 'reference1024', 'reference2048', 'exact_query'):
            comp = known['observations']['comparisons'][name]['groups']
            axes[1].semilogy(range(4), [comp[b]['transform_difference_NRMSE'] for b in labels], 'o-', label=name)
        axes[1].set_xticks(range(4), ['14–16k', '16–18.432k', 'centre', '>18.432k'])
        axes[1].set_ylabel('Complex NRMSE vs exact registered-clock tones')
        axes[1].set_title('Interpolation improves; clocked tail is still present')
        axes[1].grid(alpha=.22); axes[1].legend(fontsize=8)
        fig.suptitle('Known controls · affine clock is diagnostic only · includes finite-window leakage', fontsize=12)
        for ext in ('png', 'svg'):
            name = 'known_transfer.'+ext; fig.savefig(a.out/name, dpi=150); r['figures'][name] = sha(a.out/name)
        plt.close(fig)
        r['result'] = 'locked_source_tail_review_published'
        save(a.out/'report.json', r)
        print('TAIL_REVIEW_PUBLISHED', r['table_rows'], flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error)); save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
