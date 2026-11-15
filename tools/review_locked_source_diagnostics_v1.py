"""Publish the explicitly changed-source case after all five terminal diagnostics.

No fitting, audio generation or qualification-gate changes. Original failed
reports and all physical bands remain visible beside the main-band detail view.
"""
import argparse
import csv
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'study', 'math-audit', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[key] = '2'
    sys.path.insert(0, str(a.workspace / 'tools/python_deps'))
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', inputs={}, sources={})

    def read(path):
        path = Path(path)
        r['inputs'][str(path)] = sha(path)
        return load(path)

    try:
        for name in ('tools/review_locked_source_diagnostics_v1.py',
                     'tools/audit_locked_source_review_v1.py', 'tools/research_archive_v1.py'):
            dest = a.out / 'exact_sources' / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo / name, dest)
            r['sources'][name] = sha(dest)
        proof = read(a.math_audit)
        assert proof['result'] == 'independent_locked_source_real_verified' and proof['verification_passed']
        vr = read(a.study / 'virtual_real1/report.json')
        va = read(a.study / 'virtual_real_audit1/report.json')
        vs = read(a.study / 'virtual_real_stereo_audit1/report.json')
        native = read(a.study / 'native_real1/report.json')
        audit = read(a.study / 'native_real_audit1/report.json')
        assert vr['result'] == 'locked_source_real_virtual_measured' and len(vr['cases']) == 1
        assert va['result'] == 'independent_locked_source_virtual_verified' and va['all_consumer_checks_passed']
        assert vs['result'] == 'independent_locked_source_virtual_stereo_verified' and vs['all_stereo_checks_passed']
        assert va['producer_sha256'] == vs['producer_sha256'] == sha(a.study / 'virtual_real1/report.json')
        assert vs['prior_audit_sha256'] == sha(a.study / 'virtual_real_audit1/report.json')
        assert native['result'] == 'locked_source_native_case_measured'
        assert audit['result'] == 'independent_locked_source_native_verified' and audit['verification_passed']
        assert audit['producer_sha256'] == sha(a.study / 'native_real1/report.json')
        assert native['source']['math_audit_sha256'] == sha(a.math_audit)
        label = native['label']
        assert vr['cases'][0]['label'] == proof['case']['label'] == label
        virtual_path = a.study / 'virtual_real1' / vr['cases'][0]['report']
        assert sha(virtual_path) == vr['cases'][0]['sha256']
        virtual = read(virtual_path)
        for key in ('source_solver_qualified', 'source_fidelity_qualified',
                    'native16_32_convergence_passed', 'eligible_for_later_source_statistics'):
            assert native[key] == audit[key]
        assert native['source_solver_qualified'] == proof['case']['solver_qualified']
        assert native['source_fidelity_qualified'] == proof['case']['fidelity_qualified']
        case = Path(native['paths']['case'])
        original = read(case.parent / 'report.json')
        failed_audit = read(case.parent / (case.name + '_audit') / 'report.json')
        assert original['result'] == failed_audit['result'] == 'failed'
        assert not proof['case']['retained_cross_operator_metric_comparison']['original_2e_12_comparison_passed']
        sound_file = a.study / 'native_real1' / native['sound']['file']
        assert sha(sound_file) == native['sound']['sha256']
        r['inputs'][str(sound_file)] = sha(sound_file)
        with np.load(sound_file) as f:
            z = {key: f[key] for key in f.files}
        signals = {}
        for name in ('raw', 'FIR_only', 'fitted16', 'fitted32'):
            ms = z[name + '_broad_mean_mid_side']
            signals[name] = dict(mean_power_FS2=z[name + '_broad_mean_power'].tolist(),
                mean_mid_side_FS2=ms.tolist(), CV=z[name + '_broad_CV'].tolist(),
                side_over_mid_dB=[float(10*np.log10(s/m)) if m > 0 and s > 0 else None for m, s in ms],
                complex_coherence=[[float(v.real), float(v.imag)] for v in z[name + '_broad_complex_coherence']])
        compact = {}
        for name, c in native['comparisons'].items():
            s = c['signed_changes']['broad']
            main = slice(0, 5)
            ms = np.asarray(s['mid_side_change_dB'], float)
            coh = np.asarray(s['complex_coherence_change'], float)
            compact[name] = dict(wave_NRMSE=c['wave_NRMSE'], channel_wave_NRMSE=c['channel_wave_NRMSE'],
                band_complex_NRMSE=c['band_complex_NRMSE'], power_change_dB=s['power_change_dB'],
                side_over_mid_change_dB=(ms[:, 1]-ms[:, 0]).tolist(),
                complex_coherence_change=s['complex_coherence_change'], CV_change=s['CV_change'],
                covariance_relative_difference=s['covariance_relative_difference'],
                lag_covariance_relative_difference=s['lag_covariance_relative_difference'],
                main_0_14k_max_power_change_dB=float(np.max(abs(np.asarray(s['power_change_dB'])[main]))),
                main_0_14k_max_side_over_mid_change_dB=float(np.max(abs((ms[:, 1]-ms[:, 0])[main]))),
                main_0_14k_max_complex_coherence_change=float(np.max(np.linalg.norm(coh[main], axis=1))),
                main_0_14k_max_CV_change=float(np.max(abs(np.asarray(s['CV_change'])[main]))))
        labels = ['0-3', '3-6', '6-8', '8-10', '10-14', '14-24']
        r.update(label=label, physical_rate=48000, native_frames=native['sound']['frames'],
            flags={key: native[key] for key in ('source_solver_qualified', 'source_fidelity_qualified',
                'native16_32_convergence_passed', 'eligible_for_later_source_statistics')},
            original_virtual_weighted_metrics=proof['case']['metrics'],
            virtual_regions=virtual['regions'], signals=signals, comparisons=compact,
            original_terminal_and_cross_operator_failures_retained=True,
            physical_source_separation_or_new_sustained_voice_qualified=False,
            not_same_segment_as_prior_firstEarly=True)
        table = a.out / 'physical_bands.csv'
        with table.open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(['source', 'physical_band_kHz', 'L_FS2', 'R_FS2', 'Mid_FS2', 'Side_FS2',
                             'Side_over_Mid_dB', 'coherence_real', 'coherence_imag', 'CV_L', 'CV_R'])
            for name, s in signals.items():
                for b, band in enumerate(labels):
                    writer.writerow([name, band, *s['mean_power_FS2'][b], *s['mean_mid_side_FS2'][b],
                        s['side_over_mid_dB'][b], *s['complex_coherence'][b], *s['CV'][b]])
        r['table'] = dict(file=table.name, sha256=sha(table))
        figures = []
        for count, suffix in ((6, 'all_bands'), (5, '0_14k')):
            fig, axes = plt.subplots(2, 2, figsize=(13, 8), constrained_layout=True)
            x = np.arange(count)
            for name, color in (('FIR_only', '#756bb1'), ('fitted16', '#087e8b'), ('fitted32', '#d0643b')):
                c = compact[name + '_vs_raw']
                power = np.asarray(c['power_change_dB'])[:count]
                axes[0, 0].plot(x, power[:, 0], 'o-', color=color, label=name + ' L')
                axes[0, 0].plot(x, power[:, 1], 's--', color=color, label=name + ' R')
                axes[0, 1].plot(x, c['side_over_mid_change_dB'][:count], 'o-', color=color, label=name)
                coh = np.asarray(c['complex_coherence_change'])[:count]
                axes[1, 0].plot(x, np.linalg.norm(coh, axis=1), 'o-', color=color, label=name)
                cv = np.asarray(c['CV_change'])[:count]
                axes[1, 1].plot(x, cv[:, 0], 'o-', color=color, label=name + ' L')
                axes[1, 1].plot(x, cv[:, 1], 's--', color=color, label=name + ' R')
            for ax, title, unit in zip(axes.ravel(),
                ('Band power change vs raw', 'Side/Mid change vs raw',
                 'Complex LR coherence difference magnitude', 'Band-power CV change vs raw'),
                ('dB', 'dB', 'linear', 'linear')):
                ax.set_title(title); ax.set_ylabel(unit); ax.set_xlabel('Physical band (kHz)')
                ax.set_xticks(x, labels[:count]); ax.grid(alpha=.2); ax.axhline(0, color='#888', linewidth=.6)
                ax.legend(fontsize=8)
            fig.suptitle(label + '\nNo gain matching; finite fitted diagnostic, not a sustained engine or realism score'
                         + ('; 14k+ retained in all_bands' if count == 5 else ''))
            for ext in ('png', 'svg'):
                file = a.out / (suffix + '.' + ext)
                fig.savefig(file, dpi=150)
                figures.append(dict(file=file.name, sha256=sha(file)))
            plt.close(fig)
        r.update(result='locked_source_terminal_diagnostics_reviewed', figures=figures,
            no_gain_matching_C_default_or_hearing_change=True,
            all_six_physical_bands_retained=True, no_fitted_timeline_or_PCM_engine_loop=True)
        save(a.out / 'report.json', r)
        print('LOCKED_SOURCE_REVIEW', label, 'fidelity', r['flags']['source_fidelity_qualified'], flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error))
        save(a.out / 'report.json', r)
        raise


if __name__ == '__main__':
    main()
