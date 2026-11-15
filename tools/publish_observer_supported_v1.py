"""Publish supported/context/full-known evidence, including every failed qualification."""
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
    r = dict(result='running', inputs={}, no_runtime_or_hearing_promotion=True)
    try:
        folders = ('known1', 'known_audit3', 'context1', 'context_audit1',
                   'full1', 'full_audit1', 'null1', 'null_audit1')
        reports = {}
        for folder in folders:
            path = a.study/folder/'report.json'
            reports[folder] = load(path)
            r['inputs'][str(path)] = sha(path)
        for producer, audit in (('known1', 'known_audit3'), ('context1', 'context_audit1'),
                                ('full1', 'full_audit1'), ('null1', 'null_audit1')):
            assert reports[audit]['producer_sha256'] == sha(a.study/producer/'report.json')
        rows = []
        for old, new in zip(reports['known1']['cases'], reports['context1']['cases']):
            assert old['label'] == new['label']
            rows.append(dict(label=old['label'], no_context_high_NRMSE=old['variants']['supported']['high_component_NRMSE'],
                context_target_high_NRMSE=new['dense_metrics']['target_high_NRMSE'],
                context_whole_high_NRMSE=new['dense_metrics']['whole_high_NRMSE'],
                no_context_fidelity=old['fidelity_qualified'], context_target_fidelity=new['target_fidelity_qualified']))
        full = reports['full1']
        full_rows = [dict(band=name, target=v, whole=w) for name, v, w in zip(
            ('0-3k', '3-6k', '6-8k', '8-10k', '10-14k', '14-21.6k'),
            full['metrics']['target_supported_band_complex_NRMSE'], full['metrics']['whole_supported_band_complex_NRMSE'])]
        gates = dict(gradient_ratio=full['solver']['relative_stationarity']/2e-7,
            gap_ratio=full['certificate']['gap_upper_bound']/(1e-6*full['certificate']['primal']+1e-10),
            stop=full['solver']['stop'], iterations=full['solver']['iterations'])
        summary = dict(no_context_fidelity_passes=sum(x['no_context_fidelity'] for x in rows),
            context_target_fidelity_passes=sum(x['context_target_fidelity'] for x in rows), known_cases=8,
            full_solver_qualified=full['solver_qualified'], full_fidelity_qualified=full['fidelity_qualified'],
            full_target_wave_NRMSE=full['metrics']['target_wave_NRMSE'],
            maximum_target_band_NRMSE=max(x['target'] for x in full_rows),
            outer_loss_retained=rows[-1]['context_whole_high_NRMSE'],
            data_null_dimension_lower_bound=reports['null1']['data_null_dimension_lower_bound'],
            witness_data_norm=reports['null1']['witness_weighted_data_norm'],
            penalty_directional_derivative=reports['null1']['saved_fit_penalty_directional_derivative'],
            native_C_or_hearing_qualified=False)
        payload = dict(sparse_rows=rows, full_band_rows=full_rows, gates=gates, summary=summary)
        save(a.out/'figure_inputs.json', payload)
        fig, ax = plt.subplots(figsize=(12, 5.2), constrained_layout=True)
        x = np.arange(8)
        for key, label, style in (('no_context_high_NRMSE', 'No context: original target', 'o-'),
                                  ('context_target_high_NRMSE', 'Genuine context: same target', 's-'),
                                  ('context_whole_high_NRMSE', 'Genuine context: entire record', '^-')):
            ax.semilogy(x, [v[key] for v in rows], style, label=label)
        ax.axhline(.02, color='firebrick', linestyle='--', label='Original target gate: 2%')
        ax.set_xticks(x, [r['label'].replace('constant_', 'flat\n').replace('curved_', 'curved\n') for r in rows])
        ax.set_ylabel('High-component waveform NRMSE')
        ax.set_title('Eight exact known optima: context improves target, outer loss remains')
        ax.grid(True, which='both', alpha=.2)
        ax.legend(loc='upper left', fontsize=9)
        fig.savefig(a.out/'known_context.png', dpi=160)
        plt.close(fig)
        fig, axes = plt.subplots(1, 2, figsize=(12, 5.2), constrained_layout=True)
        ax = axes[0]
        for key, label, style in (('target', 'Original target support', 'o-'), ('whole', 'All fully supported rows', 's-')):
            ax.semilogy(np.arange(6), [row[key] for row in full_rows], style, label=label)
        ax.axhline(.02, color='firebrick', linestyle='--', label='Fidelity gate: 2%')
        ax.set_xticks(np.arange(6), [row['band'] for row in full_rows], rotation=25)
        ax.set_ylabel('Complex spectral NRMSE')
        ax.set_title('Full 288-order stereo known case: fidelity passes')
        ax.legend(fontsize=9)
        ax.grid(True, which='both', alpha=.2)
        ax = axes[1]
        ax.bar(['Original gradient', 'Primal-dual gap'], [gates['gradient_ratio'], gates['gap_ratio']], color=['#c17f35', '#b64d50'])
        ax.set_yscale('log')
        ax.axhline(1., color='black', linestyle='--')
        ax.set_ylim(.5, 1e7)
        ax.set_ylabel('Measured value / unchanged gate (must be <=1)')
        ax.set_title('Solver fails: stop 7 after fixed 4000 iterations')
        fig.savefig(a.out/'full_known_gates.png', dpi=160)
        plt.close(fig)
        r.update(result='observer_supported_publication_ready', summary=summary,
            figure_inputs_sha256=sha(a.out/'figure_inputs.json'),
            images={n:sha(a.out/n) for n in ('known_context.png', 'full_known_gates.png')},
            publisher_sha256=sha(__file__))
        save(a.out/'report.json', r)
        print(r['result'], summary, flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error))
        save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
