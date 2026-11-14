"""Pool actual24block bus covariance and near75residual without selecting a seed/window."""
import argparse,os,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from research_archive_v1 import load,save,sha
from idle_variation_budget_v1.variation import temporal
a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_assessment.py')
run=load(a.input/'report.json');assert run['result']=='complete_idle_short_bus_and_near75_budget_observed'
r=dict(result='idle_short_bus_and_near75_assessed',input_sha256=sha(a.input/'report.json'),pooled=[],source=[],spectra=[])
for basis in ['procedural','measured_acoustic']:
    for ms in [50,100,200]:
        rows=[row for row in run['cases'] if row['metadata']['kind']=='generated' and row['metadata']['phase_basis']==basis and row['window_ms']==ms];assert len(rows)==24
        covs={key:[] for key in ['covariance','main_covariance','detail_covariance','cross_covariance']};powers=[]
        for row in rows:
            path=a.input/row['file'];assert sha(path)==row['sha256']
            with np.load(path) as f:
                for key in covs:covs[key].append(f[key])
                allpower=[]
                for bus in range(3):
                    value=f['coefficients'][:,bus,[1,2,4]]/f['reference'];v=np.column_stack((value.real,value.imag))
                    allpower.append(temporal(v)[0])
                powers.append(allpower)
        means={key:np.mean(value,axis=0) for key,value in covs.items()};total=np.diag(means['covariance'][25])
        r['pooled'].append(dict(phase_basis=basis,window_ms=ms,blocks=24,
            mix_std=np.sqrt(total).tolist(),main_std=np.sqrt(np.diag(means['main_covariance'][25])).tolist(),
            detail_std=np.sqrt(np.diag(means['detail_covariance'][25])).tolist(),
            main_detail_cross_fractions=np.array([np.diag(means[key][25])/total for key in ['main_covariance','detail_covariance','cross_covariance']]).tolist(),
            temporal_power_mix_main_detail=np.mean(powers,axis=0).tolist()))
for row in run['cases']:
    if row['metadata']['kind']=='source':r['source'].append(dict(label=row['label'],window_ms=row['window_ms'],std=row['std']))
for basis in ['procedural','measured_acoustic']:
    rows=[row for row in run['spectra'] if row['metadata']['kind']=='generated' and row['metadata']['phase_basis']==basis];assert len(rows)==24
    means={key:np.mean([row['summary'][key] for row in rows],axis=0) for key in rows[0]['summary']}
    r['spectra'].append(dict(label='generated_'+basis,blocks=24,summary={key:value.tolist() for key,value in means.items()}))
for row in run['spectra']:
    if row['metadata']['kind']=='source':r['spectra'].append(dict(label=row['label'],blocks=1,summary=row['summary']))
fig,axes=plt.subplots(1,3,figsize=(15,4.5),layout='constrained')
colour={'mix':'#b87546','main':'#577b93','detail':'#47958b'}
for bus in ['mix','main','detail']:
    rows=[row for row in r['pooled'] if row['phase_basis']=='measured_acoustic']
    axes[0].plot([row['window_ms'] for row in rows],[row[bus+'_std'][0] for row in rows],'o-',color=colour[bus],label='Generated '+bus)
for part,style in [('train','--'),('check',':')]:
    rows=[row for row in r['source'] if row['label']=='source_'+part]
    axes[0].plot([row['window_ms'] for row in rows],[row['std'][0] for row in rows],style,color='#223c4a',label='F2 '+part)
axes[0].set(title='75Hz real coefficient variation',xlabel='Hann aperture (ms)',ylabel='Std; generated pooled24blocks')
row=next(row for row in r['pooled'] if row['phase_basis']=='measured_acoustic' and row['window_ms']==50)
for j,label in enumerate(['Main','Detail','Signed cross']):axes[1].bar(np.arange(3)+(j-1)*.24,np.array(row['main_detail_cross_fractions'])[j,:3],width=.24,label=label,color=['#577b93','#47958b','#b87546'][j])
axes[1].set_xticks(np.arange(3),['75','112','187']);axes[1].set(title='50ms actual bus variance fractions',xlabel='Acoustic line (Hz)',ylabel='Fraction of mix variance (signed)')
for label,style,c in [('source_train','-','#263c4b'),('source_check','--','#31978e'),('generated_measured_acoustic','-','#b87546')]:
    row=next(row for row in r['spectra'] if row['label']==label);values=np.array(row['summary']['baseband_power'])[:,0]
    axes[2].plot(np.arange(3),10*np.log10(values),'o',ls=style,color=c,label=label)
axes[2].set_xticks(np.arange(3),['0–3','3–8','8–15']);axes[2].set(title='Residual around estimated75Hz carrier',xlabel='Absolute baseband offset (Hz)',ylabel='Both signed bands, dB FS²')
for ax in axes:ax.grid(axis='y',alpha=.2);ax.legend(fontsize=7)
fig.suptitle('Actual24s bus budget / source residual; no physical AM separation or new sound',fontsize=13)
figure=a.out/'evidence.png';fig.savefig(figure,dpi=150);plt.close(fig)
r.update(figure=dict(file=figure.name,sha256=sha(figure)),source_physical_split=False,new_fit=False,new_audio=False,
    next='Build a source-derived native near75temporal-shape/complex-envelope hypothesis with observer-qualified known controls and explicit oscillator/residual power allocation before rendering. Include phase-estimator effects, preserve187detail separation; do not raise existing AM or fill low residual with arbitrary wind/noise. Source correlation does not yet identify physical excitation or prove the sustained-note cause. Full goal/pending hearing retained.')
save(a.out/'report.json',r);print(dict(result=r['result'],pooled=r['pooled'],spectra=r['spectra']),flush=True)
