"""Publish compact actual HF/stereo/time findings from audited real cases."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'batch', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace / 'tools/python_deps'))
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', cases=[], sources={}, inputs={})
    try:
        for name in ('tools/review_actual_native_cases_v1.py', 'tools/audit_actual_native_review_v1.py',
                     'research/actual_native_review_v1_plan.json', 'tools/research_archive_v1.py'):
            dest = a.out / 'exact_sources' / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo / name, dest); r['sources'][name] = sha(dest)
        publication = load(a.batch / 'report.json')
        assert publication['only_one_finite_dependent_run'] and publication['cases']
        # Mutable root state only selects immutable results; it is not an
        # immutable scientific input and is never used as a fit certificate.
        save(a.out / 'observed_batch_publication.json', publication)
        for published in publication['cases']:
            base = a.batch / published['label']
            case_file = base / 'report.json'
            assert sha(case_file) == published['report_sha256']
            case = load(case_file)
            assert case['result'] == 'real_case_virtual_and_native_diagnostics_verified'
            assert len(case['steps']) == 4 and all(step['exit_code'] == 0 for step in case['steps'])
            native_file, audit_file = base / 'native/report.json', base / 'native_audit/report.json'
            assert sha(native_file) == case['native_report_sha256']
            assert sha(audit_file) == case['native_audit_sha256']
            native, audit = load(native_file), load(audit_file)
            assert audit['result'] == 'independent_actual_native_clock_case_verified' and audit['verification_passed']
            assert audit['producer_sha256'] == sha(native_file)
            for key in ('source_solver_qualified', 'source_fidelity_qualified',
                        'native16_32_convergence_passed', 'eligible_for_later_source_statistics'):
                assert case[key] == native[key] == audit[key] == published[key]
            sound_file = base / 'native' / native['sound']['file']
            assert sha(sound_file) == native['sound']['sha256']
            for path in (case_file, native_file, audit_file, sound_file):
                r['inputs'][str(path)] = sha(path)
            with np.load(sound_file) as f:
                z = {key: f[key] for key in f.files}
            signals = {}
            for name in ('raw', 'FIR_only', 'fitted16', 'fitted32'):
                mid_side = z[name + '_broad_mean_mid_side']
                ratios = [float(10 * np.log10(s / m)) if s > 0 and m > 0 else None for m, s in mid_side]
                coherence = z[name + '_broad_complex_coherence']
                signals[name] = dict(mean_power_FS2=z[name + '_broad_mean_power'].tolist(),
                    mean_mid_side_FS2=mid_side.tolist(), side_over_mid_dB=ratios,
                    complex_coherence=[[float(v.real), float(v.imag)] for v in coherence],
                    CV=z[name + '_broad_CV'].tolist(), precision=native['sound']['precision'][name]['broad'])
            row = dict(label=published['label'],
                **{key: case[key] for key in ('source_solver_qualified', 'source_fidelity_qualified',
                    'native16_32_convergence_passed', 'eligible_for_later_source_statistics')},
                original_weighted_errors=native['source']['existing_weighted_metrics'],
                signals=signals, comparisons=native['comparisons'],
                native_report=str(native_file), native_audit=str(audit_file), sound_file=str(sound_file),
                native_frames=native['sound']['frames'], physical_rate=48000)
            output = a.out / (published['label'] + '.json'); save(output, row)
            fig, axes = plt.subplots(2, 2, figsize=(13, 8), constrained_layout=True)
            labels = ['0-3', '3-6', '6-8', '8-10', '10-14', '14-24']
            x = np.arange(6)
            colors = dict(fitted16='#006d77', fitted32='#b24427')
            for name in ('fitted16', 'fitted32'):
                changed = native['comparisons'][name + '_vs_raw']['signed_changes']['broad']
                power = np.asarray(changed['power_change_dB'], float)
                axes[0, 0].plot(x, power[:, 0], 'o-', color=colors[name], label=name + ' L')
                axes[0, 0].plot(x, power[:, 1], 's--', color=colors[name], label=name + ' R')
                side = np.array([np.nan if v is None else v for v in signals[name]['side_over_mid_dB']])
                refside = np.array([np.nan if v is None else v for v in signals['raw']['side_over_mid_dB']])
                axes[0, 1].plot(x, side - refside, 'o-', color=colors[name], label=name)
                coh = np.asarray(signals[name]['complex_coherence']) - np.asarray(signals['raw']['complex_coherence'])
                axes[1, 0].plot(x, coh[:, 0], 'o-', color=colors[name], label=name + ' real')
                axes[1, 0].plot(x, coh[:, 1], 's--', color=colors[name], label=name + ' imag')
                cv = np.asarray(signals[name]['CV']) - np.asarray(signals['raw']['CV'])
                axes[1, 1].plot(x, cv[:, 0], 'o-', color=colors[name], label=name + ' L')
                axes[1, 1].plot(x, cv[:, 1], 's--', color=colors[name], label=name + ' R')
            for ax, title, unit in zip(axes.ravel(),
                ('Band power error vs raw', 'Side/Mid change vs raw', 'Complex LR coherence change', 'Band-power CV change'),
                ('dB', 'dB', 'linear', 'linear')):
                ax.set_title(title); ax.set_ylabel(unit); ax.set_xlabel('Physical band (kHz)')
                ax.set_xticks(x, labels); ax.axhline(0, color='#777777', linewidth=.7)
                ax.grid(alpha=.2); ax.legend(fontsize=8)
            fig.suptitle(published['label'] + '\nActual fitted interval; no gain matching; not a realism score')
            figure = a.out / (published['label'] + '.png')
            vector = a.out / (published['label'] + '.svg')
            fig.savefig(figure, dpi=150); fig.savefig(vector)
            # Keep the original all-band figure. A second explicit main-band
            # view prevents an extremely weak14k+ band from hiding real changes
            # below14k. Only plot limits change; all values/gates stay intact.
            for ax in axes.ravel():
                visible = [0.]
                for line in ax.lines:
                    y = np.asarray(line.get_ydata(), dtype=float)
                    if len(y) == 6:
                        visible.extend(y[:5][np.isfinite(y[:5])].tolist())
                        line.set_data(x[:5], y[:5])
                lo, hi = min(visible), max(visible)
                margin = max(1e-14, .15*(hi-lo))
                ax.set_xlim(-.2, 4.2); ax.set_ylim(lo-margin, hi+margin)
                ax.set_xticks(x[:5], labels[:5])
            fig.suptitle(published['label'] + '\n0-14kHz detail view;14k+ retained in the separate full-band figure')
            focus = a.out / (published['label'] + '_0-14k.png')
            focus_vector = a.out / (published['label'] + '_0-14k.svg')
            fig.savefig(focus, dpi=150); fig.savefig(focus_vector); plt.close(fig)
            r['cases'].append(dict(label=published['label'], file=output.name, sha256=sha(output),
                figure=figure.name, figure_sha256=sha(figure), vector=vector.name, vector_sha256=sha(vector),
                focus_figure=focus.name, focus_figure_sha256=sha(focus),
                focus_vector=focus_vector.name, focus_vector_sha256=sha(focus_vector),
                eligible_for_later_source_statistics=case['eligible_for_later_source_statistics']))
            save(a.out / 'report.json', r)
            print('ACTUAL_NATIVE_REVIEW', published['label'], flush=True)
        r.update(result='actual_native_cases_publication_prepared', no_gain_matching_or_source_separation_or_C_promotion=True,
                 no_listening_or_sustained_or_multiengine_qualification=True)
        save(a.out / 'report.json', r)
    except BaseException as error:
        r.update(result='failed', error=repr(error)); save(a.out / 'report.json', r); raise


if __name__ == '__main__':
    main()
