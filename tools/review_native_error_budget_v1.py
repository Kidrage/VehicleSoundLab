"""Publish audited component budgets, exact locked frequency split and figures."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('workspace', 'study', 'audit', 'out'):
        p.add_argument('--'+key, type=Path, required=True)
    a = p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[key] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from native_error_budget_v1.assessment import locked_rows, virtual_split, physical_summary, sensitivity
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', sources={}, inputs={})
    try:
        for name in ('tools/review_native_error_budget_v1.py', 'tools/audit_native_error_assessment_v1.py',
            'tools/native_error_budget_v1/assessment.py', 'research/native_error_assessment_v1_plan.json',
            'tools/research_archive_v1.py'):
            dest = a.out/'exact_sources'/name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, dest); r['sources'][name] = sha(dest)
        source, audit = load(a.study/'report.json'), load(a.audit/'report.json')
        assert audit['verification_passed'] and audit['producer_sha256'] == sha(a.study/'report.json')
        assert source['result'] == 'actual_native_error_budget_measured'
        for name, digest in source['inputs'].items():
            assert sha(name) == digest
        for path in (a.study/'report.json', a.audit/'report.json'):
            r['inputs'][str(path)] = sha(path)
        # Qualification runs before reading the actual target. Endpoint tones
        # make omission of DC/Nyquist factors observable.
        n = np.arange(4096)
        known = np.column_stack((.2+.08*(-1.)**n+.15*np.cos(2*np.pi*1024*n/4096)
            +.03*np.sin(2*np.pi*1153*n/4096),
            -.1+.03*(-1.)**n+.11*np.sin(2*np.pi*1100*n/4096)))
        kw = np.linspace(.5, 1.5, 2049)
        rows, power, coverage, starts = locked_rows(known, kw, .7)
        w = .5-.5*np.cos(2*np.pi*n/4096)
        direct = np.empty((2049, 2), complex)
        conventional = np.empty_like(direct)
        for first in range(0, 2049, 64):
            k = np.arange(first, min(first+64, 2049))
            basis = np.exp(-2j*np.pi*k[:, None]*n[None]/4096)
            direct[first:first+len(k)] = basis@(known*w[:, None]/np.sqrt(coverage[:, None]))
            conventional[first:first+len(k)] = basis@(known*w[:, None])
        endpoint = np.r_[1., np.full(2047, 2.), 1.]
        direct *= (.7*np.sqrt(endpoint/4096)*kw)[:, None]
        check = float(np.max(abs(rows[0]-direct))/np.max(abs(direct)))
        pcheck = float(np.max(abs(power-abs(conventional)**2*endpoint[:, None]
            /(4096*np.dot(w, w))))/np.max(power))
        assert check < 2e-11 and pcheck < 2e-11
        np.savez_compressed(a.out/'known.npz', audio=known, weights=kw, rows=rows,
            power=power, coverage=coverage, starts=starts, direct_DFT=direct)
        r['known'] = dict(all2049bins_directDFT_relative_error=check,
            all2049bins_Welch_relative_error=pcheck, gate=2e-11, passed=True)
        case = Path(source['source']['binding_file']).parent/source['source']['label']
        for path in (case/'capture.npz', case/'report.json'):
            r['inputs'][str(path)] = sha(path)
        with np.load(case/'capture.npz') as f:
            z = {k: f[k] for k in ('target', 'wave', 'weights', 'amplitude', 'orders')}
        arrays, virtual = virtual_split(z['target'], z['wave'][2048:-2048],
            z['weights'], float(z['amplitude']), z['orders'])
        original = load(case/'report.json')['metrics']['target_supported_band_complex_NRMSE']
        actual = [b['combined_complex_NRMSE'] for b in virtual['original_bands']]
        assert np.max(abs(np.array(actual)-original)) < 2e-12
        variants, physical = [], []
        for row in source['variants']:
            path = a.study/row['file']; assert sha(path) == row['sha256']
            r['inputs'][str(path)] = sha(path)
            with np.load(path) as f:
                v = {k: f[k] for k in f.files}
            variants.append((row['file'], v))
            physical.append(dict(radius=row['radius'], up=row['up'], file=row['file'], **physical_summary(v)))
        r.update(virtual=virtual, physical=physical, sensitivity=sensitivity(variants),
            original_target_NRMSE=original, source_solver_qualified=True,
            source_fidelity_qualified=False, eligible_for_later_source_statistics=False,
            source_fidelity_gate_unchanged=.02,
            no_physical_inverse_or_sustained_source_or_C_or_listening_qualification=True)
        np.savez_compressed(a.out/'virtual_split.npz', **arrays)
        r['arrays'] = {name: sha(a.out/name) for name in ('known.npz', 'virtual_split.npz')}
        # Keep full-band and low/mid/high detail visible independently.
        focus = physical[2]
        colors = ('#557c93', '#b86b2f', '#16816e', '#8a609e')
        names = ('Source FIR', 'Declared grid reconstruction', 'Grid fit', 'Continuous minus reconstructed grid')
        labels = ('0-3', '3-6', '6-8', '8-10', '10-14', '14-24')
        fig, axes = plt.subplots(1, 2, figsize=(14, 5), constrained_layout=True)
        for j, (name, color) in enumerate(zip(names, colors)):
            value = np.asarray(focus['combined_component_NRMSE'])[:, j]
            axes[0].semilogy(range(6), value, 'o-', color=color, label=name)
        axes[0].semilogy(range(6), focus['combined_total_NRMSE'], 'k--', label='Total with signed cross terms')
        axes[0].set_xticks(range(6), labels); axes[0].set_xlabel('Physical band (kHz)')
        axes[0].set_ylabel('Component / raw-reference NRMSE'); axes[0].legend(fontsize=8)
        axes[0].set_title('Four-component diagnostic, radius128 / 16x')
        auto = np.asarray(focus['component_auto_Welch_FS2_LR']).sum(axis=2)
        cross = np.asarray(focus['component_signed_cross_Welch_FS2_LR']).sum(axis=3)
        ref = np.asarray(focus['reference_Welch_FS2_LR']).sum(axis=1)
        for b in (4, 5):
            terms = np.r_[auto[b], [cross[b, i, j] for i in range(4) for j in range(i+1, 4)]]/ref[b]
            axes[1].plot(range(10), terms, 'o-', label=labels[b]+' kHz')
        axes[1].set_yscale('symlog', linthresh=1e-8); axes[1].axhline(0, color='#777777', lw=.6)
        axes[1].set_xticks(range(10), ('FIR', 'Grid', 'Fit', 'Cont.', 'F/G', 'F/Fit', 'F/C', 'G/Fit', 'G/C', 'Fit/C'), rotation=45)
        axes[1].set_ylabel('Signed power / raw band power (not percentages)')
        axes[1].set_title('Autos and all six signed cross terms'); axes[1].legend()
        for ax in axes: ax.grid(alpha=.2)
        fig.suptitle('F3 Fifth First Early | S is a declared reconstruction, not a unique physical inverse')
        for extension in ('png', 'svg'): fig.savefig(a.out/('physical_budget.'+extension), dpi=150)
        plt.close(fig)
        fig, axes = plt.subplots(1, 2, figsize=(13, 5), constrained_layout=True)
        rows = virtual['highest_band_split']; x = np.arange(4)
        reference = np.array([sum(v['reference_weighted_mass_LR']) for v in rows])
        error = np.array([sum(v['error_weighted_mass_LR']) for v in rows])
        axes[0].bar(x-.18, reference, .36, label='Reference'); axes[0].bar(x+.18, error, .36, label='Error')
        axes[0].set_yscale('log'); axes[0].set_ylabel('Original locked observer squared mass')
        axes[0].set_title('Original virtual 14k+ band; all bins retained'); axes[0].legend()
        axes[1].semilogy(x, [v['combined_complex_NRMSE'] for v in rows], 'o-')
        axes[1].axhline(.02, color='#ad3030', ls='--', label='Original whole-band gate 0.02')
        axes[1].set_ylabel('Sub-band complex NRMSE (diagnostic only)'); axes[1].legend(fontsize=8)
        axes[1].set_title('Carrier centre is not a strict bandwidth cutoff')
        for ax in axes:
            ax.set_xticks(x, ('14-16k', '16-18.432k\nexclusive', '18.432k\ncentre', '>18.432k'))
            ax.grid(axis='y', alpha=.2)
        fig.suptitle('Original 14k+ gate remains FAILED; no sub-band replaces its admission test')
        for extension in ('png', 'svg'): fig.savefig(a.out/('virtual_split.'+extension), dpi=150)
        plt.close(fig)
        r['figures'] = {p.name: sha(p) for p in sorted(a.out.glob('*')) if p.suffix in ('.png', '.svg')}
        r['result'] = 'native_error_assessment_published'
        save(a.out/'report.json', r)
        print('NATIVE_ERROR_ASSESSMENT', 'original', actual[-1], 'above_error_fraction',
            virtual['above_centre_error_fraction_of_highest_weighted_mass'], flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error)); save(a.out/'report.json', r); raise


if __name__ == '__main__':
    main()
