"""Summarize actual layer variation, keeping phase-basis and source limits visible."""
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
run=load(a.input/'report.json');audit=load(a.audit/'report.json')
assert audit['result']=='passed' and audit['input_sha256']==sha(a.input/'report.json')
r=dict(result='running',input_sha256=sha(a.input/'report.json'),audit_sha256=sha(a.audit/'report.json'),groups={},source={})
curves={};psds={}
for row in run['cases']:
    if row['metadata']['kind'] not in ['source','samePSD_control']:continue
    with np.load(a.input/row['file']) as f:curves[row['label']]=f['covariance'];psds[row['label']]=f['temporal_power']
    r['source'][row['label']]=row['stats']
for condition in ['0.0','0.5','1.0']:
    for basis in ['procedural','measured_acoustic']:
        rows=[row for row in run['cases'] if row['metadata'].get('condition')==condition and row['metadata']['phase_basis']==basis]
        assert len(rows)==24
        arrays={name:[] for name in ['covariance','main_covariance','detail_covariance','cross_covariance','temporal_power']}
        for row in rows:
            with np.load(a.input/row['file']) as f:
                for name in arrays:arrays[name].append(f[name])
        mean={name:np.mean(value,axis=0) for name,value in arrays.items()};v=np.diag(mean['covariance'][25])
        ratios=np.array([np.diag(mean[name][25])/v for name in ['main_covariance','detail_covariance','cross_covariance']])
        assert abs(ratios.sum(axis=0)-1).max()<1e-8
        key=condition+'_'+basis;curves[key]=mean['covariance'];psds[key]=mean['temporal_power']
        r['groups'][key]=dict(blocks=24,seeds=3,within_block_pooled_std=np.sqrt(v).tolist(),
            rho_100_200_500ms=np.array([np.diag(mean['covariance'][25+lag])/v for lag in [5,10,25]]).tolist(),
            pooled_signed_main_detail_cross_variance_ratios=ratios.tolist(),
            mean_temporal_band_power=mean['temporal_power'].tolist(),
            temporal_band_power_fractions=(mean['temporal_power']/mean['temporal_power'].sum(axis=0)).tolist(),
            per_seed_median_std=[np.median([row['stats']['std'] for row in rows if row['metadata']['seed']==seed],axis=0).tolist() for seed in [149921,277139,381611]])
        # Recheck the pooled signed budget, independently of per-case table ratios.
        assert abs(mean['covariance']-mean['main_covariance']-mean['detail_covariance']-mean['cross_covariance']).max()<1e-9
fig,axes=plt.subplots(2,2,figsize=(13.2,8.6),layout='constrained');freq=[75,112,187];colors=['#25858a','#ca8837','#9b627c']
ratio=np.array(r['groups']['1.0_measured_acoustic']['pooled_signed_main_detail_cross_variance_ratios'])[:,:3]
for j,(label,color) in enumerate(zip(['Main','Detail','Signed cross'],colors)):
    axes[0,0].bar(np.arange(3)+(j-1)*.24,ratio[j]*100,width=.24,label=label,color=color)
axes[0,0].axhline(0,color='black',linewidth=.7);axes[0,0].set_xticks(np.arange(3),freq)
axes[0,0].set(title='Full-AM take: REAL coefficient variation budget',ylabel='Share of mean within-block variance (%)',xlabel='Acoustic line (Hz)');axes[0,0].legend(fontsize=8)
for condition,label,color in [('0.5','New allocation; no AM','#25858a'),('1.0','New allocation + full AM','#ca8837')]:
    for basis,style in [('measured_acoustic','o-'),('procedural','x:')]:
        std=np.array(r['groups'][condition+'_'+basis]['within_block_pooled_std'])[:3]
        axes[0,1].plot(freq,std,style,color=color,label=label+(' / measured' if basis=='measured_acoustic' else ' / known'))
for part,color in [('train','#303030'),('check','#6c747c')]:
    axes[0,1].plot(freq,r['source']['source_'+part]['std'][:3],'s--',color=color,label='F2 '+part)
axes[0,1].set(title='75 Hz too quiet;187 Hz still too variable',ylabel='Normalized real coefficient std',xlabel='Acoustic line (Hz)');axes[0,1].legend(fontsize=7)
for key,label,color,style in [('source_train','F2 TRAIN','#303030','-'),('source_check','F2 CHECK','#6c747c','--'),
    ('1.0_measured_acoustic','Full AM / measured','#ca8837','-'),('1.0_procedural','Full AM / known','#25858a',':')]:
    c=curves[key];axes[1,0].plot(np.arange(26)*.02,c[25:,0,0]/c[25,0,0],label=label,color=color,linestyle=style)
