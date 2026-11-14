"""All F3 reference-to-upper power associations and absolute powers; no source recovery."""
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
run=load(a.input/'report.json');audit=load(a.audit/'report.json')
assert audit['result']=='native_and_summaries_passed_full_MSC_tolerance_not_passed'
assert audit['observations']==12 and audit['fixed_30_to600Hz_summaries_passed']
assert not audit['full_MSC_independent_tolerance_passed']
r=dict(result='fixed_band_associations_assessed_full_MSC_gate_unpassed',input_sha256=sha(a.input/'report.json'),
       audit_sha256=sha(a.audit/'report.json'),segments=[],figures=[],same_channel_above_all_controls=0,same_channel_cases=0)
segments=['F3_fifth1','F3_fifth2','F3_sixth'];upper_names=['4-8 kHz L','4-8 kHz R','8-14 kHz L','8-14 kHz R']
labels=['30-120','120-200','200-400','400-600'];x=np.arange(4)
fig,axes=plt.subplots(4,3,figsize=(14,12),layout='constrained',sharex=True)
fig2,axs2=plt.subplots(1,3,figsize=(14,4.5),layout='constrained')
all_log=[]
for column,segment in enumerate(segments):
    source=next(v for v in run['observations'] if v['segment']==segment and v['branch']=='original')
    controls=[v for v in run['observations'] if v['segment']==segment and v['branch']!='original'];assert len(controls)==3
    rows=[]
    for b,summary in enumerate(source['summary']):
        values=np.array([v['summary'][b]['power_weighted_MSC'] for v in controls])
        original=np.array(summary['power_weighted_MSC']);lo=values.min(axis=0);hi=values.max(axis=0)
        rows.append(dict(band_hz=summary['band_hz'],original=summary,
            controls=[dict(branch=v['branch'],summary=v['summary'][b]) for v in controls],
            original_minus_control_max=(original-hi).tolist(),
            original_above_all_three=(original>hi).tolist(),control_min=lo.tolist(),control_max=hi.tolist()))
        for j in range(4):r['same_channel_cases']+=1;r['same_channel_above_all_controls']+=int(original[j%2,j]>hi[j%2,j])
    r['segments'].append(dict(segment=segment,windows=source['windows'],bands=rows))
    for j in range(4):
        ax=axes[j,column]
        for i,colour,style,label in [(j%2,'#247f73','-','same-channel'),(1-j%2,'#a36b31','--','opposite-channel')]:
            y=np.array([v['summary'][b]['power_weighted_MSC'][i][j] for b in range(4) for v in [source]])
            ctrl=np.array([[v['summary'][b]['power_weighted_MSC'][i][j] for b in range(4)] for v in controls])
            ax.fill_between(x,ctrl.min(axis=0),ctrl.max(axis=0),color=colour,alpha=.16)
            ax.plot(x,y,'o'+style,color=colour,label=label+' source',ms=4)
            for k in range(3):ax.plot(x,ctrl[k],'.',color=colour,alpha=.6,ms=3)
        ax.set(title=segment+' | '+upper_names[j],ylim=(0,max(.08,ax.get_ylim()[1]*1.05)))
        ax.set_xticks(x,labels,rotation=15);ax.grid(axis='y',alpha=.2)
        if column==0:ax.set_ylabel('Upper-power-weighted MSC')
        if j==3:ax.set_xlabel('Acoustic modulation frequency (Hz)')
        if j==0 and column==0:ax.legend(fontsize=7)
    modulation=np.array([v['upper_power_modulation'] for v in source['summary']]).T
    log=np.log10(modulation);all_log.append(log)
    ax=axs2[column];im=ax.imshow(log,aspect='auto',vmin=-17,vmax=-9,cmap='viridis')
    ax.set(title=segment,xlabel='Modulation frequency (Hz)');ax.set_xticks(x,labels,rotation=20);ax.set_yticks(x,upper_names)
    for i in range(4):
        for j in range(4):ax.text(j,i,f'{modulation[i,j]:.1e}',ha='center',va='center',fontsize=8,color='white' if log[i,j]<-12 else 'black')
fig.suptitle('Low acoustic recording vs upper analytic-power modulation | all 8 pairs\n3 same-recording phase controls: dots/range, not confidence intervals; no excitation identity',fontsize=12)
fig2.colorbar(im,ax=axs2,shrink=.8,label='log10 integrated upper-power modulation (FS^4)')
fig2.suptitle('Original absolute modulation powers | weighted MSC alone cannot measure detail strength',fontsize=12)
for name,figure in [('association.png',fig),('absolute_power.png',fig2)]:
    file=a.out/name;figure.savefig(file,dpi=150);plt.close(figure);r['figures'].append(dict(file=name,sha256=sha(file)))
r.update(full_MSC_independent_tolerance_passed=False,first_failure_and_all12_failures_preserved=True,
    same_recording_and_overlapping_windows_not_confidence_intervals=True,
    no_physical_RPM_or_source_identity=True,new_audio=False,new_profile=False,runtime_changed=False,
    next='Do not drive fast upper details with a low-waveform gain from coherence alone. Fixed-frequency association is descriptive and beating can reproduce it. Preserve separate slow colour, joint fast upper innovations and independent components; require qualified cyclic/state evidence before locking to an engine clock. Pending new idle candidate must be heard before any isolated C migration.')
save(a.out/'report.json',r)
print(dict(result=r['result'],same_channel_above_all_controls=r['same_channel_above_all_controls'],cases=r['same_channel_cases']),flush=True)
for row in r['segments']:
    print(row['segment'],flush=True)
    for b in row['bands']:
        same=[b['original']['power_weighted_MSC'][j%2][j] for j in range(4)]
        maxcontrol=[b['control_max'][j%2][j] for j in range(4)]
        print(dict(band=b['band_hz'],same_channel=same,control_max=maxcontrol),flush=True)
