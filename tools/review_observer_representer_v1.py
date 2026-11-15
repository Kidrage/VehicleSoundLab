"""Publish all representer controls, failures and old/new full-known regressions."""
import argparse, os, shutil, sys
from pathlib import Path
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'study', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    os.environ['MPLBACKEND'] = 'Agg'
    import numpy as np
    import matplotlib.pyplot as plt
    a.out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, a.out/'executed_publication.py')
    r = dict(result='running', inputs={})
    try:
        reports = {}
        for folder in ('algebra2', 'algebra_audit1', 'primal_algebra1', 'primal_algebra_audit1',
                       'context1', 'context_audit1', 'full1', 'full_audit1'):
            path = a.study/folder/'report.json'
            reports[folder] = load(path)
            r['inputs'][str(path)] = sha(path)
        for source, audit in (('algebra2', 'algebra_audit1'), ('primal_algebra1', 'primal_algebra_audit1'),
                              ('context1', 'context_audit1'), ('full1', 'full_audit1')):
            assert reports[audit]['producer_sha256'] == sha(a.study/source/'report.json')
        tiny = [dict(label=d['label'], failed_dual_error=d['stats']['iterative_dual']['dense_relative_error'],
                     primal_error=p['stats']['iterative_primal']['dense_relative_error'],
                     dual_pass=d['qualified'], primal_pass=p['qualified'])
            for d, p in zip(reports['algebra2']['cases'], reports['primal_algebra1']['cases'])]
        context = [dict(label=c['label'], node_error=c['dense_relative_error'], qualified=c['qualified'],
                        **c['metrics']) for c in reports['context1']['cases']]
        f = reports['full1']
        old, new = f['old_results'], f['metrics']
        bands = [dict(band=b, old_target=ot, new_target=nt, old_whole=ow, new_whole=nw) for b, ot, nt, ow, nw in zip(
            ('0-3k', '3-6k', '6-8k', '8-10k', '10-14k', '14-21.6k'),
            old['target_supported_band_complex_NRMSE'], new['target_supported_band_complex_NRMSE'],
            old['whole_supported_band_complex_NRMSE'], new['whole_supported_band_complex_NRMSE'])]
        gates = dict(old_gradient=f['old_solver']['relative_stationarity']/2e-7,
            new_gradient=f['solver']['relative_stationarity']/2e-7,
            old_residual_gap=f['old_certificate']['gap_upper_bound']/(1e-6*f['old_certificate']['primal']+1e-10),
            new_residual_gap=f['residual_certificate']['gap_upper_bound']/(1e-6*f['residual_certificate']['primal']+1e-10),
            new_representer_gap=f['representer_certificate']['gap_upper_bound']/(1e-6*f['representer_certificate']['primal']+1e-10))
        summary = dict(dual_algebra_passes=sum(v['dual_pass'] for v in tiny), primal_algebra_passes=sum(v['primal_pass'] for v in tiny),
            actual_Hann_passes=sum(v['qualified'] for v in context), full_solver_qualified=f['solver_qualified'],
            full_fidelity_qualified=f['fidelity_qualified'], old_objective=f['old_certificate']['primal'],
            new_objective=f['residual_certificate']['primal'], old_wave=old['whole_wave_NRMSE'], new_wave=new['whole_wave_NRMSE'],
            old_target_wave=old['target_wave_NRMSE'], new_target_wave=new['target_wave_NRMSE'],
            target_band_regressions=sum(v['new_target'] > v['old_target'] for v in bands),
            whole_band_regressions=sum(v['new_whole'] > v['old_whole'] for v in bands),
            region_regressions=sum(n > o for o, n in zip(old['whole_wave_regions_NRMSE'], new['whole_wave_regions_NRMSE'])),
            old_region_errors=old['whole_wave_regions_NRMSE'], new_region_errors=new['whole_wave_regions_NRMSE'],
            original_outer_high_loss=context[-1]['whole_high_NRMSE'],
            null_witness_penalty_derivative=reports['full_audit1']['saved_null_witness_penalty_derivative'],
            source_or_runtime_or_hearing_qualified=False)
        payload = dict(tiny=tiny, context=context, bands=bands, gates=gates, summary=summary)
        save(a.out/'figure_inputs.json', payload)
        fig, ax = plt.subplots(figsize=(9, 4.8), constrained_layout=True)
        x = np.arange(4)
        ax.semilogy(x, [v['failed_dual_error'] for v in tiny], 'o-', label='Observation-dual iteration: failed')
        ax.semilogy(x, [v['primal_error'] for v in tiny], 's-', label='Penalty-whitened primal: passed')
        ax.axhline(2e-7, color='firebrick', linestyle='--', label='Original node-error gate')
        ax.set_xticks(x, [v['label'] for v in tiny])
        ax.set_ylabel('Relative error against original dense optimum')
        ax.set_title('Same four algebra fixtures; solver recovery precision matters')
        ax.grid(True, which='both', alpha=.2)
        ax.legend(loc='upper center', bbox_to_anchor=(.5, -.12), fontsize=9)
        fig.savefig(a.out/'algebra.png', dpi=160)
        plt.close(fig)
        fig, axes = plt.subplots(2, 2, figsize=(12, 9), constrained_layout=True)
        for ax, scope in zip(axes[0], ('target', 'whole')):
            for prefix, label, style in (('old_', 'Previous block solve', 'o-'), ('new_', 'Penalty-whitened solve', 's-')):
                ax.semilogy(np.arange(6), [b[prefix+scope] for b in bands], style, label=label)
            ax.set_xticks(np.arange(6), [b['band'] for b in bands], rotation=20)
            ax.set_title('Full288 stereo: '+scope+' spectral error')
            ax.set_ylabel('Complex spectral NRMSE')
            ax.grid(True, which='both', alpha=.2)
            ax.legend(fontsize=8)
        ax = axes[1, 0]
        x = np.arange(2)
        ax.bar(x-.18, [gates['old_gradient'], gates['old_residual_gap']], .36, label='Previous')
        ax.bar(x+.18, [gates['new_gradient'], gates['new_residual_gap']], .36, label='New')
        ax.set_yscale('log')
        ax.axhline(1., color='black', linestyle='--')
        ax.set_xticks(x, ['Original gradient', 'Residual-dual gap'])
        ax.set_ylim(.5, 1e7)
        ax.set_ylabel('Value / unchanged gate (must be <=1)')
        ax.set_title('Both full solves stop7/4000: NOT qualified')
        ax.legend(fontsize=8)
        ax = axes[1, 1]
        x = np.arange(3)
        ax.bar(x-.18, old['whole_wave_regions_NRMSE'], .36, label='Previous')
        ax.bar(x+.18, new['whole_wave_regions_NRMSE'], .36, label='New')
        ax.set_yscale('log')
        ax.set_xticks(x, ['First guard', 'Original target', 'Last guard'])
        ax.set_ylabel('Waveform NRMSE')
        ax.set_title('All three waveform regions regress')
        ax.legend(fontsize=8)
        fig.savefig(a.out/'full_comparison.png', dpi=160)
        plt.close(fig)
        r.update(result='observer_representer_review_ready', summary=summary,
            figure_inputs_sha256=sha(a.out/'figure_inputs.json'), publisher_sha256=sha(__file__),
            images={n:sha(a.out/n) for n in ('algebra.png', 'full_comparison.png')})
        save(a.out/'report.json', r)
        print(r['result'], summary, flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error))
        save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
