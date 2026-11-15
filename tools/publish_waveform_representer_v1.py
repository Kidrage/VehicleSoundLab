"""Publish both original12 attempts, failed gates and dense resource arithmetic."""
import argparse, os, shutil, sys
from pathlib import Path
from research_archive_v1 import load, save, sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','study','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();os.environ['MPLBACKEND']='Agg'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    import matplotlib.pyplot as plt
    a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_publication.py')
    inputs={};versions=[]
    for number in (1,2):
        paths=[a.study/f'known{number}/report.json',a.study/f'known_audit{number}/report.json']
        source,audit=map(load,paths)
        assert audit['result']=='independent_waveform_representer_original12_measured'
        assert audit['producer_sha256']==sha(paths[0])
        for path in paths:inputs[str(path)]=sha(path)
        rows=[]
        for s,v in zip(source['cases'],audit['cases']):
            assert s['label']==v['label'] and s['kind']==v['kind']
            rows.append(dict(kind=s['kind'],label=s['label'],dense_error=v['dense_relative_error'],
                original_direct_normal=v['independent_original_direct_normal_relative'],
                root_direct_normal=v['root_direct_normal_relative'],
                original_stable_normal=v.get('original_stable_normal_relative'),
                original_backward_discrepancy=v.get('original_backward_discrepancy'),
                qualified=v['qualified'],all_original_equations_and_gaps_passed=v['original_equations_and_gaps_passed'],
                residual_gap_ratio=s['residual_certificate']['gap_upper_bound']/(1e-6*s['residual_certificate']['primal']+1e-10),
                representer_gap_ratio=s['representer_certificate']['gap_upper_bound']/(1e-6*s['representer_certificate']['primal']+1e-10),
                metric_seconds=s['metric_build_seconds'],solve_seconds=s['root_and_solve_seconds'],
                cumulative_peak_bytes=s['process_peak_working_set_bytes'],metric_bytes=s['dense_wave_metric_bytes'],
                original_primal_condition=s['solver']['primal_augmented_condition'],
                waveform_dual_condition=s['solver']['dual_augmented_condition']))
        versions.append(rows)
    # Array sizes are conditional dense-allocation arithmetic, not a peak RAM
    # prediction. In particular, shared L/R has not been assumed for a real run.
    N,P=12289,2*49*288;K=min(N,P)
    full_sizes=dict(mono_wave_metric=8*N*N,mono_dense_penalty=8*P*P,
        mono_penalty_Cholesky=8*P*P,mono_weighted_Phi=8*N*P,
        mono_whitened_X=8*N*P,mono_X_QR_storage=8*N*P,
        mono_dual_augmented_matrix=8*(P+K)*K,
        mono_current_full_dual_Q=8*(P+K)**2,
        stereo_dense_penalty=8*(2*P)**2)
    summary=dict(unique_original_cases=12,explicit_algebra_controls=7,finite_DFT_controls=4,
        before_passes=sum(v['qualified'] for v in versions[0]),after_passes=sum(v['qualified'] for v in versions[1]),
        all_original_equations_and_gaps_passed=all(v['all_original_equations_and_gaps_passed'] for v in versions[1]),
        known_dense_error_min=min(v['dense_error'] for v in versions[1]),known_dense_error_max=max(v['dense_error'] for v in versions[1]),
        failed_labels=[v['label'] for v in versions[1] if not v['qualified']],
        failed_original_stable_normal=[v['original_stable_normal'] for v in versions[1] if not v['qualified']],
        peak_process_bytes=max(v['cumulative_peak_bytes'] for v in versions[1]),
        full_array_bytes=full_sizes,full_shape_hypothesis=dict(mono_waveform_frames=N,mono_source_columns=P),
        full_runtime_or_material_qualified=False,original_stopping_and_gap_gates_unchanged=True)
    figures=dict(versions=versions,summary=summary)
    save(a.out/'figure_inputs.json',figures)
    plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False})
    x=np.arange(12);labels=[v['label'].replace('constant_','const ').replace('curved_','curve ') for v in versions[1]]
    fig,axes=plt.subplots(3,1,figsize=(12,10))
    fig.suptitle('Same original12 controls: equivalence is not a stopping qualification',y=.985)
    axes[0].semilogy(x,[v['dense_error'] for v in versions[0]],'s-',label='First direct representation',color='#888888')
    axes[0].semilogy(x,[v['dense_error'] for v in versions[1]],'o-',label='Householder residual representation',color='#246d8d')
    axes[0].axhline(2e-7,color='black',ls='--');axes[0].set_ylabel('Original dense-node relative error')
    axes[0].legend(loc='upper left',bbox_to_anchor=(0,1.31),ncol=2,frameon=False)
    axes[1].semilogy(x,[v['original_direct_normal']/1e-11 for v in versions[0]],'s-',color='#888888',label='First: original direct normal')
    axes[1].semilogy(x,[v['original_stable_normal']/1e-11 for v in versions[1]],'o-',color='#246d8d',label='Second: original stable full normal')
    axes[1].axhline(1,color='black',ls='--');axes[1].set_ylabel('Complete normal / original gate')
    axes[1].legend(loc='upper left',bbox_to_anchor=(0,1.30),ncol=2,frameon=False)
    axes[2].semilogy(x,[v['residual_gap_ratio'] for v in versions[1]],'o-',color='#246d8d',label='Residual dual gap')
    axes[2].semilogy(x,[v['representer_gap_ratio'] for v in versions[1]],'s--',color='#b94b3e',label='Representer dual gap')
    axes[2].axhline(1,color='black',ls='--');axes[2].set_ylabel('Gap / unchanged original gate')
    axes[2].legend(loc='upper left',bbox_to_anchor=(0,1.26),ncol=2,frameon=False)
    for ax in axes:ax.set_xticks(x,labels,rotation=32,ha='right');ax.grid(axis='y',alpha=.2)
    fig.subplots_adjust(left=.12,right=.98,top=.88,bottom=.13,hspace=.91)
    fig.text(.12,.02,'No real recordings or full288 run. All three remaining failures retained; no stopping or gap tolerance relaxed.')
    fig.savefig(a.out/'known_controls.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(2,1,figsize=(12,8))
    fig.suptitle('Offline dense prototype: measured known-case cost and conditional array sizes',y=.98)
    axes[0].bar(x,[v['metric_seconds'] for v in versions[1]],color='#888888',label='Build metric / fixture')
    axes[0].bar(x,[v['solve_seconds'] for v in versions[1]],bottom=[v['metric_seconds'] for v in versions[1]],color='#246d8d',label='Roots and solve')
    axes[0].set_ylabel('Measured seconds on this PC');axes[0].set_xticks(x,labels,rotation=32,ha='right')
    axes[0].legend(loc='upper left',bbox_to_anchor=(0,1.25),ncol=2,frameon=False)
    chosen=['mono_wave_metric','mono_dense_penalty','mono_dual_augmented_matrix','mono_current_full_dual_Q','stereo_dense_penalty']
    axes[1].bar(np.arange(5),[full_sizes[k]/2**30 for k in chosen],color='#b94b3e')
    axes[1].set_xticks(np.arange(5),['Mono W','Mono R','Mono augmented dual','Mono current full Q','Stereo R'])
    axes[1].set_ylabel('GiB per hypothetical dense array');axes[1].grid(axis='y',alpha=.2)
    fig.subplots_adjust(left=.1,right=.98,top=.87,bottom=.15,hspace=.63)
    fig.text(.1,.045,'Array sizes are not peak RAM and cannot be summed without lifetimes. Current process peak: %.2f GiB.\nNo full allocation or SHARC-cycle measurement; structured penalty and Householder storage are required before scaling.'%(summary['peak_process_bytes']/2**30))
    fig.savefig(a.out/'resource_scope.png',dpi=150);plt.close(fig)
    save(a.out/'report.json',dict(result='waveform_representer_publication_ready',inputs=inputs,summary=summary,
        figure_inputs_sha256=sha(a.out/'figure_inputs.json'),publisher_sha256=sha(__file__),
        images={n:sha(a.out/n) for n in ('known_controls.png','resource_scope.png')}))
    print(summary,flush=True)


if __name__=='__main__':main()
