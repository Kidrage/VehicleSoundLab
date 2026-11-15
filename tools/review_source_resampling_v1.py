"""Publish resampling transfer, all-radius sensitivity and saved-fit mismatch."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from itertools import combinations
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('workspace', 'out'):
        p.add_argument('--'+key, type=Path, required=True)
    a = p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'): os.environ[key] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from native_error_budget_v1.assessment import locked_rows
    repo = Path(__file__).resolve().parents[1]
    root = a.workspace/'references/analysis/source_resampling_v1'
    a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', sources={}, inputs={}, cases=[])
    try:
        for name in ('tools/review_source_resampling_v1.py', 'tools/audit_source_resampling_review_v1.py',
            'tools/native_error_budget_v1/assessment.py', 'research/source_resampling_v1_plan.json'):
            dest = a.out/'exact_sources'/name; dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, dest); r['sources'][name] = sha(dest)
        def read(path):
            path = Path(path); r['inputs'][str(path)] = sha(path); return load(path)
        known, ka = read(root/'known1/report.json'), read(root/'known_audit1/report.json')
        real, ra = read(root/'real1/report.json'), read(root/'real_audit1/report.json')
        assert ka['all_known_qualified'] and ra['all_actual_cases_verified']
        assert ka['producer_sha256'] == sha(root/'known1/report.json')
        assert ra['producer_sha256'] == sha(root/'real1/report.json')
        for case in real['cases']:
            path = root/'real1'/case['file']; assert sha(path) == case['sha256']
            r['inputs'][str(path)] = sha(path)
            with np.load(path) as f: z = {key: f[key] for key in f.files}
            info = case['measurements']; old = sum(info['legacy']['highest_split_Welch_FS2_LR'][-1])
            new = sum(info['sinc128']['highest_split_Welch_FS2_LR'][-1])
            pairs = []
            for first, second in combinations(('sinc64', 'sinc128', 'sinc256'), 2):
                delta = z[first][2048:-2048]-z[second][2048:-2048]
                pairs.append(dict(first=first, second=second,
                    target_wave_NRMSE_relative_legacy=float(np.linalg.norm(delta)/np.linalg.norm(z['legacy'][2048:-2048])),
                    maximum_FS=float(np.max(abs(delta)))))
            changes = info['sinc128']['signed_stereo_and_temporal_changes_vs_legacy']
            r['cases'].append(dict(label=case['label'], tail_Welch_FS2_LR={
                name: info[name]['highest_split_Welch_FS2_LR'][-1] for name in info},
                sinc128_over_legacy_tail_power=new/old,
                main0_14k_max_abs_band_power_change_dB=max(abs(v) for band in changes['power_change_dB'][:5] for v in band),
                main0_14k_max_abs_LR_complex_component_change=max(abs(v) for band in changes['complex_coherence_change'][:5] for v in band),
                sinc128_target_wave_NRMSE_vs_legacy=info['sinc128']['target_wave_NRMSE_vs_legacy'],
                all_radius_pairs=pairs))
        # This is an intentionally non-qualifying cross-reference test. Keep
        # the saved solution fixed and retain regressions against NEW inputs.
        case = a.workspace/'references/analysis/waveform_file_real_v1/real1/F3 Fifth First Early'
        math = read(a.workspace/'references/analysis/waveform_real_guard_v1/real_audit1/report.json')
        assert math['verification_passed'] and not math['all_qualified']
        for path in (case/'capture.npz', case/'report.json'): r['inputs'][str(path)] = sha(path)
        with np.load(case/'capture.npz') as f:
            fitted, weights, amplitude = f['wave'][2048:-2048], f['weights'], float(f['amplitude'])
        with np.load(root/'real1/F3 Fifth First Early.npz') as f:
            reference_variants = {name: f[name][2048:-2048] for name in ('legacy', 'sinc64', 'sinc128', 'sinc256')}
        frequency = np.arange(2049)*16
        groups = np.digitize(frequency, [3000, 6000, 8000, 10000, 14000])
        cross = {}
        for name, target in reference_variants.items():
            Y, _, _, _ = locked_rows(target, weights, amplitude)
            E, _, _, _ = locked_rows(fitted-target, weights, amplitude)
            cross[name] = [float(np.linalg.norm(E[:, groups == b])/np.linalg.norm(Y[:, groups == b])) for b in range(6)]
        original = load(case/'report.json')['metrics']['target_supported_band_complex_NRMSE']
        assert np.max(abs(np.array(cross['legacy'])-original)) < 2e-12
        r.update(saved_fit_cross_reference_complex_NRMSE=cross,
            cross_reference_is_not_a_new_solver_or_fidelity_qualification=True,
            old_solution_cannot_be_reused_as_qualified_fit_to_new_reference=True,
            original_source_fidelity_qualified=False, eligible_for_later_source_statistics=False,
            resampler_transfer_improvement_is_not_audible_realism_or_sustained_engine_acceptance=True,
            known_cases=len(known['cases']), known_and_actual_independent_audits_passed=True)
        labels = ['First Early', 'First Mid', 'First Late', 'Second Early', 'Second Mid', 'Second Late']
        fig, axes = plt.subplots(1, 2, figsize=(13, 5), constrained_layout=True)
        x = np.arange(6)
        for name in ('legacy', 'sinc64', 'sinc128', 'sinc256'):
            powers = [sum(c['tail_Welch_FS2_LR'][name]) for c in r['cases']]
            axes[0].semilogy(x, powers, 'o-', label=name)
        axes[0].set_xticks(x, labels, rotation=30, ha='right'); axes[0].set_ylabel('Welch power FS^2, combined LR')
        axes[0].set_title('Strictly above18.432k carrier centre, virtual phase grid'); axes[0].legend()
        axes[1].plot(x, [c['main0_14k_max_abs_band_power_change_dB'] for c in r['cases']], 'o-', label='Max |band power change|')
        axes[1].set_xticks(x, labels, rotation=30, ha='right'); axes[1].set_ylabel('dB, sinc128 vs legacy')
        axes[1].set_title('Main0-14k virtual bands remain close'); axes[1].legend()
        for ax in axes: ax.grid(alpha=.2)
        fig.suptitle('Same source, same FIR and common LR clock; source interpolation only')
        for ext in ('png', 'svg'): fig.savefig(a.out/('source_transfer.'+ext), dpi=150)
        plt.close(fig)
        fig, ax = plt.subplots(figsize=(10, 5), constrained_layout=True)
        for name, values in cross.items(): ax.semilogy(range(6), values, 'o-', label=name+' reference')
        ax.axhline(.02, color='#a22', ls='--', label='Original0.02 gate (unchanged)')
        ax.set_xticks(range(6), ('0-3', '3-6', '6-8', '8-10', '10-14', '14-32.768'))
        ax.set_xlabel('Virtual phase-grid band (kHz)'); ax.set_ylabel('Complex NRMSE')
        ax.set_title('Same OLD saved fit vs changed inputs: no refit, no new qualification')
        ax.grid(alpha=.2); ax.legend()
        for ext in ('png', 'svg'): fig.savefig(a.out/('saved_fit_cross_reference.'+ext), dpi=150)
        plt.close(fig)
        r['figures'] = {path.name: sha(path) for path in a.out.iterdir() if path.suffix in ('.png', '.svg')}
        r['result'] = 'source_resampling_review_published'
        save(a.out/'report.json', r)
        print(r['result'], 'saved highest', {k: v[-1] for k, v in cross.items()}, flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error)); save(a.out/'report.json', r); raise


if __name__ == '__main__': main()
