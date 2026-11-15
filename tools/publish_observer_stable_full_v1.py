"""Publish the terminal full288 solve, including failed guards and regressions."""
import argparse, os, shutil, sys
from pathlib import Path
from research_archive_v1 import load, save, sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','study','audit','out'):
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    os.environ['MPLBACKEND']='Agg'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    import matplotlib.pyplot as plt
    report=load(a.study/'report.json')
    audit=load(a.audit/'report.json')
    assert report['result']=='observer_stable_full_known_measured'
    assert audit['result']=='independent_observer_stable_full_passed'
    assert audit['producer_sha256']==sha(a.study/'report.json')
    assert report['solver_qualified']==audit['solver_qualified']
    assert report['fidelity_qualified']==audit['fidelity_qualified']
    units_path=a.study.parent/'frequency_units_audit1/report.json'
    units=load(units_path)
    assert units['result']=='independent_observer_stable_frequency_units_passed'
    assert units['producer_source_sha256']==report['sources']['tools/run_observer_stable_full_v1.py']
    assert units['analysis_rate_Hz']==65536 and units['final_band_Hz']==[14000.,32768.]
    a.out.mkdir(parents=True,exist_ok=False)
    shutil.copy2(__file__,a.out/'executed_publication.py')
    solver=report['solver']
    before,after=report['old_results'],audit['metrics']
    checkpoints=[]
    for c in solver['checkpoints']:
        checkpoints.append(dict(directions=c['directions'],stable_normal_relative=c['stable_normal_relative'],
            direct_normal_relative=c['direct_normal_relative'],backward_discrepancy=c['relative_backward_discrepancy'],
            original_gradient=c['original_checks']['relative_stationarity'],accepted=c['accepted'],
            original_residual_gap_passed=c['original_checks']['residual_gap_passed'],
            original_representer_gap_passed=c['original_checks']['representer_gap_passed']))
    assert checkpoints and checkpoints[-1]['directions']==solver['directions']
    # The earlier producer report remains an immutable bound input.
    original_paths=[Path(n) for n in report['inputs'] if n.endswith('report.json') and 'observer_representer_v1' in n]
    assert len(original_paths)==1
    original_path=original_paths[0]
    original=load(original_path)
    gaps=[]
    for label,version in (('previous',original),('stable',report)):
        values=[version['residual_certificate'],version['representer_certificate']]
        for kind,c in zip(('residual','representer'),values):
            gate=1e-6*c['primal']+1e-10
            gaps.append(dict(version=label,kind=kind,gap=c['gap_upper_bound'],gate=gate,ratio=c['gap_upper_bound']/gate,
                passed=bool(c['gap_upper_bound']<=gate),objective=c['primal']))
    # Root64 * 1024 gives 65536 Hz in this KNOWN analysis coordinate.
    # The complete-bin metric's final band runs to Nyquist, not to 21.6 kHz.
    bands=['0-3','3-6','6-8','8-10','10-14','14-32.768']
    rows=[]
    for field in ('target_supported_band_complex_NRMSE','whole_supported_band_complex_NRMSE'):
        for band,old,new in zip(bands,before[field],after[field]):
            rows.append(dict(metric=field,band_kHz=band,previous=old,stable=new,regressed=bool(new>old)))
    for field in ('whole_wave_NRMSE','target_wave_NRMSE'):
        rows.append(dict(metric=field,previous=before[field],stable=after[field],regressed=bool(after[field]>before[field])))
    for region,old,new in zip(('before','target','after'),before['whole_wave_regions_NRMSE'],after['whole_wave_regions_NRMSE']):
        rows.append(dict(metric='whole_wave_regions_NRMSE',region=region,previous=old,stable=new,regressed=bool(new>old)))
    summary=dict(solver_qualified=report['solver_qualified'],fidelity_qualified=report['fidelity_qualified'],
        directions=solver['directions'],stopping_code=solver['stop'],accepted=solver['accepted'],
        original_gradient=audit['original_space_gradient'],full_Gram_verified=audit['full_basis_Grams_verified'],
        projection_columns_independently_checked=len(audit['independently_checked_projection_columns']),
        final_stable_estimator_pass=audit['independent_stable_pass'],
        final_backward_discrepancy=audit['independent_backward_discrepancy'],
        regressions={field:sum(r['regressed'] for r in rows if r['metric']==field) for field in sorted({r['metric'] for r in rows})},
        whole_wave_NRMSE_before=before['whole_wave_NRMSE'],whole_wave_NRMSE_after=after['whole_wave_NRMSE'],
        target_wave_NRMSE_before=before['target_wave_NRMSE'],target_wave_NRMSE_after=after['target_wave_NRMSE'],
        source_or_native48k_or_C_or_hearing_qualified=False)
    inputs={str(a.study/'report.json'):sha(a.study/'report.json'),str(a.audit/'report.json'):sha(a.audit/'report.json'),str(original_path):sha(original_path),str(units_path):sha(units_path)}
    data=dict(checkpoints=checkpoints,gaps=gaps,fidelity_rows=rows,summary=summary,
        gates=dict(stable_normal=1e-11,backward=1e-11,original_gradient=2e-7,gap_relative=1e-6,gap_absolute=1e-10))
    save(a.out/'figure_inputs.json',data)
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(3,1,figsize=(12,10))
    fig.suptitle('Full288 known problem: stopping estimates and original guards',y=.985)
    x=[c['directions'] for c in checkpoints]
    axes[0].semilogy(x,[c['stable_normal_relative']/1e-11 for c in checkpoints],label='Stable model normal / gate',color='#246d8d')
    axes[0].semilogy(x,[c['original_gradient']/2e-7 for c in checkpoints],label='Original gradient / gate',color='#b94b3e')
    axes[0].set_ylabel('Stopping / gradient ratios')
    axes[0].legend(loc='upper left',bbox_to_anchor=(0,1.30),ncol=2,frameon=False)
    axes[1].semilogy(x,[c['backward_discrepancy']/1e-11 for c in checkpoints],color='#7f5292')
    axes[1].set_ylabel('Residual discrepancy / gate')
    for ax in axes[:2]:
        ax.axhline(1,color='black',ls='--',lw=1)
        ax.set_xlabel('Krylov directions')
        ax.grid(axis='y',alpha=.2)
    labels=[r['version']+'\n'+r['kind'] for r in gaps]
    axes[2].bar(np.arange(4),[r['ratio'] for r in gaps],color=['#999999','#999999','#246d8d','#246d8d'])
    axes[2].set_yscale('log')
    axes[2].set_xticks(np.arange(4),labels)
    axes[2].axhline(1,color='black',ls='--',lw=1)
    axes[2].set_ylabel('Final original gap / gate')
    axes[2].grid(axis='y',alpha=.2)
    fig.subplots_adjust(top=.89,bottom=.10,left=.12,right=.98,hspace=.58)
    fig.text(.12,.025,'One full known problem, same objective and 4000 cap. Model-normal estimates are not rigorous full-normal bounds.',fontsize=10)
    fig.savefig(a.out/'full_stopping.png',dpi=150)
    plt.close(fig)
    fig,axes=plt.subplots(3,1,figsize=(12,10))
    fig.suptitle('Full288 known problem: all fidelity changes retained',y=.985)
    for ax,field,title in zip(axes[:2],('target_supported_band_complex_NRMSE','whole_supported_band_complex_NRMSE'),('Target: fully supported spectral rows','Whole: all supported spectral rows')):
        selected=[r for r in rows if r['metric']==field]
        x=np.arange(6)
        ax.semilogy(x,[r['previous'] for r in selected],'s-',color='#999999',label='Previous full4000')
        ax.semilogy(x,[r['stable'] for r in selected],'o-',color='#246d8d',label='Stable full solve')
        ax.set_xticks(x,bands)
        ax.set_title(title)
        ax.set_xlabel('Observer bands (kHz in the 65536 Hz analysis coordinate)')
        ax.set_ylabel('Complex NRMSE')
    axes[0].legend(loc='upper left',bbox_to_anchor=(0,1.49),ncol=2,frameon=False)
    selected=rows[-5:]
    labels=['Whole wave','Target wave','Before region','Target region','After region']
    x=np.arange(5)
    axes[2].semilogy(x,[r['previous'] for r in selected],'s-',color='#999999')
    axes[2].semilogy(x,[r['stable'] for r in selected],'o-',color='#246d8d')
    axes[2].set_xticks(x,labels)
    axes[2].set_ylabel('Waveform NRMSE')
    for ax in axes: ax.grid(axis='y',alpha=.2)
    fig.subplots_adjust(top=.86,bottom=.09,left=.11,right=.98,hspace=.63)
    fig.text(.11,.025,'Not native48k audio, measured RPM, material inference or sustained synthesis. Lower is better; all regressions remain in JSON.',fontsize=10)
    fig.savefig(a.out/'full_fidelity.png',dpi=150)
    plt.close(fig)
    save(a.out/'report.json',dict(result='observer_stable_full_publication_ready',inputs=inputs,
        publisher_sha256=sha(__file__),figure_inputs_sha256=sha(a.out/'figure_inputs.json'),summary=summary,
        images={n:sha(a.out/n) for n in ('full_stopping.png','full_fidelity.png')},
        source_or_runtime_or_hearing_qualified=False))
    print(summary,flush=True)


if __name__=='__main__':
    main()