axes[1,0].axhline(0,color='black',linewidth=.5)
axes[1,0].set(title='75 Hz: current AM has a longer100 ms correlation',xlabel='Lag (seconds)',ylabel='Normalized real-coefficient autocovariance');axes[1,0].legend(fontsize=8)
keys=['source_train','source_check','0.5_measured_acoustic','1.0_measured_acoustic'];labels=['F2 TRAIN','F2 CHECK','No AM','Full AM']
bottom=np.zeros(4)
for k,(band,color) in enumerate(zip(['0-1 Hz','1-3 Hz','3-8 Hz','8-25 Hz'],['#48657b','#25858a','#ca8837','#a786a8'])):
    frac=np.array([psds[key][k,0]/psds[key][:,0].sum() for key in keys]);axes[1,1].bar(np.arange(4),frac,bottom=bottom,label=band,color=color);bottom+=frac
axes[1,1].set_xticks(np.arange(4),labels);axes[1,1].set_ylim(0,1)
axes[1,1].set(title='75 Hz coefficient variation: temporal power',ylabel='Fraction of finite Hann temporal power');axes[1,1].legend(fontsize=8,loc='lower right')
for ax in axes.flat:ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True)
fig.suptitle('Actual frozen idle buses: target main timing and residual detail separately',fontsize=14)
path=a.out/'evidence.png';fig.savefig(path,dpi=150);plt.close(fig)
fig2,ax2=plt.subplots(1,2,figsize=(12.5,4.5),layout='constrained')
for basis,label,color in [('procedural','Actual procedural phase','#25858a'),('measured_acoustic','Phase estimated from mix','#ca8837')]:
    ax2[0].plot(freq,r['groups']['1.0_'+basis]['within_block_pooled_std'][3:],'o-',label=label,color=color)
for part,color in [('train','#303030'),('check','#6c747c')]:
    ax2[0].plot(freq,r['source']['source_'+part]['std'][3:],'s--',color=color,label='F2 '+part+' / measured')
ax2[0].set(title='Imaginary coefficient variation changes with phase basis',xlabel='Acoustic line (Hz)',ylabel='Normalized imaginary coefficient std');ax2[0].legend(fontsize=8)
components=['Main','Detail','Signed cross','Total']
for j,(basis,label,color) in enumerate([('procedural','Actual procedural phase','#25858a'),('measured_acoustic','Phase estimated from mix','#ca8837')]):
    group=r['groups']['1.0_'+basis];total=group['within_block_pooled_std'][4]**2
    ratio=np.array(group['pooled_signed_main_detail_cross_variance_ratios'])[:,4]
    values=np.r_[ratio*total,total]
    ax2[1].bar(np.arange(4)+(j-.5)*.35,values,width=.35,label=label,color=color)
ax2[1].axhline(0,color='black',linewidth=.6);ax2[1].set_xticks(np.arange(4),components)
ax2[1].set(title='112 Hz imaginary variance: apparent cancellation',ylabel='Mean within-block normalized variance');ax2[1].legend(fontsize=8)
for ax in ax2:ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True)
fig2.suptitle('A phase estimate derived from the mix is not independent phase truth',fontsize=14)
coordinate_path=a.out/'coordinate_evidence.png';fig2.savefig(coordinate_path,dpi=150);plt.close(fig2)
diagnostic_plan=Path(__file__).resolve().parents[1]/'research/idle_variation_budget_v1_coordinate_diagnosis.json'
shutil.copy2(diagnostic_plan,a.out/diagnostic_plan.name)
r.update(result='actual_idle_bus_variation_assessed',figure=dict(file=path.name,sha256=sha(path)),
    coordinate_figure=dict(file=coordinate_path.name,sha256=sha(coordinate_path)),coordinate_plan_sha256=sha(diagnostic_plan),
    finite_block_statistics_NOT_confidence_intervals=True,temporal_Hz_NOT_engine_frequency_or_RPM=True,
    source_physical_main_detail_separation=False,new_audio_or_model=False,
    next='Fit75variation time structure with forward observer separately;187 excess mostly detail, not uniform AM. Put measured phase estimator in forward comparison: low observed quadrature is NOT low native phase noise. Preserve signed cross, no direct observed-to-latent covariance mapping/physical separation. No arbitrary pad/noise or rejected mean-only voice; hearing/latest idle audition and full goal remain open.')
save(a.out/'report.json',r)
print(dict(result=r['result'],fullAM_measured=r['groups']['1.0_measured_acoustic'],fullAM_known=r['groups']['1.0_procedural']))
