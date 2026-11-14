"""Compare aperture attenuation and source-vs-generator resolution without choosing a window."""
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
a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_assessment.py')
run=load(a.input/'report.json');assert run['result']=='idle_aperture_transfer_and_resolution_observed'
groups={}
for row in run['cases']:groups.setdefault(row['label'],{})[row['window_ms']]=row
transfer=[]
for j,f in enumerate([.5,1.5,4.,7.]):
    values=np.array([[r['controls'][j]['first_power_ratio'],r['controls'][j]['second_power_ratio']] for r in run['transfer']])
    transfer.append(dict(temporal_hz=f,first_power_ratio_range=[float(values[:,0].min()),float(values[:,0].max())],
        second_power_ratio_range=[float(values[:,1].min()),float(values[:,1].max())]))
fig,axes=plt.subplots(1,2,figsize=(12,4.5),layout='constrained')
for row in run['transfer']:
    axes[0].plot([x['temporal_hz'] for x in row['controls']],10*np.log10([x['first_power_ratio'] for x in row['controls']]),'o-',color='#368b8d',alpha=.55)
    axes[0].plot([x['temporal_hz'] for x in row['controls']],10*np.log10([x['second_power_ratio'] for x in row['controls']]),'s--',color='#b96e43',alpha=.55)
axes[0].plot([],[],color='#368b8d',label='One window operation');axes[0].plot([],[],'--',color='#b96e43',label='Window then re-window')
axes[0].set(xlabel='Known modulation frequency (Hz)',ylabel='Finite phase-ensemble power / native (dB)',title='Exact known75Hz perturbation transfer')
for label,colour,style in [('source_train','#223c4a','-'),('source_check','#23898b','--')]:
    values=[groups[label][ms]['std'][0] for ms in [50,100,200]]
    axes[1].plot([50,100,200],values,'o',ls=style,color=colour,label=label)
for label,group in groups.items():
    if not label.startswith('generated_') or 'measured_acoustic' not in label:continue
    axes[1].plot([50,100,200],[group[ms]['std'][0] for ms in [50,100,200]],'o-',color='#bd754b',alpha=.55)
axes[1].plot([],[],color='#bd754b',label='Original fullAM MIX, 3 seeds')
axes[1].set(xlabel='Diagnostic Hann window (ms)',ylabel='75Hz normalized real coefficient std',title='Same centres / references; no selected aperture')
for ax in axes:ax.grid(alpha=.2);ax.legend(fontsize=8)
fig.suptitle('Observation resolution study; no new audio or native excitation claim',fontsize=13)
figure=a.out/'evidence.png';fig.savefig(figure,dpi=150);plt.close(fig)
resolution=[]
for label in groups:
    if label.startswith('phase_'):continue
    for ms,row in groups[label].items():resolution.append(dict(label=label,window_ms=ms,std=row['std'],rho100ms=row['rho'][0],max_condition=row['max_condition']))
report=dict(result='idle_aperture_transfer_assessed',input_sha256=sha(a.input/'report.json'),transfer=transfer,resolution=resolution,
    figure=dict(file=figure.name,sha256=sha(figure)),new_audio=False,new_fit=False,
    known_two_pass_NOT_old_FIR_compiler=True,native_AM_recovered=False,
    next='Use source-derived temporal-shape inference through the exact observer, include actual MIX phase estimator and residual allocation. Do not directly reuse short-window amplitudes as native excitation, select an aperture from CHECK, invert near-null transfer or boost all AM. Pending idle audition and full goal remain.')
save(a.out/'report.json',report);print(report)
