"""Same observer comparison; descriptive statistics never substitute for listening."""
import argparse,os,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','audit','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from research_archive_v1 import load,save,sha

a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_assessment.py')
run=load(a.input/'report.json');assert load(a.audit/'report.json')['result']=='passed'
r=dict(result='assessed_pending_hearing',input_sha256=sha(a.input/'report.json'),audit_sha256=sha(a.audit/'report.json'),pooled=[],spectra=[],source=[])
parent=Path(run['reuse']['root'])
conditions=[('baseline',parent,run['reuse']['cases'],run['reuse']['spectra']),('independent_old',a.input,run['cases'],run['spectra']),('complex75',a.input,run['cases'],run['spectra'])]
for branch,folder,cases,spectra in conditions:
    for basis in ['procedural','measured_acoustic']:
        rows=[v for v in spectra if v['metadata']['kind']=='generated' and v['metadata']['phase_basis']==basis and (branch=='baseline' or v['metadata']['condition']==branch)];assert len(rows)==24
        r['spectra'].append(dict(branch=branch,phase_basis=basis,blocks=24,summary={k:np.mean([v['summary'][k] for v in rows],axis=0).tolist() for k in rows[0]['summary']}))
        for ms in [50,100,200]:
            rows=[v for v in cases if v['metadata']['kind']=='generated' and v['window_ms']==ms and v['metadata']['phase_basis']==basis and (branch=='baseline' or v['metadata']['condition']==branch)];assert len(rows)==24
            covs={key:[] for key in ['covariance','main_covariance','detail_covariance','cross_covariance']};rho=[];power=[]
            for row in rows:
                path=folder/row['file'];assert sha(path)==row['sha256']
                with np.load(path) as f:
                    for key in covs:covs[key].append(f[key])
                    rho.append(f['rho_100_200_500ms']);power.append(f['temporal_power'])
                    # Independent direct centered sample variance equals each stored lag0.
                    c=f['coefficients'][:,0,[1,2,4]]/f['reference'];x=np.column_stack((c.real,c.imag))
                    assert abs(np.var(x,axis=0)-np.diag(f['covariance'][25])).max()<1e-10
            means={key:np.mean(value,axis=0) for key,value in covs.items()};total=np.diag(means['covariance'][25])
            r['pooled'].append(dict(branch=branch,phase_basis=basis,window_ms=ms,blocks=24,mix_std=np.sqrt(total).tolist(),
                main_std=np.sqrt(np.diag(means['main_covariance'][25])).tolist(),detail_std=np.sqrt(np.diag(means['detail_covariance'][25])).tolist(),
                signed_fractions=np.array([np.diag(means[key][25])/total for key in ['main_covariance','detail_covariance','cross_covariance']]).tolist(),
                rho_mean=np.mean(rho,axis=0).tolist(),temporal_power_mean=np.mean(power,axis=0).tolist()))
for row in run['reuse']['cases']:
    if row['metadata']['kind']=='source':r['source'].append(dict(label=row['label'],window_ms=row['window_ms'],std=row['std']))
for row in run['reuse']['spectra']:
    if row['metadata']['kind']=='source':r['spectra'].append(dict(branch=row['label'],phase_basis='measured_acoustic',blocks=1,summary=row['summary']))
fig,axes=plt.subplots(1,3,figsize=(15,4.4),layout='constrained')
colours={'baseline':'#617e94','independent_old':'#ae9150','complex75':'#218977'}
for branch in colours:
    rows=[v for v in r['pooled'] if v['branch']==branch and v['phase_basis']=='measured_acoustic']
    axes[0].plot([v['window_ms'] for v in rows],[v['mix_std'][0] for v in rows],'o-',label=branch,color=colours[branch])
    v=next(v for v in r['spectra'] if v['branch']==branch and v['phase_basis']=='measured_acoustic')
    axes[1].plot(np.arange(3),10*np.log10(np.array(v['summary']['baseband_power'])[:,0]),'o-',label=branch,color=colours[branch])
    rows=[v for v in r['pooled'] if v['branch']==branch and v['phase_basis']=='measured_acoustic' and v['window_ms']==50]
    axes[2].plot(np.arange(3),rows[0]['mix_std'][:3],'o-',label=branch,color=colours[branch])
for part,style in [('train','--'),('check',':')]:
    rows=[v for v in r['source'] if v['label']=='source_'+part]
    axes[0].plot([v['window_ms'] for v in rows],[v['std'][0] for v in rows],style,label='F2 '+part,color='#233d48')
    v=next(v for v in r['spectra'] if v['branch']=='source_'+part)
    axes[1].plot(np.arange(3),10*np.log10(np.array(v['summary']['baseband_power'])[:,0]),style,label='F2 '+part,color='#233d48')
    row=next(v for v in rows if v['window_ms']==50);axes[2].plot(np.arange(3),row['std'][:3],style,label='F2 '+part,color='#233d48')
axes[0].set(title='Estimated 75Hz real variation',xlabel='Hann aperture (ms)',ylabel='Pooled block-centered standard deviation')
axes[1].set(title='Residual around estimated 75Hz',xlabel='Absolute offset (Hz)',ylabel='Both signed bands; dB FS squared');axes[1].set_xticks(range(3),['0–3','3–8','8–15'])
axes[2].set(title='50ms real variation by acoustic line',xlabel='Line frequency (Hz)',ylabel='Pooled block-centered standard deviation');axes[2].set_xticks(range(3),['75','112','187'])
for ax in axes:ax.grid(alpha=.2);ax.legend(fontsize=7)
fig.suptitle('Three fresh 24s takes; same gain and complete observer, no listening claim',fontsize=12)
file=a.out/'evidence.png';fig.savefig(file,dpi=150);plt.close(fig)
r.update(figure=dict(file=file.name,sha256=sha(file)),source_CHECK_already_seen=True,source_acoustic_coordinate_not_physical_AM_PM=True,
    old75_otherAM_coupling_removed_in_both_new_branches=True,runtime_changed=False,listening_accepted=False)
save(a.out/'report.json',r)
print(dict(result=r['result'],measured50ms=[v for v in r['pooled'] if v['phase_basis']=='measured_acoustic' and v['window_ms']==50],spectra=r['spectra']),flush=True)
