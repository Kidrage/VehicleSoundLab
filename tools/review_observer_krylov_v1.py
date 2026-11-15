"""Scientific diagnostic figures, including the eight new stopping failures."""
import argparse, os, shutil, sys
from pathlib import Path
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'study', 'parent', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    os.environ['MPLBACKEND'] = 'Agg'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    import matplotlib.pyplot as plt
    a.out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, a.out/'executed_publication.py')
    inputs = {}
    def read(path):
        inputs[str(path)] = sha(path)
        return load(path)
    full = read(a.study/'full1/report.json')
    fa = read(a.study/'full_audit1/report.json')
    known = read(a.study/'known1/report.json')
    ka = read(a.study/'known_audit1/report.json')
    reorth = read(a.study/'reorth_known1/report.json')
    ra = read(a.study/'reorth_known_audit1/report.json')
    old_a = read(a.parent/'primal_algebra1/report.json')
    old_h = read(a.parent/'context1/report.json')
    assert fa['result'] == 'independent_observer_krylov_full_passed'
    assert ka['result'] == 'independent_observer_krylov_known_passed'
    assert ra['result'] == 'independent_observer_reorth_known_passed' and ra['pass_count'] == 4
    with np.load(a.study/'full1/coefficients.npz') as z:
        grams = [z['U_gram'], z['V_gram']]
    inputs[str(a.study/'full1/coefficients.npz')] = sha(a.study/'full1/coefficients.npz')
    prefixes = []
    for g in grams:
        off = abs(g-np.diag(np.diag(g)))
        prefixes.append([float(off[:j, :j].max()) for j in range(1, len(g)+1)])
    old_errors = [c['stats']['iterative_primal']['dense_relative_error'] for c in old_a['cases']]
    old_errors += [c['dense_relative_error'] for c in old_h['cases']]
    rows = reorth['cases']
    new_errors = [c['dense_relative_error'] for c in rows]
    stop_ratios = [c['solver']['transformed_normal_norm']/(c['solver']['projected_Frobenius_estimate']*c['solver']['residual_norm']*1e-11) for c in rows]
    dense_ratios = [c['independent_original_dense_transformed_normal_relative']/1e-11 for c in ra['cases']]
    labels = [c['label'].replace('constant_', 'const\n').replace('curved_', 'curve\n').replace('silent_right', 'silent R') for c in rows]
    figures = dict(prefixes=prefixes, old_node_errors=old_errors, new_node_errors=new_errors,
        direct_stop_ratio=stop_ratios, independent_dense_stop_ratio=dense_ratios,
        labels=labels, qualified=[c['qualified'] for c in rows], stops=[c['solver']['stop'] for c in rows])
    save(a.out/'figure_inputs.json', figures)
    plt.rcParams.update({'font.size':10, 'axes.titlesize':12, 'figure.dpi':150})
    fig, axes = plt.subplots(2, 2, figsize=(11.2, 8.2), constrained_layout=True)
    for j, (g, prefix, tag) in enumerate(zip(grams, prefixes, ('left U', 'right V'))):
        off = abs(g-np.diag(np.diag(g)))
        im = axes[0, j].imshow(off, vmin=0, vmax=1, origin='lower', cmap='magma')
        axes[0, j].set(title=tag+' off-diagonal absolute inner products', xlabel='Basis column', ylabel='Basis column')
        fig.colorbar(im, ax=axes[0, j], fraction=.046)
        axes[1, j].semilogy(np.arange(len(prefix)), np.maximum(prefix, 1e-18))
        axes[1, j].axhline(1e-8, linestyle='--', color='#c64c35', label='Diagnostic 1e-8 level')
        axes[1, j].set(xlabel='Last column in prefix (zero based)', ylabel='Largest off-diagonal magnitude', ylim=(1e-18, 2), title=tag+' loss by prefix')
        axes[1, j].legend(loc='lower right')
        axes[1, j].grid(alpha=.2)
    fig.suptitle('Same full288 operator: 128-step probe loses orthogonality\nAll128 forward/adjoint recurrences independently checked; no new solve', fontsize=14)
    fig.savefig(a.out/'full_orthogonality.png')
    plt.close(fig)
    fig, axes = plt.subplots(2, 1, figsize=(12.5, 8.2), constrained_layout=True)
    x = np.arange(12)
    axes[0].semilogy(x, old_errors, 'o-', label='Previous penalty-whitened LSMR')
    axes[0].semilogy(x, new_errors, 's-', label='Two-sided reorthogonalized projection')
    axes[0].axhline(2e-7, linestyle='--', color='#c64c35', label='Original node-error gate 2e-7')
    axes[0].set(title='Node accuracy improves; this alone does not qualify a solver', ylabel='Relative error to frozen dense optimum', xticks=x, xticklabels=labels, ylim=(1e-14, 1e-6))
    axes[0].legend(loc='upper center')
    axes[1].semilogy(x, stop_ratios, 's-', label='New solver: saved direct normal test / tolerance')
    axes[1].semilogy(x, dense_ratios, 'o--', label='Independent original dense optimum: direct test / tolerance')
    axes[1].axhline(1, linestyle='--', color='#c64c35', label='Declared 1e-11 stopping level')
    axes[1].set(title='4/12 qualify; all8 Hann stopping failures retained (stop7)', ylabel='Ratio to normal-test tolerance', xticks=x, xticklabels=labels)
    axes[1].legend(loc='lower right')
    for ax in axes:
        ax.axvline(3.5, color='gray', linewidth=.8)
        ax.grid(alpha=.2)
    fig.suptitle('Reorthogonalized known controls: accurate parameters, unresolved stopping arithmetic', fontsize=14)
    fig.savefig(a.out/'known_stopping.png')
    plt.close(fig)
    images = {name:sha(a.out/name) for name in ('full_orthogonality.png', 'known_stopping.png')}
    save(a.out/'report.json', dict(result='observer_krylov_review_ready', inputs=inputs, images=images,
        summary=dict(known_controls=11, full_probe_steps=128, full_U_max_offdiagonal=full['info']['U_max_offdiagonal'],
            full_V_max_offdiagonal=full['info']['V_max_offdiagonal'], reorth_cases=12, reorth_passes=4,
            reorth_stopping_failures=8, max_new_node_error=max(new_errors),
            full_fit_or_real_source_or_timbre_qualified=False),
        publisher_sha256=sha(__file__), figure_inputs_sha256=sha(a.out/'figure_inputs.json')))
    print('observer_krylov_review_ready', flush=True)


if __name__ == '__main__':
    main()
