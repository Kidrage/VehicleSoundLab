"""Publish qualified small controls only; never read or freeze the live full solve."""
import argparse, os, shutil, sys
from pathlib import Path
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'study', 'previous', 'out'):
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
    old = read(a.previous/'reorth_known_audit1/report.json')
    old_source = read(a.previous/'reorth_known1/report.json')
    known = read(a.study/'known_audit1/report.json')
    source = read(a.study/'known1/report.json')
    mapped = read(a.study/'known_mapped_audit1/report.json')
    storage = read(a.study/'storage_audit1/report.json')
    controls = read(a.study/'controls1/report.json')
    audit = read(a.study/'controls_audit1/report.json')
    assert known['all_qualified'] and mapped['all_qualified']
    assert storage['all12_arrays_bitwise_exact'] and storage['all24_trimmed_raw_bases_verified']
    rows = []
    for before, after, original, current in zip(old['cases'], known['cases'], old_source['cases'], source['cases']):
        assert (before['kind'], before['label']) == (after['kind'], after['label'])
        path0, path1 = a.previous/'reorth_known1'/original['file'], a.study/'known1'/current['file']
        assert sha(path0) == original['sha256'] and sha(path1) == current['sha256']
        inputs[str(path0)], inputs[str(path1)] = sha(path0), sha(path1)
        with np.load(path0) as x, np.load(path1) as y:
            same = bool(np.array_equal(x['fitted'], y['fitted']))
            difference = float(np.max(abs(x['fitted']-y['fitted'])))
        gap_gate = 1e-6*after['original_objective']+1e-10
        rows.append(dict(kind=after['kind'], label=after['label'],
            old_qualified=before['qualified'], qualified=after['qualified'],
            old_stop=before['stopping_code'], stop=after['stopping_code'],
            directions=current['solver']['directions'],
            direct_normal_relative=after['independent_direct_transformed_normal_relative'],
            stable_normal_relative=after['stable_normal_relative'],
            backward_discrepancy=after['independent_backward_discrepancy'],
            gradient=after['gradient'], gap_gate=gap_gate,
            residual_gap=after['certificates']['residual']['gap'],
            representer_gap=after['certificates']['representer']['gap'],
            dense_relative_error=after['dense_relative_error'], fitted_bitwise_equal_old=same,
            maximum_fitted_difference=difference))
    assert len(rows) == 12
    ca = {c['label']:c for c in audit['cases']}
    cs = {c['label']:c['info'] for c in controls['cases']}
    summary = dict(unique_known_cases=12, old_qualified=sum(r['old_qualified'] for r in rows),
        stable_qualified=sum(r['qualified'] for r in rows), mapped_qualified=mapped['pass_count'],
        estimator_controls=audit['controls'], bitwise_equal_old_fitted=sum(r['fitted_bitwise_equal_old'] for r in rows),
        storage_arrays_per_case=[len(c['arrays_sha256']) for c in storage['cases']],
        trimmed_basis_files=sum(len(c['raw_basis_files_sha256']) for c in storage['cases']),
        dense_error_range=[min(r['dense_relative_error'] for r in rows),max(r['dense_relative_error'] for r in rows)],
        max_independent_backward_discrepancy=max(r['backward_discrepancy'] for r in rows),
        maximum_fitted_difference=max(r['maximum_fitted_difference'] for r in rows))
    control_rows = dict(
        outside_gradient=dict(projected=cs['outside_gradient']['projected_only_normal_norm'],
            modeled_full=cs['outside_gradient']['stable_normal_norm'], direct_full=cs['outside_gradient']['direct_normal_norm']),
        ill_conditioned=dict(modeled_full_binary64=cs['ill_conditioned']['stable_normal_norm'],
            high_precision_projected_model=float(ca['ill_conditioned']['projected_high_precision_normal_norm']),
            high_precision_original=float(ca['ill_conditioned']['original_high_precision_normal_norm']),
            gradient_defect_bound=float(ca['ill_conditioned']['projection_gradient_defect_bound']),
            actual_gradient_defect=float(ca['ill_conditioned']['actual_gradient_defect'])),
        projection_defect=dict(backward_discrepancy=cs['projection_defect']['relative_backward_discrepancy'], gate=1e-11))
    data = dict(rows=rows, controls=control_rows, summary=summary,
        gates=dict(normal=1e-11,backward=1e-11,gradient=2e-7,gap_relative=1e-6,gap_absolute=1e-10))
    save(a.out/'figure_inputs.json',data)
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    x = np.arange(12)
    labels = [r['label'] for r in rows]
    fig, axes = plt.subplots(3,1,figsize=(13,10),sharex=True)
    fig.suptitle('Same 12 known problems: stable residual stopping, original guards retained',y=.985)
    axes[0].semilogy(x,[r['direct_normal_relative'] for r in rows],'x',color='#b94b3e',label='Direct subtraction, independently recomputed')
    axes[0].semilogy(x,[r['stable_normal_relative'] for r in rows],'o',color='#246d8d',label='Stable model residual + complete adjoint')
    axes[0].axhline(1e-11,color='black',ls='--',lw=1)
    axes[0].set_ylabel('Normal / (||H||F ||r||)')
    axes[0].legend(loc='upper left',bbox_to_anchor=(0,1.34),ncol=2,frameon=False)
    axes[1].semilogy(x,[r['backward_discrepancy']/1e-11 for r in rows],'o',color='#7f5292')
    axes[1].axhline(1,color='black',ls='--',lw=1)
    axes[1].set_ylabel('Residual discrepancy / gate')
    axes[1].set_ylim(.001,3)
    axes[2].semilogy(x,[r['gradient']/2e-7 for r in rows],'o',label='Original gradient / gate',color='#287e50')
    axes[2].semilogy(x,[max(r['residual_gap'],r['representer_gap'])/r['gap_gate'] for r in rows],'s',label='Larger original gap / gate',color='#b47b21')
    axes[2].axhline(1,color='black',ls='--',lw=1)
    axes[2].set_ylabel('Original guard ratios')
    axes[2].set_ylim(1e-13,3)
    axes[2].legend(loc='upper left',bbox_to_anchor=(0,1.32),ncol=2,frameon=False)
    for ax in axes:
        ax.grid(axis='y',alpha=.2)
        ax.axvline(3.5,color='gray',ls=':',lw=1)
    axes[-1].set_xticks(x,labels,rotation=30,ha='right')
    fig.subplots_adjust(top=.88,bottom=.16,left=.10,right=.98,hspace=.62)
    fig.text(.1,.025,'4 algebra + 8 Hann controls; RAM/mapped are two backends, not 24 independent problems. No new sound or full288 qualification.',fontsize=10)
    fig.savefig(a.out/'known_stopping.png',dpi=150)
    plt.close(fig)
    fig, axes = plt.subplots(1,3,figsize=(14,5.8))
    fig.suptitle('Counterexamples: a tiny projected normal is insufficient',y=.97)
    vals = list(control_rows['outside_gradient'].values())
    axes[0].bar(np.arange(3),vals,color=['#b94b3e','#246d8d','#287e50'])
    axes[0].set_xticks(np.arange(3),['Projected H^T c','Full A^T Uc','Direct A^T(Az-b)'],rotation=25,ha='right')
    axes[0].set_ylim(0,3.6)
    axes[0].set_title('Outside-V gradient control')
    axes[0].set_ylabel('Normal norm')
    for j,v in enumerate(vals): axes[0].text(j,v+.10,f'{v:g}',ha='center')
    ill=control_rows['ill_conditioned']
    vals=[ill[k] for k in ('modeled_full_binary64','high_precision_projected_model','high_precision_original','gradient_defect_bound')]
    axes[1].bar(np.arange(4),vals,color=['#246d8d','#619ab3','#b94b3e','#a68742'])
    axes[1].set_yscale('log')
    axes[1].set_ylim(1e-18,1e3)
    axes[1].set_xticks(np.arange(4),['FP64 modeled','110-digit model','110-digit original','Defect bound'],rotation=25,ha='right')
    axes[1].set_title('Ill-conditioned control')
    axes[1].set_ylabel('Normal / gradient-defect norm')
    for j,v in enumerate(vals): axes[1].text(j,v*3,f'{v:.2g}',ha='center',fontsize=9)
    defect=control_rows['projection_defect']
    axes[2].bar([0,1],[defect['gate'],defect['backward_discrepancy']],color=['#287e50','#b94b3e'])
    axes[2].set_yscale('log')
    axes[2].set_ylim(1e-12,1)
    axes[2].set_xticks([0,1],['Required gate','1% projection defect'],rotation=25,ha='right')
    axes[2].set_title('Deliberate defect is rejected')
    axes[2].set_ylabel('||r_direct-r_model|| / ||b||')
    for j,v in enumerate((defect['gate'],defect['backward_discrepancy'])): axes[2].text(j,v*2,f'{v:.3g}',ha='center')
    for ax in axes: ax.grid(axis='y',alpha=.2)
    fig.subplots_adjust(left=.065,right=.98,bottom=.28,top=.83,wspace=.4)
    fig.text(.065,.035,'Decimal controls use the exact binary64 inputs. The model estimator is not a rigorous bound on the true full normal.',fontsize=10)
    fig.savefig(a.out/'estimator_counterexamples.png',dpi=150)
    plt.close(fig)
    save(a.out/'report.json',dict(result='observer_stable_known_publication_ready',inputs=inputs,
        publisher_sha256=sha(__file__),figure_inputs_sha256=sha(a.out/'figure_inputs.json'),summary=summary,
        images={n:sha(a.out/n) for n in ('known_stopping.png','estimator_counterexamples.png')},
        source_or_full_solver_or_runtime_or_hearing_qualified=False))
    print(summary,flush=True)


if __name__ == '__main__':
    main()
