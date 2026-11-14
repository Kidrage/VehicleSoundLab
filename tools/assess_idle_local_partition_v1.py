"""Summarize selected-source allocation, controls and every generated block."""
import argparse,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','audit','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from research_archive_v1 import load,save,sha

a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_assessment.py')
r=dict(result='running',input_sha256=sha(a.input/'report.json'),audit_sha256=sha(a.audit/'report.json'),sources=[],generated=[])
try:
    audit=load(a.audit/'report.json');assert audit['result']=='passed'
    observation=load(a.input/'report.json');assert len(observation['cases'])==80
    profile=load(a.workspace/'baselines/fixed_source_profiles_v1/evidence/trial1/F2_tailpipe/profile.json')
    old=np.array(profile['modal']['amplitude_LR'])[[1,2,4]]
    for row in observation['cases']:
        if row['metadata']['kind']=='generated':continue
        with np.load(a.input/row['file']) as f:
            native=f['variable_coefficients'];beta=f['global_coefficients'];ratio=f['stereo_ratio']
        rms=np.sqrt(np.mean(abs(native)**2,axis=0));rms=np.column_stack((rms,rms*abs(ratio)))
        static=abs(beta[[1,2,4]]-1j*beta[[14,15,17]])
        budgets=row['budgets']['dynamic'];total=np.array(budgets['total']);main=np.array(budgets['main']);residual=np.array(budgets['residual']);cross=np.array(budgets['cross'])
        source=dict(label=row['label'],metadata=row['metadata'],near_line_dynamic_static_residual_ratio=row['residual_near_line_ratio'],
            selected_dynamic_coefficient_RMS_LR=rms.tolist(),selected_global_magnitude_LR=static.tolist(),old_profile_amplitude_LR=old.tolist(),
            total_power_LR=total.tolist(),main_power_LR=main.tolist(),residual_power_LR=residual.tolist(),signed_cross_power_LR=cross.tolist(),
            cross_fraction_original7bands=(cross[1:-1]/total[1:-1]).tolist(),
            independent_debt_original7bands=(total-main)[1:-1].tolist(),
            negative_independent_debt_cells=int(np.sum((total-main)[1:-1]<0)),
            maximum_absolute_cross_fraction_original7bands=float(abs(cross[1:-1]/total[1:-1]).max()))
        r['sources'].append(source)
    for condition in ['0.0','0.5','1.0']:
        for seed in [149921,277139,381611]:
            rows=[row for row in observation['cases'] if row['metadata']['kind']=='generated'
                  and row['metadata']['seed']==seed and row['metadata']['condition']==condition]
            assert len(rows)==8
            values=np.array([row['residual_near_line_ratio'] for row in rows])
            r['generated'].append(dict(seed=seed,condition=condition,blocks=8,
                near_line_ratio_median=np.median(values,axis=0).tolist(),minimum=values.min(axis=0).tolist(),maximum=values.max(axis=0).tolist(),
                near_line_ratios_all_blocks=values.tolist()))
    source=[x for x in r['sources'] if x['metadata']['kind']=='source'];controls=[x for x in r['sources'] if x['metadata']['kind']=='samePSD_control']
    fig,axes=plt.subplots(2,2,figsize=(12,8),layout='constrained');line=[75,112,187]
    for src,color in zip(source,['#243d5a','#697c86']):axes[0,0].plot(line,np.array(src['near_line_dynamic_static_residual_ratio'])[:,0],'s--',label=src['metadata']['part'],color=color)
    control=np.array([x['near_line_dynamic_static_residual_ratio'] for x in controls])[:,:,0]
    axes[0,0].plot(line,np.median(control,axis=0),':',color='#b94e35',label='same-PSD controls median')
    axes[0,0].fill_between(line,control.min(axis=0),control.max(axis=0),alpha=.12,color='#b94e35')
    for condition,color in [('0.0','#8798a4'),('0.5','#28776c'),('1.0','#d9a449')]:
        data=np.array([x['near_line_ratio_median'] for x in r['generated'] if x['condition']==condition])[:,:,0]
        axes[0,0].plot(line,np.median(data,axis=0),'o-',label='generated '+condition,color=color)
    axes[0,0].set(title='Dynamic/static remaining power within +/-10Hz',xlabel='acoustic line (Hz)',ylabel='remaining residual power ratio');axes[0,0].legend(fontsize=8)
    axes[0,1].plot(line,old[:,0],'o-',label='old profile',color='#8798a4')
    for src,color in zip(source,['#243d5a','#28776c']):
        axes[0,1].plot(line,np.array(src['selected_dynamic_coefficient_RMS_LR'])[:,0],'s--',label='source '+src['metadata']['part'],color=color)
    axes[0,1].set(title='Coefficient RMS; analysis proxy, not adopted gain',xlabel='acoustic line (Hz)',ylabel='linear amplitude');axes[0,1].legend(fontsize=8)
    for ax,src in zip([axes[1,0],axes[1,1]],source):
        total=np.array(src['total_power_LR'])[1:-1,0]
        for j,(name,color) in enumerate([('main','#243d5a'),('residual','#28776c'),('signed_cross','#d9a449')]):
            values=np.array(src[name+'_power_LR'])[1:-1,0]/total
            ax.bar(np.arange(7)+(j-1)*.24,values,width=.23,label=name,color=color)
        ax.axhline(1,color='#999',lw=.7);ax.axhline(0,color='#777',lw=.7)
        ax.set_xticks(np.arange(7),['30-120','120-400','400-1.2k','1.2-2.2k','2.2-4k','4-8k','8-14k'],rotation=22)
        ax.set(title='Source '+src['metadata']['part']+' dynamic budget incl. signed cross',ylabel='fraction of mixed recording band power');ax.legend(fontsize=8)
    for ax in axes.flat:ax.grid(alpha=.2)
    fig.suptitle('Idle allocation: local fit reduces controls too; residual is not an identified noise source',fontsize=13)
    figure=a.out/'assessment.png';fig.savefig(figure,dpi=150);plt.close(fig)
    r.update(result='all_local_partition_cases_assessed',figure=dict(file=figure.name,sha256=sha(figure)),
        source_CHECK_already_inspected=True,new_synthesis_model=False,physical_source_identified=False,
        reductions_are_not_hearing_scores=True,runtime_changed=False,listening_accepted=False,
        next='Do not copy local coefficient trajectories or fit a larger envelope just to remove residual. Source residual187 retains much power while generated noise has more slow removable beating; jointly budget coherent main amplitude and residual before another generator. Retain pending listening and full driving goal.')
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(dict(result=r['result'],source=[dict(label=x['label'],ratios=x['near_line_dynamic_static_residual_ratio'],
     dynamic_RMS=x['selected_dynamic_coefficient_RMS_LR'],max_cross=x['maximum_absolute_cross_fraction_original7bands'],
     negative_debt=x['negative_independent_debt_cells']) for x in r['sources'] if x['metadata']['kind']=='source']),flush=True)
